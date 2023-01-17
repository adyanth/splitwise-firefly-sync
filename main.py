from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from splitwise import Splitwise, Expense, User, Comment
from splitwise.user import ExpenseUser
from typing import Generator

import os
import requests

time_now = datetime.now().astimezone()


def formatExpense(exp: Expense, myshare: ExpenseUser) -> str:
    return f"Expense {exp.getDescription()} for {exp.getCurrencyCode()} {myshare.getOwedShare()} on {exp.getDate()}"


def getSWUrlForExpense(exp: Expense) -> str:
    return f"{Splitwise.SPLITWISE_BASE_URL}expenses/{exp.getId()}"


def getDate(datestr: str) -> datetime:
    return datetime.fromisoformat(datestr.replace("Z", "+00:00"))


def getExpensesAfter(sw: Splitwise, date: datetime, user: User) -> Generator[tuple[Expense, ExpenseUser, list[str]], None, None]:
    offset = 0
    limit = 20
    expenses: list[Expense] = []
    while True:
        # Splitwise dated_after filters by getDate, not getCreatedAt
        # Splitwise updated_after filters by getUpdatedAt
        # getDate is the entered date in the expense
        # getCreatedAt is the date when the expense was created
        # getUpdatedAt is the date when the expense was last updated
        exp = sw.getExpenses(updated_after=date.isoformat(),
                             offset=offset, limit=limit)
        offset += limit
        if not exp:
            break
        expenses.extend(exp)

    for exp in expenses:
        # Skip deleted expenses
        if exp.getDeletedAt():
            continue

        # Ignore payments
        if exp.getPayment():
            continue

        # Get my share by userId
        myexpense = filter(lambda x: x.getId() == user.getId(), exp.getUsers())
        myshare: ExpenseUser = next(myexpense, None)
        # Ignore transactions where I paid for someone else
        if myshare is None:
            continue

        # Ignore transactions where I do not owe anything
        if myshare.getOwedShare() == "0.0":
            continue

        # Ignore entries added by Splitwise on global settle
        if exp.getDescription() == "Settle all balances":
            continue

        # Get data, latest comment > old comment > notes
        data: str = None

        accept_check = exp.getUpdatedBy() and exp.getUpdatedBy().getId() == user.getId()
        accept_check = accept_check or (
            not exp.getUpdatedBy() and exp.getCreatedBy().getId() == user.getId())

        if accept_check and (details := processText(exp.getDetails())):
            data = details

        c: Comment
        for c in sw.getComments(exp.getId()):
            if c.getCommentedUser().getId() != user.getId():
                pass
            if text := processText(c.getContent()):
                data = text

        # If not found, do not process, report
        if not data:
            print(
                f"-----> {formatExpense(exp, myshare)} matches, no comment found! Enter manually.")
            continue
        if data[0] == True:
            data = []

        yield exp, myshare, data


def processText(text: str) -> list[str]:
    if not text:
        return []
    split = text.split("/")
    if split[0].strip().lower() == "firefly":
        return split[1:] or [True]
    return []


def callApi(path, method="POST", params={}, body={}, fail=True):
    baseUrl = os.getenv("FIREFLY_URL", "http://firefly:8080")
    token = os.getenv("FIREFLY_TOKEN")
    headers = {
        "Authorization": f"Bearer {token}",
        # https://github.com/firefly-iii/firefly-iii/issues/6829
        "Accept": "application/json",
    }

    if method != "GET" and os.getenv("FIREFLY_DRY_RUN"):
        print(f"Skipping {method} call due to dry run.")
        res = requests.Response()
        res.status_code, res._content = 200, b"{}"
        return res

    res = requests.request(
        method,
        f"{baseUrl}/api/v1/{path}",
        headers=headers,
        params=params,
        json=body,
    )
    if fail:
        res.raise_for_status()
    return res


def searchTransactions(params: dict[str, str]) -> list[dict]:
    txns: list[dict] = []
    page = 1
    while True:
        params["page"] = page
        txn: list[dict] = callApi(
            "search/transactions", "GET", params).json()["data"]
        page += 1
        if not txn:
            break
        txns.extend(txn)
    return txns


def getTransactionsAfter(date: datetime) -> dict[str, dict]:
    days: int = (time_now - date).days
    # https://docs.firefly-iii.org/firefly-iii/pages-and-features/search/
    params = {"query": f'date_after:"-{days}d" any_external_url:true'}
    txns = searchTransactions(params)
    return {t["attributes"]["transactions"][0]["external_url"]: t for t in txns}


