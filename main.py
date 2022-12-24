from datetime import datetime, timedelta
from dotenv import load_dotenv
from splitwise import Splitwise, Expense, User, Comment
from splitwise.user import ExpenseUser
from typing import Generator

import os

def getExpensesAfter(sw: Splitwise, date: datetime, user: User) -> Generator[tuple[Expense, ExpenseUser, list[str]], None, None]:
    expenses: list[Expense] = sw.getExpenses(dated_after=date.isoformat())
    for exp in expenses:
        # Ignore payments
        if exp.getPayment():
            continue

        # Get my share by userId
        myshare: ExpenseUser = filter(lambda x: x.getId() == user.getId(), exp.getUsers()).__next__()
        # Ignore transactions where I do not owe anything
        if myshare.getOwedShare() == "0.0":
            continue

        # Get data, latest comment > old comment > notes
        data: str = None
        if details:=processText(exp.getDetails()):
            data = details
        c: Comment
        for c in sw.getComments(exp.getId()):
            if c.getCommentedUser().getId() != user.getId():
                pass
            if text:=processText(c.getContent()):
                data = text

        yield exp, myshare, data

def processText(text: str) -> list[str]:
    split = text.split("/")
    if split[0].lower() == "firefly":
        return split[1:]
    return []

def processExp(exp: Expense, myshare:ExpenseUser, data: list[str]):
    print(exp.getDescription())
    print(exp.getCurrencyCode())
    print(exp.getDate())
    print(exp.getCreatedAt())
    # print(exp.getCategory().getName())
    print(myshare.getOwedShare())
    print(data)
    print()

if __name__ == "__main__":
    past_day = datetime.now() - timedelta(days=1)
    load_dotenv()
    sw = Splitwise("", "", api_key=os.getenv("SPLITWISE_TOKEN"))
    currentUser = sw.getCurrentUser()
    print(currentUser.getFirstName())
    for e in getExpensesAfter(sw, past_day, currentUser):
        processExp(*e)
