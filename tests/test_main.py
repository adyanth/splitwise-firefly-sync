import pytest
from datetime import datetime, timedelta
from splitwise import Splitwise, Expense, User, Comment
from splitwise.user import ExpenseUser
from unittest.mock import MagicMock, patch

from main import (
    formatExpense, getSWUrlForExpense, getDate, getExpensesAfter,
    processText, callApi, searchTransactions, getTransactionsAfter,
    processExpense, getExpenseTransactionBody
)

@pytest.fixture
def mock_splitwise():
    mock_sw = MagicMock(spec=Splitwise)
    mock_sw.getExpenses.return_value = []
    return mock_sw

@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.getId.return_value = "12345"
    user.getFirstName.return_value = "Test"
    return user

@pytest.fixture
def mock_expense():
    expense = MagicMock(spec=Expense)
    expense.getId.return_value = "67890"
    expense.getDescription.return_value = "Test Expense"
    expense.getCurrencyCode.return_value = "USD"
    expense.getDate.return_value = "2023-09-10T12:00:00Z"
    expense.getCreatedAt.return_value = "2023-09-10T12:00:00Z"
    expense.getDetails.return_value = "Test details"
    expense.getDeletedAt.return_value = None
    expense.getPayment.return_value = False
    expense.getUpdatedBy.return_value = None
    expense.getCreatedBy.return_value = MagicMock(getId=MagicMock(return_value="12345"))
    return expense

@pytest.fixture
def mock_expense_user():
    expense_user = MagicMock(spec=ExpenseUser)
    expense_user.getId.return_value = "12345"
    expense_user.getOwedShare.return_value = "10.00"
    expense_user.getPaidShare.return_value = "10.00"
    return expense_user

def test_formatExpense(mock_expense, mock_expense_user):
    result = formatExpense(mock_expense, mock_expense_user)
    assert "Test Expense" in result
    assert "USD" in result
    assert "10.00" in result
    assert "2023-09-10" in result
    print(result)
    assert result == "Expense Test Expense for USD 10.00 on 2023-09-10T12:00:00Z"

def test_getSWUrlForExpense(mock_expense):
    result = getSWUrlForExpense(mock_expense)
    assert result == "https://secure.splitwise.com/expenses/67890"

def test_getDate():
    date_str = "2023-09-10T12:00:00Z"
    result = getDate(date_str)
    assert isinstance(result, datetime)
    assert result.year == 2023
    assert result.month == 9
    assert result.day == 10

@pytest.mark.parametrize("text,expected", [
    ("firefly/category/description", ["category", "description"]),
    ("firefly", [True]),
    ("normal text", []),
])
def test_processText(text, expected):
    assert processText(text) == expected

@patch('requests.request')
def test_callApi(mock_request):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": "test"}
    mock_request.return_value = mock_response

    result = callApi("test_path", method="GET")
    assert result.json() == {"data": "test"}
    mock_request.assert_called_once()

@patch('main.callApi')
def test_searchTransactions(mock_callApi):
    # Simulate pagination
    mock_responses = [
        MagicMock(json=lambda: {"data": [{"id": "1"}, {"id": "2"}]}),
        MagicMock(json=lambda: {"data": [{"id": "3"}]}),
        MagicMock(json=lambda: {"data": []})  # Empty response to end pagination
    ]
    mock_callApi.side_effect = mock_responses

    result = list(searchTransactions({"query": "test"}))
    assert len(result) == 3
    assert [r["id"] for r in result] == ["1", "2", "3"]
    assert mock_callApi.call_count == 3

@patch('main.searchTransactions')
def test_getTransactionsAfter(mock_searchTransactions):
    mock_searchTransactions.return_value = [
        {"attributes": {"transactions": [{"external_url": "url1"}]}},
        {"attributes": {"transactions": [{"external_url": "url2"}]}}
    ]

    result = getTransactionsAfter(datetime.now() - timedelta(days=1))
    assert len(result) == 2
    assert "url1" in result
    assert "url2" in result

def test_getExpenseTransactionBody(mock_expense, mock_expense_user):
    result = getExpenseTransactionBody(mock_expense, mock_expense_user, ["Dest", "Category", "Desc"])
    assert result["source_name"] == "Amex"
    assert result["destination_name"] == "Dest"
    assert result["category_name"] == "Category"
    assert result["amount"] == "10.00"
    assert result["currency_code"] == "USD"
    assert result["description"] == "Desc"

@patch('main.callApi')
@patch('main.updateTransaction')
@patch('main.addTransaction')
@patch('main.searchTransactions')
def test_processExpense(mock_searchTransactions, mock_addTransaction, mock_updateTransaction, mock_callApi, mock_expense, mock_expense_user):
    # Mock callApi to prevent actual API calls
    mock_callApi.return_value = MagicMock(json=lambda: {})

    # Mock searchTransactions to return an empty list
    mock_searchTransactions.return_value = []

    # Test updating an existing transaction
    txns = {getSWUrlForExpense(mock_expense): {"id": "123", "attributes": {}}}
    processExpense(datetime.now().astimezone() - timedelta(days=1), txns, mock_expense, mock_expense_user, [])
    mock_updateTransaction.assert_called_once()
    mock_addTransaction.assert_not_called()
    mock_searchTransactions.assert_not_called()

    # Reset mocks
    mock_updateTransaction.reset_mock()
    mock_addTransaction.reset_mock()
    mock_searchTransactions.reset_mock()

    # Test adding a new transaction
    txns = {}
    processExpense(datetime.now().astimezone() - timedelta(days=1), txns, mock_expense, mock_expense_user, [])
    mock_addTransaction.assert_called_once()
    mock_updateTransaction.assert_not_called()
    mock_searchTransactions.assert_called_once()

