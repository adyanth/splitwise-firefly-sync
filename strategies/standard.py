from .base import TransactionStrategy
from splitwise import Expense
from splitwise.user import ExpenseUser

class StandardTransactionStrategy(TransactionStrategy):
    def __init__(self, get_expense_transaction_body) -> None:
        self._get_expense_transaction_body = get_expense_transaction_body

    def create_transactions(self, exp: Expense, myshare: ExpenseUser, data: list[str]) -> list[dict]:
        return [self._get_expense_transaction_body(exp, myshare, data)]