from datetime import datetime
from decimal import Decimal
from unittest.mock import patch
import pytest

from chalicelib.trade_processing import preprocess_trade_signal, get_all_recent_signals, DatabaseError, SignalsFetchError

def test_preprocess_trade_signal():
   """Test trade signal preprocessing with different scenarios."""
   
   # Mock strategy config
   mock_config = {
       "ETH/USD": {
           "exchange_symbol": "ETH/USD",
           "base_asset": "ETH",
           "percentage": 20.5,
       }
   }
   
   # Mock trade signals
   test_cases = [
       {
           "name": "valid trade signal",
           "signal": {
               "ticker": "ETH/USD",
               "time": "2024-01-08T10:00:00",
               "order_action": "buy",
               "order_price": 2500.50
           },
           "expected": {
               "ticker": "ETH/USD",
               "create_ts": "2024-01-08T10:00:00",
               "order_action": "buy",
               "order_price": Decimal("2500.50"),
               "exchange_symbol": "ETH/USD",
               "base_asset": "ETH",
               "percentage": Decimal("20.5"),
           }
       }
   ]
   
   # Test error cases
   error_cases = [
       {
           "name": "missing ticker",
           "signal": {
               "time": "2024-01-08T10:00:00",
               "order_action": "buy",
               "order_price": 2500.50
           },
           "error": "Trade signal missing 'ticker' attribute"
       },
       {
           "name": "missing time",
           "signal": {
               "ticker": "ETH/USD",
               "order_action": "buy",
               "order_price": 2500.50
           },
           "error": "Trade signal missing 'time' attribute"
       },
       {
           "name": "unknown ticker",
           "signal": {
               "ticker": "UNKNOWN/USD",
               "time": "2024-01-08T10:00:00",
               "order_action": "buy",
               "order_price": 2500.50
           },
           "error": "No configuration found for ticker 'UNKNOWN/USD'"
       }
   ]
   
   # Test valid cases
   with patch('chalicelib.utils.load_strategy_config', return_value=mock_config):
       for case in test_cases:
           result = preprocess_trade_signal(case["signal"])
           assert result == case["expected"], \
               f"Failed case '{case['name']}': expected {case['expected']}, got {result}"
   
   # Test error cases
   with patch('chalicelib.utils.load_strategy_config', return_value=mock_config):
       for case in error_cases:
           with pytest.raises(ValueError) as exc_info:
               preprocess_trade_signal(case["signal"])
           assert str(exc_info.value) == case["error"], \
               f"Failed case '{case['name']}': expected '{case['error']}', got '{str(exc_info.value)}'"
           
def test_get_all_recent_signals():
   """Test retrieving recent signals for active strategies."""
   
   # Mock data
   cutoff_time = datetime(2024, 1, 8, 10, 0, 0)
   table_name = "trade_signals"
   
   mock_active_tickers = ["BTC/USD", "ETH/USD"]
   
   mock_signals = {
       "BTC/USD": [
           {
               "ticker": "BTC/USD",
               "create_ts": "2024-01-08T10:30:00",
               "order_action": "buy",
               "order_price": Decimal("45000.00")
           }
       ],
       "ETH/USD": [
           {
               "ticker": "ETH/USD",
               "create_ts": "2024-01-08T11:00:00",
               "order_action": "sell",
               "order_price": Decimal("2500.50")
           }
       ]
   }
   
   # Test successful case
   with patch('chalicelib.trade_processing.get_active_strategy_tickers', return_value=mock_active_tickers), \
        patch('chalicelib.trade_processing.get_ticker_recent_signals', side_effect=lambda ticker, *args: mock_signals[ticker]):
       
       result = get_all_recent_signals(cutoff_time, table_name)
       assert len(result) == 2
       assert result[0]["ticker"] == "BTC/USD"
       assert result[1]["ticker"] == "ETH/USD"

def test_get_all_recent_signals_with_threshold():
   """Test signals retrieval with allocation threshold."""
   
   cutoff_time = datetime(2024, 1, 8, 10, 0, 0)
   threshold = Decimal('5.0')  # 5% threshold
   
   with patch('chalicelib.trade_processing.get_active_strategy_tickers', return_value=[]) as mock_get_tickers:
       result = get_all_recent_signals(cutoff_time, "trade_signals", threshold)
       assert len(result) == 0
       mock_get_tickers.assert_called_once_with(threshold)

def test_get_all_recent_signals_partial_failure():
   """Test handling of partial failures in signal retrieval."""
   
   cutoff_time = datetime(2024, 1, 8, 10, 0, 0)
   mock_active_tickers = ["BTC/USD", "ETH/USD"]
   
   def mock_get_signals(ticker, *args):
       if ticker == "BTC/USD":
           return [{"ticker": "BTC/USD", "order_action": "buy"}]
       raise DatabaseError(f"Failed to fetch signals for {ticker}")
   
   with patch('chalicelib.trade_processing.get_active_strategy_tickers', return_value=mock_active_tickers), \
        patch('chalicelib.trade_processing.get_ticker_recent_signals', side_effect=mock_get_signals):
       
       with pytest.raises(SignalsFetchError) as exc_info:
           get_all_recent_signals(cutoff_time, "trade_signals")
       
       assert "ETH/USD" in exc_info.value.failed_tickers
       assert "Failed to fetch signals for ETH/USD" in exc_info.value.failed_tickers["ETH/USD"]

def test_get_all_recent_signals_no_active_tickers():
   """Test behavior when no active tickers are found."""
   
   cutoff_time = datetime(2024, 1, 8, 10, 0, 0)
   
   with patch('chalicelib.trade_processing.get_active_strategy_tickers', return_value=[]):
       result = get_all_recent_signals(cutoff_time, "trade_signals")
       assert result == []