import time
from typing import List
from decimal import Decimal, ROUND_HALF_UP
from chalicelib.exchanges import gemini
from chalicelib import utils

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
        # TODO: Deprecate this method
        return self.client.get_bid_ask(symbol)
    
    def get_last_price(self, symbol: str):
        return self.client.get_last_price(symbol)
    
    def get_account_allocation(self):
        return self.client.get_account_allocation()

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
        trades (List[dict]): A list of trades. Each trade is a dictionary containing keys:
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


def buy_side_boost(exchange: Exchange, trades: List[dict], increment_pct: float=0) -> List:
    """
    Most efficient way to allocate funds to multiple strategies.
    
    Buy side boost uses all available capital to purchase on buy signals. When 
    there is more than one strategy in an active trade, the strategy with the 
    higher allocation percentage will receive the otherwise available cash.  

    Args:
        exchange (Exchange): An instance of the exchange.
        trades (List[dict]): A list of trades. Each trade is a dictionary containing keys:
            - symbol: Symbol of the asset.
            - currency: Currency of the asset.
            - order_action: Action to perform ("buy" or "sell").
            - percentage: Percentage of total allocation for "buy" orders.
        increment_pct: Percentage to increment order price by.  Defaults to 0.

    Returns:
        JSON representing order placed.
    """
    if not trades:
        raise ValueError("Trades list is empty.")
    
    sell_signals = [trade for trade in trades if trade.get("order_action") == "sell"]
    buy_signals = [trade for trade in trades if trade.get("order_action") == "buy"]

    orders = []
    if sell_signals:
        for trade in sell_signals:
            symbol = trade.get("symbol")
            currency = trade.get("currency")
            order_action = trade.get("order_action")

            last_price = exchange.get_last_price(symbol)
            price_adjustment = Decimal(str(increment_pct)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

            sell_amount = exchange.get_total_currency(currency)
            order_price = last_price - (last_price * price_adjustment)
            order = exchange.create_limit_order(symbol, order_action, sell_amount, order_price)

            orders.append(order)

    if buy_signals:
        account_allocation_dict = exchange.get_account_allocation()
        strategy_config = utils.get_strategy_config()

        total_account_value_usd = Decimal(str(sum(account_allocation_dict.values())))
        total_usd = Decimal(str(account_allocation_dict.get("USD", 0)))

        incoming_trade_symbols = [buy_signal.get("symbol") for buy_signal in buy_signals]
        current_trade_symbols = [utils.get_symbol_from_currency(key) for key, value in account_allocation_dict.items() if key != "USD" and value > 0]
        all_trade_symbols = incoming_trade_symbols + current_trade_symbols

        total_config_allocation_pct = sum([Decimal(str(strategy.get("percentage", 0))) for strategy in strategy_config.values()])
        unallocated_pct = 1 - total_config_allocation_pct # Configured percentage not allocated to any strategy for fees & flexibility

        incoming_trades_pct = sum([trade.get("percentage", 0) for trade in buy_signals])
        current_trades_config_pct = sum([Decimal(str(utils.get_percentage_from_symbol(symbol))) for symbol in current_trade_symbols])

        available_pct = total_config_allocation_pct - incoming_trades_pct - current_trades_config_pct 
        available_usd_pct = round(total_usd / total_account_value_usd, 4)

        trade_precedence_symbol = utils.get_trade_precedence(all_trade_symbols)

        # If active trades, reallocate funds to incoming trades, prioritizing the symbol with trade precedence.
        if current_trade_symbols:
            # Partially allocated account and trade precedence symbol stays in current trades
            if (trade_precedence_symbol in current_trade_symbols) & (incoming_trades_pct <= available_usd_pct):
                for trade in buy_signals:
                    symbol = trade.get("symbol")
                    currency = trade.get("currency")
                    order_action = trade.get("order_action")
                    percentage = trade.get("percentage")

                    last_price = exchange.get_last_price(symbol)
                    price_adjustment = Decimal(str(increment_pct)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

                    allocated_usd = total_account_value_usd * percentage
                    order_price = last_price + (last_price * price_adjustment)
                    position_size = allocated_usd / order_price
                    order = exchange.create_limit_order(symbol, order_action, position_size, order_price)

                    orders.append(order)

            # Sell from symbol with trade precedence to make room for incoming trades
            elif (trade_precedence_symbol in current_trade_symbols) & (incoming_trades_pct > available_usd_pct):
                trade_precedence_currency = utils.get_currency_from_symbol(trade_precedence_symbol)
                trade_precedence_owned = exchange.get_total_currency(trade_precedence_currency)

                # Calculate proportion of current trade to sell to get account to target allocation
                account_sell_pct = (incoming_trades_pct - available_usd_pct) + unallocated_pct
                current_pct = Decimal(str(account_allocation_dict.get(trade_precedence_currency))) / total_account_value_usd
                position_sell_pct = round(account_sell_pct / current_pct, 2)

                last_price = exchange.get_last_price(trade_precedence_symbol)
                price_adjustment = Decimal(str(increment_pct)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

                sell_amount = round(trade_precedence_owned * position_sell_pct, 4)
                order_price = last_price - (last_price * price_adjustment)
                order = exchange.create_limit_order(trade_precedence_symbol, "sell", sell_amount, order_price)

                orders.append(order)

                # Wait till order is filled
                if not wait_till_sell_order_fill(exchange, trade_precedence_currency, trade_precedence_owned - sell_amount, wait_seconds=15, max_attempts=4):
                    raise ValueError(f"Failed to fill sell order on {trade_precedence_symbol} in specified time.")

                account_allocation_dict = exchange.get_account_allocation()
                total_account_value_usd = Decimal(str(sum(account_allocation_dict.values()) ))

                for trade in buy_signals:
                    symbol = trade.get("symbol")
                    currency = trade.get("currency")
                    order_action = trade.get("order_action")
                    percentage = trade.get("percentage")

                    last_price = exchange.get_last_price(symbol)
                    price_adjustment = Decimal(str(increment_pct)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

                    allocated_usd = total_account_value_usd * percentage
                    order_price = last_price + (last_price * price_adjustment)
                    position_size = allocated_usd / order_price
                    order = exchange.create_limit_order(symbol, order_action, position_size, order_price)

                    orders.append(order)

            # No selling required
            elif (trade_precedence_symbol in incoming_trade_symbols) & (incoming_trades_pct + available_pct + unallocated_pct <= available_usd_pct):
                for trade in buy_signals:
                    symbol = trade.get("symbol")
                    currency = trade.get("currency")
                    order_action = trade.get("order_action")
                    if symbol == trade_precedence_symbol:
                        percentage = trade.get("percentage") + available_pct
                    else:
                        percentage = trade.get("percentage")

                    last_price = exchange.get_last_price(symbol)
                    price_adjustment = Decimal(str(increment_pct)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

                    allocated_usd = total_account_value_usd * percentage
                    order_price = last_price + (last_price * price_adjustment)
                    position_size = allocated_usd / order_price
                    order = exchange.create_limit_order(symbol, order_action, position_size, order_price)

                    orders.append(order)

            # Sell from current trades symbol with trade precedence to make room for incoming trades
            elif (trade_precedence_symbol in incoming_trade_symbols) & (incoming_trades_pct + available_pct + unallocated_pct > available_usd_pct):
                sell_from_symbol = utils.get_trade_precedence(current_trade_symbols)
                sell_from_currency = utils.get_currency_from_symbol(sell_from_symbol)
                sell_from_owned = exchange.get_total_currency(sell_from_currency)

                target_pct = Decimal(str(utils.get_percentage_from_symbol(sell_from_symbol)))
                current_pct = Decimal(str(account_allocation_dict.get(sell_from_currency))) / total_account_value_usd
                
                account_sell_pct = current_pct - target_pct
                position_sell_pct = round(account_sell_pct / current_pct, 2)

                last_price = exchange.get_last_price(sell_from_symbol)
                price_adjustment = Decimal(str(increment_pct)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

                sell_amount = round(sell_from_owned * position_sell_pct, 4)
                order_price = last_price - (last_price * price_adjustment)
                order = exchange.create_limit_order(sell_from_symbol, "sell", sell_amount, order_price)

                orders.append(order)

                # Wait till order is filled
                if not wait_till_sell_order_fill(exchange, sell_from_currency, sell_from_owned - sell_amount, wait_seconds=15, max_attempts=4):
                    raise ValueError(f"Failed to fill sell order on {sell_from_symbol} in specified time.")

                account_allocation_dict = exchange.get_account_allocation()
                total_account_value_usd = Decimal(str(sum(account_allocation_dict.values())))

                for trade in buy_signals:
                    symbol = trade.get("symbol")
                    currency = trade.get("currency")
                    order_action = trade.get("order_action")

                    if symbol == trade_precedence_symbol:
                        percentage = trade.get("percentage") + available_pct
                    else:
                        percentage = trade.get("percentage")

                    last_price = exchange.get_last_price(symbol)
                    price_adjustment = Decimal(str(increment_pct)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

                    allocated_usd = total_account_value_usd * percentage
                    order_price = last_price + (last_price * price_adjustment)
                    position_size = allocated_usd / order_price
                    order = exchange.create_limit_order(symbol, order_action, position_size, order_price)

                    orders.append(order)

        # If no active trades, use full account value for incoming trades, prioritizing the symbol with trade precedence.
        elif not current_trade_symbols:
            for trade in buy_signals:
                symbol = trade.get("symbol")
                currency = trade.get("currency")
                order_action = trade.get("order_action")
                if symbol == trade_precedence_symbol:
                    percentage = trade.get("percentage") + Decimal(str(available_pct))
                else:
                    percentage = trade.get("percentage")

                last_price = exchange.get_last_price(symbol)
                price_adjustment = Decimal(str(increment_pct)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

                allocated_usd = total_usd * percentage
                order_price = last_price + (last_price * price_adjustment)
                position_size = allocated_usd / order_price
                order = exchange.create_limit_order(symbol, order_action, position_size, order_price)

                orders.append(order)

    return orders

def wait_till_sell_order_fill(exchange: Exchange, currency: str, amount: Decimal, wait_seconds: int=15, max_attempts: int=3) -> bool:
    """
    Waits for a sell order to be filled.

    Args:
        exchange (Exchange): An instance of the exchange.
        currency (str): Currency of the asset.
        amount (float): Amount of the asset to be sold.

    Returns:
        True if order is filled, False otherwise.
    """
    attempts = 0
    while attempts < max_attempts:
        currency_now = exchange.get_total_currency(currency)
        if currency_now == amount:
            return True
        else:
            time.sleep(wait_seconds)
            attempts += 1
    return False