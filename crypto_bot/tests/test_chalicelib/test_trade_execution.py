import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal
from chalicelib.trade_execution import (
    Exchange, 
    multi_strategy_allocation, 
    execute_long_stop, 
    buy_side_boost,
)

class MockExchange(Exchange):
    def __init__(self):
        pass
    
    def get_total_usd(self):
        # Mock implementation, return some value for testing
        return Decimal(10000)
    
    def get_total_currency(self, currency):
        # Mock implementation, return some value for testing
        return Decimal(1000)
    
    def get_last_price(self, symbol):
        # Mock implementation, return some value for testing
        return Decimal(10)
    
    def create_limit_order(self, symbol, order_action, amount, price):
        # Mock implementation, return some value for testing
        return {"symbol": symbol, "action": order_action, "amount": amount, "price": price}

@pytest.fixture
def mock_exchange():
    return MockExchange()

def test_multi_strategy_allocation_normal(mock_exchange):
    trades = [
        {"symbol": "BTC/USD", "currency": "BTC", "order_action": "buy", "percentage": Decimal(str(0.2))},
        {"symbol": "ETH/USD", "currency": "ETH", "order_action": "sell"}
    ]
    orders = multi_strategy_allocation(mock_exchange, trades, increment_pct=0.0001)
    assert len(orders) == 2
    assert orders[0].get("price") == Decimal(str(10.0010))
    assert orders[1].get("price") == Decimal(str(9.9990))

def test_multi_strategy_allocation_empty_trades(mock_exchange):
    with pytest.raises(ValueError):
        multi_strategy_allocation(mock_exchange, [])

def test_multi_strategy_allocation_invalid_order_action(mock_exchange):
    trades = [{"symbol": "BTC/USD", "currency": "BTC", "order_action": "invalid", "percentage": Decimal(str(0.2))}]
    with pytest.raises(ValueError):
        multi_strategy_allocation(mock_exchange, trades)

def test_execute_long_stop(mock_exchange):
    trade = {
        "symbol": "BTC/USD", 
        "currency": "BTC", 
        "order_action": "sell", 
        "percentage": Decimal(str(0.2)), 
        "order_comment": "long stop"
    }
    order = execute_long_stop(mock_exchange, trade, increment_pct=0.0001)
    assert order.get("price") == Decimal(str(9.9990))

def create_limit_order_side_effect_func(symbol, side, amount, order_price):
    return {'symbol': symbol, 'side': side, 'price': float(order_price), 'cost': float(round(order_price * amount, 2)), 'amount': float(round(amount, 4))}

def test_buy_side_boost_no_active_trades():
    exchange = MagicMock()
    exchange.get_account_allocation.return_value = {
        "USD": 1000,
        "BTC": 0,
        "ETH": 0,
        "SOL": 0,
    }
    exchange.get_last_price.return_value = Decimal(str(50000))
    exchange.create_limit_order.side_effect = create_limit_order_side_effect_func

    trades = [
        {"symbol": "BTC/USD", "currency": "BTC", "order_action": "buy", "percentage": Decimal(str(0.2))},
    ]

    expected_result = [
        {'symbol': 'BTC/USD', 'side': 'buy', 'price': 50000, 'cost': 980, 'amount': 0.0196}
    ]
    result = buy_side_boost(exchange, trades)

    assert result == expected_result

def test_buy_side_boost_active_trade_without_precedence():
    exchange = MagicMock()
    exchange.get_account_allocation.side_effect = [
        {
            "USD": 20,
            "BTC": 980,
            "ETH": 0,
            "SOL": 0,
        }, {
            "USD": 820.7,
            "BTC": 195,
            "ETH": 0,
            "SOL": 0,
        }
        ]

    def get_last_price_side_effect(symbol):
        if symbol == "BTC/USD":
            return Decimal(str(51000))
        elif symbol == "SOL/USD":
            return Decimal(str(150))
        
    exchange.get_total_currency.side_effect = [Decimal(str(0.0196)), Decimal(str(0.0039))]
    exchange.get_last_price.side_effect = get_last_price_side_effect
    exchange.create_limit_order.side_effect = create_limit_order_side_effect_func

    trades = [
        {"symbol": "SOL/USD", "currency": "SOL", "order_action": "buy", "percentage": Decimal(str(0.53))},
    ]

    expected_result = [
        {'symbol': 'BTC/USD', 'side': 'sell', 'price': 51000, 'cost': 800.7, 'amount': 0.0157},
        {'symbol': 'SOL/USD', 'side': 'buy', 'price': 150, 'cost': 792.25, 'amount': 5.2816}
    ]
    result = buy_side_boost(exchange, trades)

    assert result == expected_result

