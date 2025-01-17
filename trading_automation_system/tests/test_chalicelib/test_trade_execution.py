from typing import Dict
from unittest.mock import MagicMock, Mock, patch
import pytest
from decimal import Decimal
from chalicelib.trade_execution import (
    multi_strategy_allocation, 
    execute_long_stop, 
    buy_side_boost,
)
from chalicelib.exceptions import OrderError

def test_multi_strategy_allocation():
   """Test order creation for multiple trading strategies."""
   
   # Mock exchange
   mock_exchange = Mock()
   mock_exchange.get_total_usd.return_value = Decimal('10000')  # $10,000 USD
   mock_exchange.get_last_price.return_value = Decimal('50000')  # $50,000 per BTC
   mock_exchange.get_total_base_asset.return_value = Decimal('0.1')  # 0.1 BTC
   
   # Test trades
   test_cases = [
       {
           "name": "buy and sell orders",
           "trades": [
               {
                   "exchange_symbol": "BTC/USD",
                   "base_asset": "BTC",
                   "order_action": "buy",
                   "percentage": Decimal('0.5')  # 50% allocation
               },
               {
                   "exchange_symbol": "ETH/USD", 
                   "base_asset": "ETH",
                   "order_action": "sell",
                   "percentage": Decimal('0.3')
               }
           ],
           "increment_pct": Decimal(str(0.001)),
           "expected_calls": 2
       }
   ]
   
   for case in test_cases:
       mock_exchange.create_limit_order.reset_mock()
       
       # Execute function
       orders = multi_strategy_allocation(
           exchange=mock_exchange,
           trades=case["trades"],
           increment_pct=case["increment_pct"]
       )
       
       # Verify number of orders
       assert len(orders) == case["expected_calls"], \
           f"Failed case '{case['name']}': Wrong number of orders"
           
       # Verify exchange calls
       assert mock_exchange.create_limit_order.call_count == case["expected_calls"], \
           f"Failed case '{case['name']}': Wrong number of exchange calls"
       
       # Verify specific order parameters
       calls = mock_exchange.create_limit_order.call_args_list
       
       # Verify buy order
       buy_call = calls[0]
       assert buy_call[0][0] == "BTC/USD"  # symbol
       assert buy_call[0][1] == "buy"  # action
       assert buy_call[0][3] > Decimal('50000')  # price higher due to increment
       
       # Verify sell order
       sell_call = calls[1]
       assert sell_call[0][0] == "ETH/USD"  # symbol
       assert sell_call[0][1] == "sell"  # action
       assert sell_call[0][2] == Decimal('0.1')  # amount from get_total_base_asset

def test_multi_strategy_allocation_errors():
   """Test error handling in multi strategy allocation."""
   
   mock_exchange = Mock()
   mock_exchange.get_total_usd.return_value = Decimal('10000')
   
   error_cases = [
       {
           "name": "empty trades list",
           "trades": [],
           "expected_error": ValueError,
           "error_msg": "Trades list is empty"
       },
       {
           "name": "invalid order action",
           "trades": [{
               "exchange_symbol": "BTC/USD",
               "base_asset": "BTC",
               "order_action": "invalid",
               "percentage": Decimal('0.5')
           }],
           "expected_error": ValueError,
           "error_msg": "Invalid order action: invalid"
       },
       {
           "name": "missing required field",
           "trades": [{
               "exchange_symbol": "BTC/USD",
               "base_asset": "BTC",
               # missing order_action
               "percentage": Decimal('0.5')
           }],
           "expected_error": ValueError,
           "error_msg": "Missing required filed in trade"
       }
   ]
   
   for case in error_cases:
       with pytest.raises(case["expected_error"]) as exc_info:
           multi_strategy_allocation(mock_exchange, case["trades"])
       assert case["error_msg"] in str(exc_info.value), \
           f"Failed case '{case['name']}': Wrong error message"

def test_multi_strategy_allocation_exchange_error():
   """Test handling of exchange errors."""
   
   mock_exchange = Mock()
   mock_exchange.get_total_usd.return_value = Decimal('10000')
   mock_exchange.get_last_price.side_effect = Exception("Exchange error")
   
   trades = [{
       "exchange_symbol": "BTC/USD",
       "base_asset": "BTC",
       "order_action": "buy",
       "percentage": Decimal('0.5')
   }]
   
   with pytest.raises(OrderError) as exc_info:
       multi_strategy_allocation(mock_exchange, trades)
   assert "Failed to create order for BTC/USD" in str(exc_info.value)

