from .base import TransactionStrategy
from splitwise import Expense
from splitwise.user import ExpenseUser

class SWBalanceTransactionStrategy(TransactionStrategy):
    def __init__(self, get_expense_transaction_body, sw_balance_account, apply_transaction_amount) -> None:
        """
        Initialize the SWBalanceTransactionStrategy.

        :param get_expense_transaction_body: Function to get the transaction body for the expense. Must take the expense, user's share, and additional data as arguments.
        :param sw_balance_account: Name of the Splitwise balance account for the user.
        :param apply_transaction_amount: Function to apply the transaction amount to the transaction body. Must take the transaction body, expense, and amount as arguments.
        """

        self._get_expense_transaction_body = get_expense_transaction_body
        self._sw_balance_account = sw_balance_account
        self._apply_transaction_amount = apply_transaction_amount

    def create_transactions(self, exp: Expense, myshare: ExpenseUser, data: list[str]) -> list[dict]:
        """
        Create transactions for the given expense and user's share of the expense.
        
        Create transactions for the expense using the provided function to get the transaction from the expense, user's share, and additional data.
        If the user paid for the expense, create a payment withdrawal transaction and a cover deposit transaction to the Splitwise balance. Split the payment transaction to the owed amount and the cover amount.
        If the user owes money for the expense, create a balance transfer withdrawal transaction from the Splitwise balance account.

        :param exp: Expense to create transactions from
        :param myshare: ExpenseUser object representing the user's share in the expense
        :param data: List of strings containing additional data for the transaction
        """
        
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

        if float(myshare.getPaidShare()) != 0: # I paid; payment txn needed
            txns['paid'] = [owed_txn, cover_txn]

        if balance != 0: # I owe or am owed; balance txn needed
            balance_txn = owed_txn.copy()
            balance_txn.update({
                'description': f"Balance transfer for: {description}",
                'type': 'deposit' if balance > 0 else 'withdrawal',
                'category_name': ''
            })

            if balance > 0: # I am owed; difference credited to balance account
                balance_txn.update({
                    'source_name': self._sw_balance_account + " balancer",
                    'destination_name': self._sw_balance_account
                })
            else: # I owe; difference debited from balance account
                balance_txn.update({
                    'source_name': self._sw_balance_account,
                    'destination_name': owed_txn['destination_name']
                })
                balance = -balance
            balance_txn = self._apply_transaction_amount(balance_txn, exp, balance)
            txns['balance'] = balance_txn
        return list(txns.values())