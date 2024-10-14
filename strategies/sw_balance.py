from .base import TransactionStrategy
from splitwise import Expense
from splitwise.user import ExpenseUser

class SWBalanceTransactionStrategy(TransactionStrategy):
    def __init__(self, get_expense_transaction_body, sw_balance_account) -> None:
        self._get_expense_transaction_body = get_expense_transaction_body
        self._sw_balance_account = sw_balance_account

    def create_transactions(self, exp: Expense, myshare: ExpenseUser, data: list[str]) -> list[dict]:
        paid_txn = self._get_expense_transaction_body(exp, myshare, data, use_paid_amount=True)

        balance_txn = paid_txn.copy()
        balance = myshare.getNetBalance()
        if balance > 0: # I payed something and people owe me money; extra money goes to balance account
            balance_txn['source_name'] = paid_txn['source_name']
            balance_txn['destination_name'] = self._sw_balance_account
            balance_txn['amount'] = balance
            balance_txn['type'] = 'transfer'
            balance_txn['description'] = f"Balance transfer for: {paid_txn['description']}"
        else: # I payed less than what I owe; I payed the remaining amount from balance account
            balance_txn['source_name'] = self._sw_balance_account
            balance_txn['destination_name'] = paid_txn['destination_name']
            balance_txn['amount'] = -balance
            balance_txn['type'] = "withdrawal"
            balance_txn['description'] = f"Balance transfer for: {paid_txn['description']}"
        
        return [paid_txn, balance_txn]