import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal
from datetime import datetime
from chalicelib.trade_processing import preprocess_trade_signal, get_ticker_recent_signals

@pytest.fixture
def mock_dynamo_manager():
    """
    Fixture to mock the DynamoDBManager class and return an instance.
    """
    with patch("chalicelib.utils.DynamoDBManager") as mock_dynamo_manager:
        yield mock_dynamo_manager.return_value

@pytest.fixture
def mock_get_dynamodb_table(mock_dynamo_manager):
    """
    Fixture to mock the get_table method of DynamoDBManager.
    """
    with patch.object(mock_dynamo_manager, "get_table") as mock_get_table:
        yield mock_get_table

@pytest.fixture
def mock_get_strategy_config():
    """
    Fixture to mock the get_strategy_config method.
    """
    with patch("chalicelib.utils.get_strategy_config") as mock_get_strategy_config:
        yield mock_get_strategy_config

def test_preprocess_trade_signal(mock_get_strategy_config):
    # Mocked configuration
    ticker_config = {"symbol": "SOL", "percentage": 0.60, "stop_loss": 0.066}
    mock_get_strategy_config.return_value = {"SOLUSD": ticker_config}

    # Input trade signal
    trade_signal = {
        "ticker": "SOLUSD",
        "time": "2024-03-18T08:00:00Z", 
        "order_action": "buy",
        "order_price": "100.0",
    }

    # Call the function
    processed_trade_signal = preprocess_trade_signal(trade_signal)

    # Assertions
    mock_get_strategy_config.assert_called_once()

    assert processed_trade_signal == {
        "ticker": "SOLUSD",
        "order_action": "buy",
        "order_price": Decimal('100.0'),
        "create_ts": "2024-03-18T08:00:00Z",
        "symbol": "SOL",
        "percentage": Decimal('0.6'),
        "stop_loss": Decimal('0.066'),
    }

def test_preprocess_trade_signal_no_ticker():
    """Test case for when trade signalis missing ticker attribute."""
    # Input trade signal
    trade_signal = {
        "time": "2024-03-18T08:00:00Z", 
        "order_action": "buy",
        "order_price": "100.0",
    }

    # Test missing ticker value error
    with pytest.raises(ValueError, match="Trade signal missing 'ticker' attribute."):
        preprocess_trade_signal(trade_signal)

def test_get_recent_trade_signal(mock_get_dynamodb_table):
    # Mock DynamoDB table and query response
    mock_table = MagicMock()
    mock_response = {
        "Items": [
            {"ticker": "SOLUSD", "create_ts": "2024-03-18T18:00:00Z"}
        ]
    }
    mock_table.query.return_value = mock_response
    mock_get_dynamodb_table.return_value = mock_table
    
    # Input parameters
    ticker = "SOLUSD"
    cutoff_time = datetime(2024, 3, 18, 18, 0)
    table_name = "tradesignals"
    
    # Call the function
    result = get_ticker_recent_signals(ticker, cutoff_time, table_name)
    
    # Assertions
    mock_get_dynamodb_table.assert_called_once_with(table_name)
    mock_table.query.assert_called_once_with(
        KeyConditionExpression="#ticker = :ticker AND #create_ts >= :cutoff_time",
        ExpressionAttributeNames={"#ticker": "ticker", "#create_ts": "create_ts"},
        ExpressionAttributeValues={":ticker": ticker, ":cutoff_time": cutoff_time.isoformat()},
        ScanIndexForward=False
    )

    assert result == [
         {"ticker": "SOLUSD", "create_ts": "2024-03-18T18:00:00Z"}
    ]

def test_get_recent_trade_signal_no_signals(mock_get_dynamodb_table):
    """Test case for event that no items are returned."""
    # Mock DynamoDB table and query response
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": []}
    mock_get_dynamodb_table.return_value = mock_table
    
    # Input parameters
    ticker = "SOLUSD"
    cutoff_time = datetime(2024, 3, 18, 18, 0)
    table_name = "tradesignals"
    
    # Call the function
    result = get_ticker_recent_signals(ticker, cutoff_time, table_name)
    
    # Assertions
    mock_get_dynamodb_table.assert_called_once_with(table_name)
    mock_table.query.assert_called_once_with(
        KeyConditionExpression="#ticker = :ticker AND #create_ts >= :cutoff_time",
        ExpressionAttributeNames={"#ticker": "ticker", "#create_ts": "create_ts"},
        ExpressionAttributeValues={":ticker": ticker, ":cutoff_time": cutoff_time.isoformat()},
        ScanIndexForward=False
    )
    assert result == []