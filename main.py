from datetime import datetime, timedelta
from dotenv import load_dotenv
from splitwise import Splitwise, Expense, User, Comment
from splitwise.user import ExpenseUser
from typing import Generator, TypedDict, Union
from functools import wraps
from typing import Union

import os
import requests

from strategies.standard import StandardTransactionStrategy
from strategies.sw_balance import SWBalanceTransactionStrategy
from strategies.base import TransactionStrategy

class Config(TypedDict):
    FIREFLY_URL: str    
    FIREFLY_TOKEN: str
    FIREFLY_DRY_RUN: bool
    FIREFLY_DEFAULT_CATEGORY: str
    FIREFLY_DEFAULT_SPEND_ACCOUNT: str
    FIREFLY_DEFAULT_TRXFR_ACCOUNT: str
    SPLITWISE_TOKEN: str
    SPLITWISE_DAYS: int
    # Debt tracker
    SW_BALANCE_ACCOUNT: str

def load_config() -> Config:
    load_dotenv()
    return {
        "SPLITWISE_TOKEN": os.getenv("SPLITWISE_TOKEN"),
        "FIREFLY_URL": os.getenv("FIREFLY_URL", "http://firefly:8080"),
        "FIREFLY_TOKEN": os.getenv("FIREFLY_TOKEN"),
        "FIREFLY_DEFAULT_CATEGORY": os.getenv("FIREFLY_DEFAULT_CATEGORY"),
        "FIREFLY_DEFAULT_SPEND_ACCOUNT": os.getenv("FIREFLY_DEFAULT_SPEND_ACCOUNT", "Amex"),
        "FIREFLY_DEFAULT_TRXFR_ACCOUNT": os.getenv("FIREFLY_DEFAULT_TRXFR_ACCOUNT", "Chase Checking"),
        "FIREFLY_DRY_RUN": bool(os.getenv("FIREFLY_DRY_RUN", True)),
        "SPLITWISE_DAYS": int(os.getenv("SPLITWISE_DAYS", 1)),
        "FOREIGN_CURRENCY_TOFIX_TAG": os.getenv("FOREIGN_CURRENCY_TOFIX_TAG"),
        "SW_BALANCE_ACCOUNT": os.getenv("SW_BALANCE_ACCOUNT", False),
        "SW_BALANCE_DEFAULT_DESCRIPTION": os.getenv("SW_BALANCE_DEFAULT_DESCRIPTION", "Splitwise balance"),
    }

time_now = datetime.now().astimezone()
conf = load_config()

def formatExpense(exp: Expense, myshare: ExpenseUser) -> str:
    """
    Format expense for logging.
    :param exp: A Splitwise Expense object
    :param myshare: A Splitwise User object
    :return: A formatted string
    """
    return f"Expense {exp.getDescription()} for {exp.getCurrencyCode()} {myshare.getOwedShare()} on {exp.getDate()}"


def getSWUrlForExpense(exp: Expense) -> str:
    """
    Get the Splitwise URL for an expense.
    :param exp: A Splitwise Expense object
    :return: A Splitwise URL
    """
    return f"{Splitwise.SPLITWISE_BASE_URL}expenses/{exp.getId()}"


def getDate(datestr: str) -> datetime:
    """
    Convert ISO 8601 date string to datetime object.
    :param datestr: An ISO 8601 date string
    :return: A datetime object
    """
    return datetime.fromisoformat(datestr.replace("Z", "+00:00"))


def getExpensesAfter(sw: Splitwise, date: datetime, user: User) -> Generator[tuple[Expense, ExpenseUser, list[str]], None, None]:
    """
    Get Splitwise expenses after a date for a user. Yield a tuple of Expense, ExpenseUser corresponding to my share, and a list of strings for Firefly fields.
    If no firefly fields found, print a warning.
    :param sw: A Splitwise object
    :param date: A datetime object, representing the date after which to get expenses
    :param user: A Splitwise User object for whom to get expenses
    :return: A generator of tuples of Expense, ExpenseUser, and a list of strings for Firefly fields. If no data found, return None."""
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
    """
    Process expense test to get data for Firefly fields.
    :param text: A string of text separated by "/" and starting with "Firefly"
    :return: A list of strings. If doesn't start with "Firefly", return empty list. If no separators, return [True].
    """
    if not text:
        return []
    split = text.split("/")
    if split[0].strip().lower() == "firefly":
        return split[1:] or [True]
    return []


