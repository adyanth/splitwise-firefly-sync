from datetime import datetime, timedelta
from dotenv import load_dotenv
from splitwise import Splitwise, Expense, User, Comment
from splitwise.user import ExpenseUser
from typing import Generator

import os
import requests


def formatExpense(exp: Expense, myshare: ExpenseUser):
    return f"Expense {exp.getDescription()} for {exp.getCurrencyCode()} {myshare.getOwedShare()} on {exp.getDate()}"


def getExpensesAfter(sw: Splitwise, date: datetime, user: User) -> Generator[tuple[Expense, ExpenseUser, list[str]], None, None]:
    offset = 0
    limit = 20
    expenses: list[Expense] = []
    while True:
        exp = sw.getExpenses(dated_after=date.isoformat(), offset=offset, limit=limit)
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
    headers = {"Authorization": f"Bearer {token}"}
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


def addTransaction(txn: dict[str, str]):
    body = {
        "error_if_duplicate_hash": True,
        "group_title": txn["description"],
        "transactions": [txn]
    }
    try:
        callApi("transactions", method="POST", body=body).json()
    except Exception as e:
        print(f"Transaction {txn['description']} errored, body: {body}")
        raise
    print(f"Added Transaction: {txn['description']}")


def processExp(exp: Expense, myshare: ExpenseUser, data: list[str]):
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

    # TODO: Handle multiple people paying. Would need to add two transactions on Firefly.
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
        "date": exp.getCreatedAt(),
        "payment_date": exp.getDate(),
        "description": exp.getDescription(),
        "reconciled": False,
        "notes": notes,
        "external_url": f"{Splitwise.SPLITWISE_BASE_URL}expenses/{exp.getId()}",
    }
    print(
        f"Syncing {category} {formatExpense(exp, myshare)} from {source} to {dest}")
    if os.getenv("FIREFLY_DRY_RUN"):
        return
    addTransaction(newTxn)


if __name__ == "__main__":
    load_dotenv()
    past_day = datetime.now() - timedelta(days=int(os.getenv("DAYS", 1)))
    sw = Splitwise("", "", api_key=os.getenv("SPLITWISE_TOKEN"))
    currentUser = sw.getCurrentUser()
    print(f"User: {currentUser.getFirstName()}")
    print(f"From: {past_day}")
    for e in getExpensesAfter(sw, past_day, currentUser):
        processExp(*e)
    print("Complete")
