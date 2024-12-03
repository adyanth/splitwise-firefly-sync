from .base import TransactionStrategy
from splitwise import Expense
from splitwise.user import ExpenseUser

class StandardTransactionStrategy(TransactionStrategy):
    def __init__(self, get_expense_transaction_body) -> None:
        """
        Initialize the StandardTransactionStrategy with the function to get the transaction body.
        
        :param get_expense_transaction_body: Function to get the transaction body for the expense. Must take the expense, user's share, and additional data as arguments.
        """

        self._get_expense_transaction_body = get_expense_transaction_body

    def create_transactions(self, exp: Expense, myshare: ExpenseUser, data: list[str]) -> list[dict]:
        """
        Create a transaction for the given expense and user's share of the expense.
        
        Create a single transaction for the expense using the provided function to get the transaction from the expense, user's share, and additional data.

        :param exp: Expense to create transactions from
        :param myshare: ExpenseUser object representing the user's share in the expense
        :param data: List of strings containing additional data for the transaction
        """
        
        return [self._get_expense_transaction_body(exp, myshare, data)]