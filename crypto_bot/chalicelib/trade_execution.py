from typing import List
from decimal import Decimal, ROUND_HALF_UP
from chalicelib.exchanges import gemini

class Exchange:
    def __init__(self, exchange_name: str):
        if exchange_name == "gemini":
            self.client = gemini.GeminiClient()

    def connect(self, secret_name, sandbox=False, max_retries=3):
        self.client.connect(secret_name, sandbox, max_retries)

    def create_limit_order(self, symbol: str, side: str, amount: float, order_price: float):
        return self.client.create_limit_order(symbol, side, amount, order_price)

    def get_total_currency(self, currency: str):
        return self.client.get_total_currency(currency)

    def get_bid_ask(self, symbol: str):
        return self.client.get_bid_ask(symbol)
    
    def get_last_price(self, symbol: str):
        return self.client.get_last_price(symbol)

    def get_total_usd(self):
        return self.client.get_total_usd()
    

def multi_strategy_allocation(exchange: Exchange, trades: List[dict], increment_pct: float=0) -> List:
    """
    Allocates percentage of portfolio based on multiple strategies.

    Args:
        exchange (Exchange): An instance of the exchange.
        trades (List[dict]): A list of trades. Each trade is a dictionary containing keys:
            - symbol: Symbol of the asset.
            - currency: Currency of the asset.
            - order_action: Action to perform ("buy" or "sell").
            - percentage: Percentage of total allocation for "buy" orders.
        increment_pct: Percentage to increment order price by.  Defaults to 0.

    Returns:
        List of orders placed on the exchange.
    """
    if not trades:
        raise ValueError("Trades list is empty.")

    total_usd = exchange.get_total_usd()
    orders = []

    for trade in trades:
        
        symbol = trade.get("symbol")
        currency = trade.get("currency")
        order_action = trade.get("order_action")
        percentage = trade.get("percentage")

        if order_action not in ("buy", "sell"):
            raise ValueError(f"Invalid order action: {order_action}")
        
        last_price = exchange.get_last_price(symbol)
        price_adjustment = Decimal(str(increment_pct)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        
        if order_action == "sell":
            sell_amount = exchange.get_total_currency(currency)
            order_price = last_price - (last_price * price_adjustment)
            order = exchange.create_limit_order(symbol, order_action, sell_amount, order_price)

        elif order_action == "buy":
            allocated_usd = total_usd * percentage
            order_price = last_price + (last_price * price_adjustment)
            position_size = allocated_usd / order_price
            order = exchange.create_limit_order(symbol, order_action, position_size, order_price)
        
        orders.append(order)

    return orders

def execute_long_stop(exchange: Exchange, trade: dict, increment_pct: float=0) -> dict:
    """
    Executes long stop trading signal from TradingView strategy.

    Args:
        exchange (Exchange): An instance of the exchange.
        trades: A dictionary containing keys:
            - symbol: Symbol of the asset.
            - currency: Currency of the asset.
            - order_action: Action to perform ("buy" or "sell").
            - percentage: Percentage of total allocation for "buy" orders.
        increment_pct: Percentage to increment order price by.  Defaults to 0.

    Returns:
        JSON representing order placed.
    """
    symbol = trade.get("symbol")
    currency = trade.get("currency")
    order_action = trade.get("order_action")
    
    if order_action != "sell":
        raise ValueError(f"Invalid order action for long stop: {order_action}")

    last_price = exchange.get_last_price(symbol)
    price_adjustment = Decimal(str(increment_pct)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
    
    sell_amount = exchange.get_total_currency(currency)
    order_price = last_price - (last_price * price_adjustment)
    order = exchange.create_limit_order(symbol, order_action, sell_amount, order_price)

    return order