def test_execute_long_stop():
   """Test long position stop loss execution."""
   
   # Mock exchange setup
   mock_exchange = Mock()
   mock_exchange.get_last_price.return_value = Decimal('50000')  # $50,000 per BTC
   mock_exchange.get_total_base_asset.return_value = Decimal('0.1')  # 0.1 BTC
   
   # Test valid stop loss order
   valid_trade = {
       "exchange_symbol": "BTC/USD",
       "base_asset": "BTC",
       "order_action": "sell"
   }
   
   order = execute_long_stop(
       exchange=mock_exchange,
       trade=valid_trade,
       increment_pct=Decimal(str(0.001))
   )
   
   # Verify exchange method calls
   mock_exchange.get_last_price.assert_called_once_with("BTC/USD")
   mock_exchange.get_total_base_asset.assert_called_once_with("BTC")
   mock_exchange.create_limit_order.assert_called_once()
   
   # Verify order parameters
   call_args = mock_exchange.create_limit_order.call_args[0]
   assert call_args[0] == "BTC/USD"  # symbol
   assert call_args[1] == "sell"     # action
   assert call_args[2] == Decimal('0.1')  # amount
   assert call_args[3] == Decimal('49950')  # price (50000 * 0.999)

def test_execute_long_stop_errors():
   """Test error handling in stop loss execution."""
   
   mock_exchange = Mock()
   
   error_cases = [
       {
           "name": "wrong order action",
           "trade": {
               "exchange_symbol": "BTC/USD",
               "base_asset": "BTC",
               "order_action": "buy"
           },
           "expected_error": ValueError,
           "error_msg": "Stop loss requires sell order"
       },
       {
           "name": "missing field",
           "trade": {
               "exchange_symbol": "BTC/USD",
               # missing base_asset
               "order_action": "sell"
           },
           "expected_error": ValueError,
           "error_msg": "Missing required filed in trade"
       }
   ]
   
   for case in error_cases:
       with pytest.raises(case["expected_error"]) as exc_info:
           execute_long_stop(mock_exchange, case["trade"])
       assert case["error_msg"] in str(exc_info.value), \
           f"Failed case '{case['name']}': Wrong error message"

def test_execute_long_stop_exchange_error():
   """Test handling of exchange errors."""
   
   mock_exchange = Mock()
   mock_exchange.get_last_price.side_effect = Exception("Exchange error")
   
   trade = {
       "exchange_symbol": "BTC/USD",
       "base_asset": "BTC",
       "order_action": "sell"
   }
   
   with pytest.raises(OrderError) as exc_info:
       execute_long_stop(mock_exchange, trade)
   assert "Failed to create order for BTC/USD" in str(exc_info.value)

def create_limit_order_side_effect_func(symbol: str, side: str, amount: Decimal, order_price: Decimal) -> Dict:
   """Mock order creation with calculated cost."""
   return {
       "id": 1,
       "symbol": symbol,
       "side": side,
       "price": float(order_price),
       "cost": float(round(order_price * amount, 2)),
       "amount": float(round(amount, 4))
   }

@pytest.fixture
def mock_exchange():
   """Create a mock exchange with basic functionality."""
   exchange = MagicMock()
   exchange.quote_currency = "USD"
   exchange.create_limit_order.side_effect = create_limit_order_side_effect_func
   return exchange

def create_trade(symbol: str, action: str, percentage: float) -> Dict:
   """Create a trade dictionary with standard format."""
   base_asset = symbol.split('/')[0]
   return {
       "exchange_symbol": symbol,
       "base_asset": base_asset,
       "order_action": action,
       "percentage": Decimal(str(percentage))
   }

@patch('chalicelib.utils.get_total_allocation_pct')
def test_your_function(mock_get_allocation):
    # Set the return value
    mock_get_allocation.return_value = Decimal(str(0.98))

def test_buy_side_boost_no_active_trades(mock_exchange):
   """
   Test buying with no active positions.
   
   Should allocate full available USD (minus buffer) when no other positions exist.
   """
   # Setup
   mock_exchange.get_account_allocation.return_value = {
       "USD": Decimal("1000"),
       "BTC": Decimal("0"),
       "ETH": Decimal("0"),
       "SOL": Decimal("0")
   }
   mock_exchange.get_last_price.return_value = Decimal("50000")
   
   trades = [create_trade("BTC/USD", "buy", 0.2)]
   
   # Expected 98% of USD (buffer = 2%) allocated to BTC
   expected_orders = [{
       'id': 1,
       'symbol': 'BTC/USD',
       'side': 'buy',
       'price': 50000,
       'cost': 980,  # 1000 * 0.98
       'amount': 0.0196  # 980 / 50000
   }]
   
   # Execute
   result = buy_side_boost(mock_exchange, trades)
   
   # Verify
   assert result == expected_orders
   mock_exchange.get_account_allocation.assert_called_once()
   mock_exchange.get_last_price.assert_called_once_with("BTC/USD")
   mock_exchange.create_limit_order.assert_called_once()