def updateTransaction(newTxn: dict, oldTxnBody: dict) -> None:
    old_id = oldTxnBody["id"]
    oldTxnBody = oldTxnBody["attributes"]

    for k, val in newTxn.items():
        if (old := oldTxnBody["transactions"][0][k]) != val:
            # Firefly has a lot of 0 after decimal
            if k == "amount" and float(old) == float(val):
                continue
            # Firefly stores time with timezone
            # See https://github.com/firefly-iii/firefly-iii/issues/6810
            if k == "date" or k == "payment_date":
                if getDate(old) == getDate(val):
                    continue
            break
    else:
        print(f"No update needed for {newTxn['description']}")
        return

    oldTxnBody["transactions"][0].update(newTxn)

    # https://github.com/firefly-iii/firefly-iii/issues/6828
    del oldTxnBody["transactions"][0]["foreign_currency_id"]

    try:
        callApi(f"transactions/{old_id}", method="PUT", body=oldTxnBody).json()
    except Exception as e:
        print(
            f"Transaction {newTxn['description']} errored, body: {oldTxnBody}, e: {e}")
        raise
    print(f"Updated Transaction: {newTxn['description']}")


def addTransaction(newTxn: dict) -> None:
    body = {
        "error_if_duplicate_hash": True,
        "group_title": newTxn["description"],
        "transactions": [newTxn]
    }
    try:
        callApi("transactions", method="POST", body=body).json()
    except Exception as e:
        print(
            f"Transaction {newTxn['description']} errored, body: {body}, e: {e}")
        raise
    print(f"Added Transaction: {newTxn['description']}")


def processExpense(past_day: datetime, txns: dict[dict], exp: Expense, *args) -> None:
    newTxn: dict = getExpenseTransactionBody(exp, *args)
    if oldTxnBody := txns.get(getSWUrlForExpense(exp)):
        print("Updating...")
        return updateTransaction(newTxn, oldTxnBody)

    if getDate(exp.getCreatedAt()) < past_day or getDate(exp.getDate()) < past_day:
        if search := searchTransactions({"query": f'external_url_is:"{getSWUrlForExpense(exp)}"'}):
            print("Updating old...")
            # TODO(#1): This would have 2 results for same splitwise expense
            return updateTransaction(newTxn, search[0])
    print("Adding...")
    return addTransaction(newTxn)


def getExpenseTransactionBody(exp: Expense, myshare: ExpenseUser, data: list[str]) -> dict:
    if len(data) > 0 and data[0]:
        dest = data[0]
        data = data[1:]
    else:
        dest = exp.getDescription()

    if len(data) > 0 and data[0]:
        category = data[0]
        data = data[1:]
    else:
        category = os.getenv("FIREFLY_DEFAULT_CATEGORY",
                             exp.getCategory().getName())

    if len(data) > 0 and data[0]:
        description = data[0]
        data = data[1:]
    else:
        description = exp.getDescription()

    # TODO(#1): Handle multiple people paying. Would need to add two transactions on Firefly.
    if len(data) > 0 and data[0]:
        source = data[0]
        data = data[1:]
    else:
        if myshare.getPaidShare() != "0.0":
            source = os.getenv("FIREFLY_DEFAULT_SPEND_ACCOUNT", "Amex")
        else:
            source = os.getenv(
                "FIREFLY_DEFAULT_TRXFR_ACCOUNT", "Chase Checking")

    notes = ""
    if not processText(exp.getDetails()):
        notes = exp.getDetails()

    newTxn = {
        "source_name": source,
        "destination_name": dest,
        "category_name": category,
        "type": "withdrawal",
        "amount": myshare.getOwedShare(),
        "currency_code": exp.getCurrencyCode(),
        "date": getDate(exp.getCreatedAt()).isoformat(),
        "payment_date": getDate(exp.getDate()).isoformat(),
        "description": description,
        "reconciled": False,
        "notes": notes,
        "external_url": getSWUrlForExpense(exp),
    }
    print(
        f"Processing {category} {formatExpense(exp, myshare)} from {source} to {dest}")
    return newTxn


if __name__ == "__main__":
    load_dotenv()
    past_day = time_now - timedelta(days=int(os.getenv("SPLITWISE_DAYS", 1)))

    txns = getTransactionsAfter(past_day)

    sw = Splitwise("", "", api_key=os.getenv("SPLITWISE_TOKEN"))
    currentUser = sw.getCurrentUser()
    print(f"User: {currentUser.getFirstName()}")
    print(f"From: {past_day}")

    for e in getExpensesAfter(sw, past_day, currentUser):
        processExpense(past_day, txns, *e)

    print("Complete")