def callApi(path, method="POST", params={}, body={}, fail=True):
    """
    Call Firefly API.
    :param path: The API subpath
    :param method: The HTTP method
    :param params: A dictionary of query parameters
    :param body: A dictionary of the request body
    :param fail: Whether to raise an exception on failure
    :return: The response object
    """
    baseUrl = conf["FIREFLY_URL"]
    token = conf["FIREFLY_TOKEN"]
    headers = {
        "Authorization": f"Bearer {token}",
        # https://github.com/firefly-iii/firefly-iii/issues/6829
        "Accept": "application/json",
    }

    if method != "GET" and conf["FIREFLY_DRY_RUN"]:
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
    """
    Search transactions on Firefly.
    :param params: A dictionary of query parameters
    :return: A list of transactions
    """
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
    """
    Get transactions from Firefly after a date.
    :param date: A datetime object
    :return: A dictionary of transactions indexed by external URL
    """
    days: int = (time_now - date).days
    # https://docs.firefly-iii.org/firefly-iii/pages-and-features/search/
    params = {"query": f'date_after:"-{days}d" any_external_url:true'}
    txns = searchTransactions(params)
    return {t["attributes"]["transactions"][0]["external_url"]: t for t in txns}


def updateTransaction(newTxn: dict, oldTxnBody: dict) -> None:
    """
    Update a transaction on Firefly, if needed.
    :param newTxn: A dictionary of the new transaction body
    :param oldTxnBody: A dictionary of the old transaction body
    :return: None
    :raises: Exception if the transaction update fails
    """
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


def addTransaction(newTxn: Union[dict, list[dict]], group_title=None) -> None:
    """
    Add a transaction to Firefly.

    If newTxn is a dictionary, add a single transaction. If newTxn is a list of dictionaries, add a split transaction.

    :param newTxn: A dictionary of the transaction body, or a list of such dictionaries for a split transaction.
    :param group_title: The title of the transaction group. If None, use the description of the first transaction.
    :return: None
    :raises: Exception if the transaction add fails.
    """

    txns: list[dict] = [newTxn] if isinstance(newTxn, dict) else newTxn
    group_title = group_title or txns[0]["description"]
    body = {
        "error_if_duplicate_hash": True,
        "group_title": group_title,
        "transactions": txns
    }
    try:
        callApi("transactions", method="POST", body=body).json()
    except Exception as e:
        print(
            f"Transaction {newTxn['description']} errored, body: {body}, e: {e}")
        raise
    print(f"Added Transaction: {group_title}")


def processExpense(past_day: datetime, txns: dict[dict], exp: Expense, *args) -> None:
    """
    Process a Splitwise expense. Update or add a transaction on Firefly.

    :param past_day: A datetime object. Expenses before this date are ignored.
    :param txns: A dictionary of transactions indexed by Splitwise external URL.
    :param exp: A Splitwise Expense object.
    :param args: A list of strings for Firefly fields.
    :return: None
    """

    strategy = get_transaction_strategy()
    new_txns: list = strategy.create_transactions(exp, *args)
    for idx, new_txn in enumerate(new_txns):
        external_url = getSWUrlForExpense(exp)
        if idx > 0:
            external_url += f"-balance_transfer-{idx}"
        if isinstance(new_txn, dict):
            new_txn["external_url"] = external_url
        else:
            for split in new_txn:
                split["external_url"] = external_url
        
        if oldTxnBody := txns.get(external_url):
            print(f"Updating transaction {idx + 1}...")
            updateTransaction(new_txn, oldTxnBody)
            continue
        if getDate(exp.getCreatedAt()) < past_day or getDate(exp.getDate()) < past_day:
            if search := searchTransactions({"query": f'external_url_is:"{external_url}"'}):
                print(f"Updating old transaction {idx + 1}...")
                # TODO(#1): This would have 2 results for same splitwise expense
                updateTransaction(new_txn, search[0])
                continue
        print(f"Adding transaction {idx + 1}...")
        addTransaction(new_txn)


