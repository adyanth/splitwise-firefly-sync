from .base import TransactionStrategy
from splitwise import Expense
from splitwise.user import ExpenseUser

class SWBalanceTransactionStrategy(TransactionStrategy):
    def __init__(self, get_expense_transaction_body, sw_balance_account, apply_transaction_amount) -> None:
        self._get_expense_transaction_body = get_expense_transaction_body
        self._sw_balance_account = sw_balance_account
        self._apply_transaction_amount = apply_transaction_amount

    def create_transactions(self, exp: Expense, myshare: ExpenseUser, data: list[str]) -> list[dict]:
        txns = {}
        paid_txn = self._get_expense_transaction_body(exp, myshare, data)
        paid_txn = self._apply_transaction_amount(paid_txn, exp, myshare.getPaidShare())
        if float(paid_txn['amount']) != 0: # I paid; payment txn needed
            txns['paid'] = paid_txn

        balance_txn = paid_txn.copy()
        balance = float(myshare.getNetBalance())
        if balance != 0: # I owe or am owed; balance txn needed
            txns['balance'] = balance_txn
            if balance > 0: # I am owed; difference credited to balance account
                balance_txn['source_name'] = self._sw_balance_account + " balancer"
                balance_txn['destination_name'] = self._sw_balance_account
                balance_txn['type'] = 'deposit'
                balance_txn['description'] = f"Balance transfer for: {paid_txn['description']}"
                balance_txn = self._apply_transaction_amount(balance_txn, exp, balance)
            else: # I owe; difference debited from balance account
                balance_txn['source_name'] = self._sw_balance_account
                balance_txn['destination_name'] = paid_txn['destination_name']
                balance_txn['type'] = "withdrawal"
                balance_txn['description'] = f"Balance transfer for: {paid_txn['description']}"
                balance_txn = self._apply_transaction_amount(balance_txn, exp, -balance)
        return list(txns.values())