def test_buy_side_boost_active_trade_without_precedence(mock_exchange):
    """
    Test buying when active trade doesn't have precedence and needs reallocation.

    Scenario:
    1. Active position in BTC
    2. New SOL trade has higher allocation (53% vs BTC's 20%)
    3. Should sell part of BTC position to make room for SOL
    4. Then buy SOL with freed up funds
    """
    # Setup
    # Mock account balance before and after BTC sell
    mock_exchange.get_account_allocation.side_effect = [
        {
            "USD": Decimal("20"),
            "BTC": Decimal("980"),
            "ETH": Decimal("0"),
            "SOL": Decimal("0")
        },
        {
            "USD": Decimal("820.7"),
            "BTC": Decimal("195"),
            "ETH": Decimal("0"),
            "SOL": Decimal("0")
        }
    ]

    # Mock price lookups
    def get_last_price(symbol: str) -> Decimal:
        prices = {
            "BTC/USD": Decimal("51000"),
            "SOL/USD": Decimal("150")
        }
        return prices[symbol]

    mock_exchange.get_last_price.side_effect = get_last_price
    mock_exchange.get_total_base_asset.side_effect = [Decimal("0.0196")]

    # Create incoming trade
    trades = [create_trade("SOL/USD", "buy", 0.53)]

    # Expected orders
    expected_orders = [
        {
            'id': 1,
            'symbol': 'BTC/USD',
            'side': 'sell',
            'price': 51000,
            'cost': 800.7,    # Selling ~80% of BTC position
            'amount': 0.0157
        },
        {
            'id': 1,
            'symbol': 'SOL/USD',
            'side': 'buy',
            'price': 150,
            'cost': 792.25,   # ~96.5% of freed up funds
            'amount': 5.2816
        }
    ]
   
    # Execute
    with patch("chalicelib.trade_execution.wait_for_order_fill", return_value=True):
        result = buy_side_boost(mock_exchange, trades)

        assert result == expected_orders
        assert mock_exchange.get_account_allocation.call_count == 2
        assert mock_exchange.get_last_price.call_count == 2
        assert mock_exchange.get_total_base_asset.call_count == 1
        assert mock_exchange.create_limit_order.call_count == 2

def test_buy_side_boost_active_trade_with_precedence(mock_exchange):
    """
    Test buying when active trade has precedence and we need reallocation.

    Scenario:
    1. Active position in BTC and SOL
    2. New ETH trade has lower allocation (25% vs SOL's 53%)
    3. Should sell part of SOL position to make room for ETH
    4. Then buy ETH with freed up funds
    """
    mock_exchange.get_account_allocation.side_effect = [
        {
            "USD": Decimal(str(28.45)),
            "BTC": Decimal(str(195)),
            "ETH": Decimal(str(0)),
            "SOL": Decimal(str(792.25)),
        }, {
            "USD": Decimal(str(282.4485)),
            "BTC": Decimal(str(195)),
            "ETH": Decimal(str(0)),
            "SOL": Decimal(str(546.441897)),
        }
    ]

    def get_last_price_side_effect(symbol):
        if symbol == "ETH/USD":
            return Decimal(str(2500))
        elif symbol == "SOL/USD":
            return Decimal(str(155))
        
    mock_exchange.get_total_base_asset.side_effect = [Decimal(str(5.2816)), Decimal(str(3.6443))]
    mock_exchange.get_last_price.side_effect = get_last_price_side_effect
    mock_exchange.create_limit_order.side_effect = create_limit_order_side_effect_func

    # Create incoming trade
    trades = [create_trade("ETH/USD", "buy", 0.25)]

    expected_orders = [
        {
            'id': 1,
            'symbol': 'SOL/USD', 
            'side': 'sell', 
            'price': 155, 
            'cost': 253.78, 
            'amount': 1.6373
        },
        {
            'id': 1,
            'symbol': 'ETH/USD', 
            'side': 'buy', 
            'price': 2500, 
            'cost': 255.97, 
            'amount': 0.1024
        }
    ]

    # Execute
    with patch("chalicelib.trade_execution.wait_for_order_fill", return_value=True):
        result = buy_side_boost(mock_exchange, trades)

        assert result == expected_orders
        assert mock_exchange.get_account_allocation.call_count == 2
        assert mock_exchange.get_last_price.call_count == 2
        assert mock_exchange.get_total_base_asset.call_count == 1
        assert mock_exchange.create_limit_order.call_count == 2