def getExpenseTransactionBody(exp: Expense, myshare: ExpenseUser, data: list[str]) -> dict:
    """
    Get the transaction body for a Splitwise expense.
    :param exp: A Splitwise Expense object
    :param myshare: A Splitwise User object, representing the current user
    :param data: A list of strings for Firefly fields. [dest, category, description, source]. If empty, use default values.
    """
    if len(data) > 0 and data[0]:
        dest = data[0]
    else:
        dest = exp.getDescription()
    data = data[1:]

    if len(data) > 0 and data[0]:
        category = data[0]
    else:
        category = conf["FIREFLY_DEFAULT_CATEGORY"] or exp.getCategory().getName()
    data = data[1:]

    if len(data) > 0 and data[0]:
        description = data[0]
    else:
        description = exp.getDescription()
    data = data[1:]

    # TODO(#1): Handle multiple people paying. Would need to add two transactions on Firefly.
    if len(data) > 0 and data[0]:
        source = data[0]
    else:
        if myshare.getPaidShare() != "0.0":
            source = conf["FIREFLY_DEFAULT_SPEND_ACCOUNT"]
        else:
            source = conf["FIREFLY_DEFAULT_TRXFR_ACCOUNT"]
    data = data[1:]

    notes = ""
    if not processText(exp.getDetails()):
        notes = exp.getDetails()

    newTxn = {
        "source_name": source,
        "destination_name": dest,
        "category_name": category,
        "type": "withdrawal",
        "date": getDate(exp.getCreatedAt()).isoformat(),
        "payment_date": getDate(exp.getDate()).isoformat(),
        "description": description,
        "reconciled": False,
        "notes": notes,
        "external_url": getSWUrlForExpense(exp),
        "tags": [],
    }
    newTxn = applyAmountToTransaction(newTxn, exp, myshare.getOwedShare())
    print(
        f"Processing {category} {formatExpense(exp, myshare)} from {source} to {dest}")
    return newTxn

def applyAmountToTransaction(transaction: dict, exp: Expense, amount: float) -> dict:
    """Apply the amount to the transaction based on the currency of the account.
    
    :param transaction: The transaction dictionary
    :param exp: The Splitwise expense
    :param amount: The amount to apply
    :return: The updated transaction dictionary
    """
    amount = str(float(amount))

    if transaction['type'] in ["withdrawal", "transfer"]:
        account_to_check = transaction['source_name']
    elif transaction['type'] == "deposit":
        account_to_check = transaction['destination_name']
    else:
        raise NotImplementedError(f"Transaction type {transaction['type']} not implemented.")
    if getAccountCurrencyCode(account_to_check) == exp.getCurrencyCode():
        transaction["amount"] = amount
    else:
        transaction["foreign_currency_code"] = exp.getCurrencyCode()
        transaction["foreign_amount"] = amount
        transaction["amount"] = 0.1
        transaction["tags"].append(conf["FOREIGN_CURRENCY_TOFIX_TAG"])
    return transaction

def get_transaction_strategy() -> TransactionStrategy:
    if conf["SW_BALANCE_ACCOUNT"]:
        return SWBalanceTransactionStrategy(getExpenseTransactionBody, conf["SW_BALANCE_ACCOUNT"], applyAmountToTransaction)
    else:
        return StandardTransactionStrategy(getExpenseTransactionBody)

def getAccounts(account_type: str="asset") -> list:
    """Get accounts from Firefly.

    :param account_type: The type of account
    :return: A list of accounts
    """
    return callApi("accounts/", method="GET", params={"type": account_type}).json()['data']

def cache_account_currency(function):
    account_name_currency = dict(
        map(
            lambda x: (x["attributes"]["name"], x["attributes"]["currency_code"]),
            getAccounts("asset"),
        )
    )

    @wraps(function)
    def cached(account_name: str) -> str:
        try:
            return account_name_currency[account_name]
        except KeyError:
            raise ValueError(f"Account {account_name} not found in asset accounts.")

    return cached

@cache_account_currency
def getAccountCurrencyCode(account_name: str) -> str:
    """Get the currency of an account on Firefly.

    :param account: The account name
    :return: The currency code
    :raises: ValueError if the account is not found
    """
    raise Exception("Will not be called")


if __name__ == "__main__":
    """
    Main function. Get Splitwise expenses after a date and process them - update or add transactions on Firefly.
    """
    past_day = time_now - timedelta(days=conf["SPLITWISE_DAYS"])

    txns = getTransactionsAfter(past_day)

    sw = Splitwise("", "", api_key=conf["SPLITWISE_TOKEN"])
    currentUser = sw.getCurrentUser()
    print(f"User: {currentUser.getFirstName()}")
    print(f"From: {past_day}")

    for e in getExpensesAfter(sw, past_day, currentUser):
        processExpense(past_day, txns, *e)

    print("Complete")