@pytest.fixture
def mock_splitwise():
    return MagicMock()

def test_getExpensesAfter(mock_splitwise, mock_user):
    # Setup
    mock_expense1 = MagicMock(spec=Expense)
    mock_expense1.getId.return_value = "1"
    mock_expense1.getDescription.return_value = "Expense 1"
    mock_expense1.getDeletedAt.return_value = None
    mock_expense1.getPayment.return_value = False
    mock_expense1.getUpdatedAt.return_value = "2023-09-10T12:00:00Z"
    mock_expense1.getCreatedAt.return_value = "2023-09-10T12:00:00Z"
    mock_expense1.getDate.return_value = "2023-09-10"
    mock_expense1.getDetails.return_value = "firefly/Category1/Description1"
    mock_expense1.getUpdatedBy.return_value = None
    mock_expense1.getCreatedBy.return_value = MagicMock(getId=MagicMock(return_value="12345"))

    mock_expense2 = MagicMock(spec=Expense)
    mock_expense2.getId.return_value = "2"
    mock_expense2.getDescription.return_value = "Expense 2"
    mock_expense2.getDeletedAt.return_value = None
    mock_expense2.getPayment.return_value = False
    mock_expense2.getUpdatedAt.return_value = "2023-09-11T12:00:00Z"
    mock_expense2.getCreatedAt.return_value = "2023-09-11T12:00:00Z"
    mock_expense2.getDate.return_value = "2023-09-11"
    mock_expense2.getDetails.return_value = "Regular expense details"
    mock_expense2.getUpdatedBy.return_value = None
    mock_expense2.getCreatedBy.return_value = MagicMock(getId=MagicMock(return_value="12345"))

    mock_expense3 = MagicMock(spec=Expense)
    mock_expense3.getId.return_value = "3"
    mock_expense3.getDescription.return_value = "Expense 3"
    mock_expense3.getDeletedAt.return_value = None
    mock_expense3.getPayment.return_value = False
    mock_expense3.getUpdatedAt.return_value = "2023-09-12T12:00:00Z"
    mock_expense3.getCreatedAt.return_value = "2023-09-12T12:00:00Z"
    mock_expense3.getDate.return_value = "2023-09-12"
    mock_expense3.getDetails.return_value = "Another regular expense"
    mock_expense3.getUpdatedBy.return_value = None
    mock_expense3.getCreatedBy.return_value = MagicMock(getId=MagicMock(return_value="12345"))

    mock_expense_user = MagicMock(spec=ExpenseUser)
    mock_expense_user.getId.return_value = "12345"
    mock_expense_user.getOwedShare.return_value = "10.00"

    for expense in [mock_expense1, mock_expense2, mock_expense3]:
        expense.getUsers.return_value = [mock_expense_user]

    # Mock comments
    mock_comment2 = MagicMock(spec=Comment)
    mock_comment2.getCommentedUser.return_value = MagicMock(getId=MagicMock(return_value="12345"))
    mock_comment2.getContent.return_value = "firefly/Category2/Description2"

    mock_splitwise.getComments.side_effect = [
        [],  # For expense1 (already has Firefly data in details)
        [mock_comment2],  # For expense2
        []  # For expense3
    ]

    mock_splitwise.getExpenses.side_effect = [
        [mock_expense1, mock_expense2, mock_expense3],
        []  # Empty list to end pagination
    ]

    # Call the function
    date = datetime.now() - timedelta(days=7)
    result = list(getExpensesAfter(mock_splitwise, date, mock_user))

    # Assertions
    assert len(result) == 2, "Should only return 2 expenses with Firefly data"
    
    # Check first expense (with Firefly data in details)
    assert result[0][0] == mock_expense1
    assert result[0][1] == mock_expense_user
    assert result[0][2] == ["Category1", "Description1"]

    # Check second expense (with Firefly data in comment)
    assert result[1][0] == mock_expense2
    assert result[1][1] == mock_expense_user
    assert result[1][2] == ["Category2", "Description2"]

    # Check that getExpenses was called with correct parameters
    mock_splitwise.getExpenses.assert_called_with(
        updated_after=date.isoformat(),
        offset=20,  # This should match the 'limit' in your getExpensesAfter function
        limit=20
    )

    # Ensure getComments was called for each expense
    assert mock_splitwise.getComments.call_count == 3

    # Verify that the third expense (without Firefly data) was not returned
    assert all(r[0].getId() != "3" for r in result), "Expense without Firefly data should not be returned"

if __name__ == "__main__":
    pytest.main()