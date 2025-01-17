import pytest
from unittest.mock import Mock, patch
from decimal import Decimal
from ccxt.base.errors import NetworkError, ExchangeError
from chalicelib.exchanges.gemini import GeminiClient, ConnectionError


def test_get_most_recent_trade():
   """Test different scenarios for get_most_recent_trade method."""
   
   # Setup mock client
   mock_client = Mock()
   exchange = GeminiClient("USD")
   exchange._client = mock_client
   
   test_cases = [
       {
           "name": "empty trades list",
           "trades": [],
           "expected": []
       },
       {
           "name": "single buy trade",
           "trades": [
               {"side": "buy", "amount": 1.0, "price": 100}
           ],
           "expected": [
               {"side": "buy", "amount": 1.0, "price": 100}
           ]
       },
       {
           "name": "multiple buys no sell",
           "trades": [
               {"side": "buy", "amount": 1.0, "price": 100},
               {"side": "buy", "amount": 2.0, "price": 90}
           ],
           "expected": [
               {"side": "buy", "amount": 1.0, "price": 100},
               {"side": "buy", "amount": 2.0, "price": 90}
           ]
       },
       {
           "name": "buy-sell sequence with earlier trades",
           "trades": [
               {"side": "buy", "amount": 1.0, "price": 80},
               {"side": "sell", "amount": 1.0, "price": 85},
               {"side": "buy", "amount": 2.0, "price": 90},
               {"side": "buy", "amount": 1.0, "price": 95}
           ],
           "expected": [
               {"side": "buy", "amount": 2.0, "price": 90},
               {"side": "buy", "amount": 1.0, "price": 95}
           ]
       },
       {
           "name": "multiple buy-sell sequences",
           "trades": [
               {"side": "buy", "amount": 1.0, "price": 100},
               {"side": "sell", "amount": 1.0, "price": 110},
               {"side": "buy", "amount": 2.0, "price": 95},
               {"side": "buy", "amount": 1.0, "price": 90},
               {"side": "sell", "amount": 3.0, "price": 105},
               {"side": "buy", "amount": 1.5, "price": 92}
           ],
           "expected": [
               {"side": "buy", "amount": 1.5, "price": 92}
           ]
       },
       {
           "name": "multiple buys with partial sell",
           "trades": [
               {"side": "buy", "amount": 5.0, "price": 100},
               {"side": "sell", "amount": 5.0, "price": 150},
               {"side": "buy", "amount": 2.0, "price": 100},
               {"side": "buy", "amount": 3.0, "price": 95},
               {"side": "sell", "amount": 1.0, "price": 110},
           ],
           "expected": [
               {"side": "buy", "amount": 2.0, "price": 100},
               {"side": "buy", "amount": 3.0, "price": 95},
               {"side": "sell", "amount": 1.0, "price": 110},
           ]
       }
   ]
   
   for case in test_cases:
       # Set return value for mock
       mock_client.fetch_my_trades.return_value = case["trades"]
       
       # Test the function
       result = exchange.get_most_recent_trade("ETH/USD")
       
       # Verify the result
       assert result == case["expected"], f"Failed case: {case['name']}"

def test_get_most_recent_trade_network_error():
    """Test network error handling."""
    
    mock_client = Mock()
    exchange = GeminiClient("USD")
    exchange._client = mock_client
    exchange.RETRY_DELAY = 0  # Speed up test
    
    # Mock network error
    mock_client.fetch_my_trades.side_effect = NetworkError("Connection failed")
    
    with pytest.raises(ConnectionError) as exc_info:
        exchange.get_most_recent_trade("ETH/USD", max_retries=2)
    
    assert "Failed to fetch trades after 2 attempts" in str(exc_info.value)
    assert mock_client.fetch_my_trades.call_count == 2  # Verify retry behavior

def test_get_most_recent_trade_exchange_error():
    """Test exchange error handling."""
    
    mock_client = Mock()
    exchange = GeminiClient("USD")
    exchange._client = mock_client
    
    # Mock exchange error
    mock_client.fetch_my_trades.side_effect = ExchangeError("Invalid symbol")
    
    with pytest.raises(ConnectionError) as exc_info:
        exchange.get_most_recent_trade("ETH/USD")
    
    assert "Failed to fetch trades" in str(exc_info.value)

def test_get_trade_value_usd():
   """Test calculating remaining USD value of trades in different scenarios."""
   
   exchange = GeminiClient("USD")
   
   test_cases = [
       {
           "name": "single buy",
           "trades": [
               {
                   'symbol': 'ETH/USD',
                   'side': 'buy',
                   'price': 3359.31,
                   'cost': 2000,
                   'amount': 1.15
               }
           ],
           "expected": 2000
       },
       {
           "name": "multiple buys no sells",
           "trades": [
               {
                   'symbol': 'ETH/USD',
                   'side': 'buy', 
                   'price': 3359.31,
                   'cost': 2000,
                   'amount': 1.15
               },
               {
                   'symbol': 'ETH/USD',
                   'side': 'buy',
                   'price': 3359.31,
                   'cost': 200,
                   'amount': 0.115
               }
           ],
           "expected": 2200
       },
       {
           "name": "multiple buys with partial sell",
           "trades": [
               {
                   'symbol': 'ETH/USD',
                   'side': 'buy',
                   'price': 3359.31,
                   'cost': 2000,
                   'amount': 1.15
               },
               {
                   'symbol': 'ETH/USD',
                   'side': 'buy',
                   'price': 3359.31,
                   'cost': 200,
                   'amount': 0.115
               },
               {
                   'symbol': 'ETH/USD',
                   'side': 'sell',
                   'price': 3679.36,
                   'cost': 1200,
                   'amount': 0.55
               }
           ],
           "expected": 1254  # (1.15 + 0.115 - 0.55)/(1.15 + 0.115) * 2200
       },
       {
           "name": "complete buy-sell cycle",
           "trades": [
               {
                   'symbol': 'ETH/USD',
                   'side': 'buy',
                   'price': 3359.31,
                   'cost': 500,
                   'amount': 0.156192
               },
               {
                   'symbol': 'ETH/USD',
                   'side': 'sell',
                   'price': 3679.36,
                   'cost': 500,
                   'amount': 0.156192
               }
           ],
           "expected": 0  # All position sold
       }
   ]
   
   for case in test_cases:
       result = exchange.get_trade_value_usd(case["trades"])
       assert result == case["expected"], \
           f"Failed case '{case['name']}': expected {case['expected']}, got {result}"
