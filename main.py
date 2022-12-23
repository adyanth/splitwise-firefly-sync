from datetime import datetime, timedelta
from dotenv import load_dotenv
from splitwise import Splitwise

import os

def getExpensesAfter(date, user):
    expenses = sw.getExpenses(dated_after=date.isoformat())
    for exp in expenses:
        # Ignore payments
        if exp.getPayment():
            continue

        # Get my share by userId
        myshare = filter(lambda x: x.getId() == user.getId(), exp.getUsers()).__next__()
        # Ignore transactions where I do not owe anything
        if myshare.getOwedShare() == "0.0":
            continue
        
        yield exp, myshare

def printExp(exp, myshare):
    print(exp.getDescription())
    print(exp.getCurrencyCode())
    print(exp.getDate())
    print(exp.getCreatedAt())
    print(exp.getCategory().getName())
    print(myshare.getOwedShare())
    print()

if __name__ == "__main__":
    past_day = datetime.now() - timedelta(days=1)
    load_dotenv()
    sw = Splitwise("", "", api_key=os.getenv("TOKEN"))
    currentUser = sw.getCurrentUser()
    print(currentUser.getFirstName())
    for e in getExpensesAfter(past_day, currentUser):
        printExp(*e)