def test_buy_side_boost_sell_signals(mock_exchange):
    mock_exchange.get_account_allocation.side_effect = [
        {
            "USD": Decimal(str(20)),
            "BTC": Decimal(str(200)),
            "ETH": Decimal(str(250)),
            "SOL": Decimal(str(530)),
        }
        ]

    def get_last_price_side_effect(symbol):
        if symbol == "BTC/USD":
            return Decimal(str(50000))
        elif symbol == "ETH/USD":
            return Decimal(str(2500))
        
    mock_exchange.get_total_base_asset.side_effect = [Decimal(str(.002)), Decimal(str(.01))]
    mock_exchange.get_last_price.side_effect = get_last_price_side_effect
    mock_exchange.create_limit_order.side_effect = create_limit_order_side_effect_func

    trades = [
        create_trade("BTC/USD", "sell", 0.20),
        create_trade("ETH/USD", "sell", 0.25),
    ]

    expected_orders = [
        {
            'id': 1,
            'symbol': 'BTC/USD', 
            'side': 'sell', 
            'price': 50000, 
            'cost': 100, 
            'amount': 0.002
        },
        {
            'id': 1,
            'symbol': 'ETH/USD', 
            'side': 'sell', 
            'price': 2500, 
            'cost': 25, 
            'amount': 0.01
        }
    ]
    result = buy_side_boost(mock_exchange, trades)
   
    # Verify
    assert result == expected_orders
    assert mock_exchange.get_total_base_asset.call_count == 2
    assert mock_exchange.get_last_price.call_count == 2
    assert mock_exchange.create_limit_order.call_count == 2

def test_buy_side_boost_partial_allocation(mock_exchange):
    mock_exchange.get_account_allocation.side_effect = [
        {
            "USD": Decimal(str(500)),
            "BTC": Decimal(str(0)),
            "ETH": Decimal(str(0)),
            "SOL": Decimal(str(530)),
        }
        ]

    def get_last_price_side_effect(symbol):
        if symbol == "BTC/USD":
            return Decimal(str(50000))
        elif symbol == "ETH/USD":
            return Decimal(str(2500))
        
    mock_exchange.get_last_price.side_effect = get_last_price_side_effect
    mock_exchange.create_limit_order.side_effect = create_limit_order_side_effect_func

    trades = [
        create_trade("BTC/USD", "buy", 0.20),
        create_trade("ETH/USD", "buy", 0.25),
   ]

    expected_orders = [
        {
            'id': 1,
            'symbol': 'BTC/USD', 
            'side': 'buy', 
            'price': 50000, 
            'cost': 206, 
            'amount': 0.0041
        },
        {
            'id': 1,
            'symbol': 'ETH/USD', 
            'side': 'buy', 
            'price': 2500, 
            'cost': 257.5, 
            'amount': 0.103
        }
    ]
    result = buy_side_boost(mock_exchange, trades)

    # Verify
    assert result == expected_orders
    assert mock_exchange.get_last_price.call_count == 2
    assert mock_exchange.create_limit_order.call_count == 2

def test_buy_side_boost_partial_allocation_incoming_trade_precedence(mock_exchange):
    mock_exchange.get_account_allocation.side_effect = [
        {
            "USD": Decimal(str(1000)),
            "BTC": Decimal(str(200)),
            "ETH": Decimal(str(0)),
            "SOL": Decimal(str(0)),
        }
        ]

    def get_last_price_side_effect(symbol):
        if symbol == "SOL/USD":
            return Decimal(str(150))
        
    mock_exchange.get_last_price.side_effect = get_last_price_side_effect
    mock_exchange.create_limit_order.side_effect = create_limit_order_side_effect_func

    trades = [
        create_trade("SOL/USD", "buy", 0.53),
    ]

    expected_orders = [
        {
            'id': 1,
            'symbol': 'SOL/USD', 
            'side': 'buy', 
            'price': 150, 
            'cost': 936, 
            'amount': 6.24
        }
    ]
    result = buy_side_boost(mock_exchange, trades)

    # Verify
    assert result == expected_orders
    assert mock_exchange.get_last_price.call_count == 1
    assert mock_exchange.create_limit_order.call_count == 1