import pytest
from decimal import Decimal
from chalicelib.trade_execution import Exchange, multi_strategy_allocation, execute_long_stop

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
        {"symbol": "BTC/USD", "currency": "USD", "order_action": "buy", "percentage": Decimal(0.5)},
        {"symbol": "ETH/USD", "currency": "USD", "order_action": "sell"}
    ]
    orders = multi_strategy_allocation(mock_exchange, trades, increment_pct=0.0001)
    assert len(orders) == 2
    assert orders[0].get("price") == Decimal(str(10.0010))
    assert orders[1].get("price") == Decimal(str(9.9990))

def test_multi_strategy_allocation_empty_trades(mock_exchange):
    with pytest.raises(ValueError):
        multi_strategy_allocation(mock_exchange, [])

def test_multi_strategy_allocation_invalid_order_action(mock_exchange):
    trades = [{"symbol": "BTC", "currency": "USD", "order_action": "invalid", "percentage": Decimal(0.5)}]
    with pytest.raises(ValueError):
        multi_strategy_allocation(mock_exchange, trades)

def test_execute_long_stop(mock_exchange):
    trade = {
        "symbol": "BTC/USD", 
        "currency": "USD", 
        "order_action": "sell", 
        "percentage": Decimal(0.5), 
        "order_comment": "long stop"
    }
    order = execute_long_stop(mock_exchange, trade, increment_pct=0.0001)
    assert order.get("price") == Decimal(str(9.9990))