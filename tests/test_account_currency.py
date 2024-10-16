import pytest
from unittest.mock import patch, Mock
import importlib
import requests

# Mock the entire requests library
@pytest.fixture(autouse=True)
def mock_requests():
    with patch('requests.request') as mock:
        mock.return_value.json.return_value = {'data': []}
        yield mock

# Reload the main module in each test to ensure a clean slate
def reload_main():
    with patch('main.callApi') as mock_call_api:
        mock_call_api.return_value.json.return_value = {'data': []}
        import main
        importlib.reload(main)
        return main

def test_getAccounts(mock_requests):
    mock_requests.return_value.json.return_value = {
        'data': [
            {'attributes': {'name': 'Account1', 'currency_code': 'USD'}},
            {'attributes': {'name': 'Account2', 'currency_code': 'EUR'}}
        ]
    }
    
    main = reload_main()
    result = main.getAccounts()
    
    assert len(result) == 2
    assert result[0]['attributes']['name'] == 'Account1'
    assert result[1]['attributes']['currency_code'] == 'EUR'

def test_getAccountCurrencyCode(mock_requests):
    mock_requests.return_value.json.return_value = {
        'data': [
            {'attributes': {'name': 'Account1', 'currency_code': 'USD'}},
            {'attributes': {'name': 'Account2', 'currency_code': 'EUR'}}
        ]
    }
    
    main = reload_main()
    
    assert main.getAccountCurrencyCode('Account1') == 'USD'
    assert main.getAccountCurrencyCode('Account2') == 'EUR'
    
    with pytest.raises(ValueError):
        main.getAccountCurrencyCode('NonexistentAccount')

def test_cache_behavior(mock_requests):
    call_count = 0
    def mock_request(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_response = Mock()
        mock_response.json.return_value = {
            'data': [
                {'attributes': {'name': 'Account1', 'currency_code': 'USD'}},
                {'attributes': {'name': 'Account2', 'currency_code': 'EUR'}}
            ]
        }
        return mock_response
    
    mock_requests.side_effect = mock_request
    
    main = reload_main()
    
    assert main.getAccountCurrencyCode('Account1') == 'USD'
    assert main.getAccountCurrencyCode('Account2') == 'EUR'
    assert main.getAccountCurrencyCode('Account1') == 'USD'
    
    # The request should only be made once due to caching
    assert call_count == 1

if __name__ == "__main__":
    pytest.main([__file__])