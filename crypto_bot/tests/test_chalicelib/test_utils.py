import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch
from chalicelib.utils import DynamoDBManager, get_trade_precedence

@pytest.fixture
def mock_boto3_resource():
    with patch('boto3.resource') as mock_resource:
        yield mock_resource

@pytest.fixture
def dynamo_manager(mock_boto3_resource):
    return DynamoDBManager()

def test_get_table(mock_boto3_resource, dynamo_manager):
    # Mock the DynamoDB client
    mock_client = MagicMock()
    mock_boto3_resource.return_value = mock_client

    # Define test table name
    table_name = "tradesignals"

    # Call the get_table method
    table = dynamo_manager.get_table(table_name)

    # Assert that the DynamoDB client was called
    mock_boto3_resource.assert_called_once()

    # Assert that the client.Table method was called with the correct table name
    mock_client.Table.assert_called_once_with(table_name)

    # Assert that the returned table is correct
    assert table == mock_client.Table.return_value

def test_get_trade_precedence():
    trade_symbols = ["ETH/USD", "BTC/USD"]
    result = get_trade_precedence(trade_symbols)

    assert result == "ETH/USD"