def test_buy_side_boost_active_trade_with_precedence():
    exchange = MagicMock()
    exchange.get_account_allocation.side_effect = [
        {
            "USD": 28.45,
            "BTC": 195,
            "ETH": 0,
            "SOL": 792.25,
        }, {
            "USD": 282.4485,
            "BTC": 195,
            "ETH": 0,
            "SOL": 546.441897,
        }
        ]

    def get_last_price_side_effect(symbol):
        if symbol == "ETH/USD":
            return Decimal(str(2500))
        elif symbol == "SOL/USD":
            return Decimal(str(155))
        
    exchange.get_total_currency.side_effect = [Decimal(str(5.2816)), Decimal(str(3.6443))]
    exchange.get_last_price.side_effect = get_last_price_side_effect
    exchange.create_limit_order.side_effect = create_limit_order_side_effect_func

    trades = [
        {"symbol": "ETH/USD", "currency": "ETH", "order_action": "buy", "percentage": Decimal(str(0.25))},
    ]

    expected_result = [
        {'symbol': 'SOL/USD', 'side': 'sell', 'price': 155, 'cost': 253.78, 'amount': 1.6373},
        {'symbol': 'ETH/USD', 'side': 'buy', 'price': 2500, 'cost': 255.97, 'amount': 0.1024}
    ]
    result = buy_side_boost(exchange, trades)

    assert result == expected_result

def test_buy_side_boost_sell_signals():
    exchange = MagicMock()
    exchange.get_account_allocation.side_effect = [
        {
            "USD": 20,
            "BTC": 200,
            "ETH": 250,
            "SOL": 530,
        }
        ]

    def get_last_price_side_effect(symbol):
        if symbol == "BTC/USD":
            return Decimal(str(50000))
        elif symbol == "ETH/USD":
            return Decimal(str(2500))
        
    exchange.get_total_currency.side_effect = [Decimal(str(.002)), Decimal(str(.01))]
    exchange.get_last_price.side_effect = get_last_price_side_effect
    exchange.create_limit_order.side_effect = create_limit_order_side_effect_func

    trades = [
        {"symbol": "BTC/USD", "currency": "BTC", "order_action": "sell", "percentage": Decimal(str(0.20))},
        {"symbol": "ETH/USD", "currency": "ETH", "order_action": "sell", "percentage": Decimal(str(0.25))},
    ]

    expected_result = [
        {'symbol': 'BTC/USD', 'side': 'sell', 'price': 50000, 'cost': 100, 'amount': 0.002},
        {'symbol': 'ETH/USD', 'side': 'sell', 'price': 2500, 'cost': 25, 'amount': 0.01}
    ]
    result = buy_side_boost(exchange, trades)

    assert result == expected_result

def test_buy_side_boost_partial_allocation():
    exchange = MagicMock()
    exchange.get_account_allocation.side_effect = [
        {
            "USD": 500,
            "BTC": 0,
            "ETH": 0,
            "SOL": 530,
        }
        ]

    def get_last_price_side_effect(symbol):
        if symbol == "BTC/USD":
            return Decimal(str(50000))
        elif symbol == "ETH/USD":
            return Decimal(str(2500))
        
    exchange.get_last_price.side_effect = get_last_price_side_effect
    exchange.create_limit_order.side_effect = create_limit_order_side_effect_func

    trades = [
        {"symbol": "BTC/USD", "currency": "BTC", "order_action": "buy", "percentage": Decimal(str(0.20))},
        {"symbol": "ETH/USD", "currency": "ETH", "order_action": "buy", "percentage": Decimal(str(0.25))},
    ]

    expected_result = [
        {'symbol': 'BTC/USD', 'side': 'buy', 'price': 50000, 'cost': 206, 'amount': 0.0041},
        {'symbol': 'ETH/USD', 'side': 'buy', 'price': 2500, 'cost': 257.5, 'amount': 0.103}
    ]
    result = buy_side_boost(exchange, trades)

    assert result == expected_result

def test_buy_side_boost_partial_allocation_incoming_trade_precedence():
    exchange = MagicMock()
    exchange.get_account_allocation.side_effect = [
        {
            "USD": 1000,
            "BTC": 200,
            "ETH": 0,
            "SOL": 0,
        }
        ]

    def get_last_price_side_effect(symbol):
        if symbol == "SOL/USD":
            return Decimal(str(150))
        
    exchange.get_last_price.side_effect = get_last_price_side_effect
    exchange.create_limit_order.side_effect = create_limit_order_side_effect_func

    trades = [
        {"symbol": "SOL/USD", "currency": "SOL", "order_action": "buy", "percentage": Decimal(str(0.53))},
    ]

    expected_result = [
        {'symbol': 'SOL/USD', 'side': 'buy', 'price': 150, 'cost': 936, 'amount': 6.24}
    ]
    result = buy_side_boost(exchange, trades)

    assert result == expected_result