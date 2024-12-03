from abc import ABC, abstractmethod
from splitwise import Expense
from splitwise.user import ExpenseUser

class TransactionStrategy(ABC):
    @abstractmethod
    def create_transactions(self, exp: Expense, myshare: ExpenseUser, data: list[str]) -> list:
        pass