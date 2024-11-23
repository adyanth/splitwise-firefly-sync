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
        owed_txn = self._get_expense_transaction_body(exp, myshare, data)
        description = owed_txn['description']
        balance = float(myshare.getNetBalance())
        
        # Create cover transaction
        cover_txn = self._apply_transaction_amount(owed_txn.copy(), exp, balance)
        cover_txn.update({
            'description': f"Cover for: {description}",
            'category_name': ''
        })
        
        if float(owed_txn['amount']) != 0: # I paid; payment txn needed
            txns['paid'] = [owed_txn, cover_txn]

        balance_txn = owed_txn.copy()
        if balance != 0: # I owe or am owed; balance txn needed
            txns['balance'] = balance_txn
            if balance > 0: # I am owed; difference credited to balance account
                balance_txn['source_name'] = self._sw_balance_account + " balancer"
                balance_txn['destination_name'] = self._sw_balance_account
                balance_txn['type'] = 'deposit'
                balance_txn['description'] = f"Balance transfer for: {description}"
                balance_txn = self._apply_transaction_amount(balance_txn, exp, balance)
            else: # I owe; difference debited from balance account
                balance_txn['source_name'] = self._sw_balance_account
                balance_txn['destination_name'] = owed_txn['destination_name']
                balance_txn['type'] = "withdrawal"
                balance_txn['description'] = f"Balance transfer for: {description}"
                balance_txn = self._apply_transaction_amount(balance_txn, exp, -balance)
        return list(txns.values())