import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from strategies.standard import StandardTransactionStrategy
from strategies.sw_balance import SWBalanceTransactionStrategy
from splitwise import Expense
from splitwise.user import ExpenseUser

# Mock objects
mock_expense = Mock(spec=Expense)
mock_expense.getId.return_value = "123"
mock_expense.getDescription.return_value = "Test Expense"
mock_expense.getCurrencyCode.return_value = "USD"
mock_expense.getDate.return_value = "2023-05-01"
mock_expense.getCreatedAt.return_value = "2023-05-01T12:00:00Z"

mock_user = Mock(spec=ExpenseUser)
mock_user.getId.return_value = "456"
mock_user.getOwedShare.return_value = "50.00"
mock_user.getPaidShare.return_value = "100.00"

# Mock getExpenseTransactionBody function
def mock_get_expense_transaction_body(exp, myshare, data, use_paid_amount=False):
    amount = myshare.getPaidShare() if use_paid_amount else myshare.getOwedShare()
    return {
        "amount": amount,
        "description": exp.getDescription(),
        "date": exp.getDate(),
        "source_name": "Test Source",
        "destination_name": "Test Destination",
        "category_name": "Test Category",
        "type": "withdrawal",
    }

# Tests for StandardTransactionStrategy
def test_standard_strategy():
    strategy = StandardTransactionStrategy(mock_get_expense_transaction_body)
    transactions = strategy.create_transactions(mock_expense, mock_user, [])
    
    assert len(transactions) == 1
    assert transactions[0]["amount"] == "50.00"
    assert transactions[0]["description"] == "Test Expense"

# Tests for SWBalanceTransactionStrategy
def test_sw_balance_strategy():
    strategy = SWBalanceTransactionStrategy(mock_get_expense_transaction_body, "Splitwise Balance")
    transactions = strategy.create_transactions(mock_expense, mock_user, [])
    
    assert len(transactions) == 2
    assert transactions[0]["amount"] == "100.00"
    assert transactions[0]["description"] == "Test Expense"
    assert transactions[1]["amount"] == "50.00"
    assert transactions[1]["type"] == "transfer"
    assert transactions[1]["destination_name"] == "Splitwise Balance"

# Test for processExpense function
@patch('main.get_transaction_strategy')
@patch('main.updateTransaction')
@patch('main.addTransaction')
@patch('main.searchTransactions')
@patch('main.getSWUrlForExpense')
def test_process_expense(mock_get_url, mock_search, mock_add, mock_update, mock_get_strategy):
    from main import processExpense, Config
    
    # Mock configuration
    mock_config = Mock(spec=Config)
    mock_config.USE_SW_BALANCE_ACCOUNT = True
    
    # Set up mock strategy
    mock_strategy = Mock()
    mock_strategy.create_transactions.return_value = [
        {"amount": "100.00", "description": "Test Expense"},
        {"amount": "50.00", "description": "Balance transfer for: Test Expense", "type": "transfer"}
    ]
    mock_get_strategy.return_value = mock_strategy
    
    # Set up other mocks
    mock_get_url.return_value = "http://example.com/expense/123"
    mock_search.return_value = []
    
    # Call processExpense
    processExpense(datetime.now(), {}, mock_expense, mock_user, [])
    
    # Assertions
    assert mock_strategy.create_transactions.called
    assert mock_add.call_count == 2
    assert mock_update.call_count == 0
    mock_add.assert_any_call({"amount": "100.00", "description": "Test Expense", "external_url": "http://example.com/expense/123"})
    mock_add.assert_any_call({"amount": "50.00", "description": "Balance transfer for: Test Expense", "type": "transfer", "external_url": "http://example.com/expense/123-balance-transfer-1"})

# Test for get_transaction_strategy function
@patch('requests.request')
def test_get_transaction_strategy(mock_request):
    mock_request.return_value.json.return_value = {'data': []}
    from main import get_transaction_strategy, Config
    
    # Test with USE_SW_BALANCE_ACCOUNT = False
    mock_config = Mock(spec=Config)
    mock_config.USE_SW_BALANCE_ACCOUNT = False
    
    with patch('main.conf', mock_config):
        strategy = get_transaction_strategy()
        assert isinstance(strategy, StandardTransactionStrategy)
    
    # Test with USE_SW_BALANCE_ACCOUNT = True
    mock_config.USE_SW_BALANCE_ACCOUNT = True
    mock_config.SW_BALANCE_ACCOUNT = "Splitwise Balance"
    
    with patch('main.conf', mock_config):
        strategy = get_transaction_strategy()
        assert isinstance(strategy, SWBalanceTransactionStrategy)