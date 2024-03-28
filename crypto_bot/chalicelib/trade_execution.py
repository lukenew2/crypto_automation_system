from typing import List
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
    

def multi_strategy_allocation(exchange: Exchange, trades: List) -> List:
    """
    Allocates percentage of portfolio based on multiple strategies.

    Args:
        exchange (Exchange): An instance of the exchange.
        trades (List[dict]): A list of trades. Each trade is a dictionary containing keys:
            - symbol: Symbol of the asset.
            - currency: Currency of the asset.
            - order_action: Action to perform ("buy" or "sell").
            - percentage: Percentage of total allocation for "buy" orders.

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
        if order_action == "sell":
            sell_amount = exchange.get_total_currency(currency)
            order_price = exchange.get_last_price(symbol)
            order = exchange.create_limit_order(symbol, order_action, sell_amount, order_price)
        elif order_action == "buy":
            allocated_usd = total_usd * trade.get("percentage")
            order_price = exchange.get_last_price(symbol)
            position_size = allocated_usd / order_price
            order = exchange.create_limit_order(symbol, order_action, position_size, order_price)
        else:
            raise ValueError(f"Invalid order action: {order_action}")
        
        orders.append(order)

    return orders