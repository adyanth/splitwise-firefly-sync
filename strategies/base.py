from abc import ABC, abstractmethod
from splitwise import Expense
from splitwise.user import ExpenseUser

class TransactionStrategy(ABC):
    @abstractmethod
    def create_transactions(self, exp: Expense, myshare: ExpenseUser, data: list[str]) -> list:
        """
        Create transactions for the given expense and user's share of the expense.

        :param exp: Expense to create transactions from
        :param myshare: ExpenseUser object representing the user's share in the expense
        :param data: List of strings containing additional data for the transaction
        """
        pass