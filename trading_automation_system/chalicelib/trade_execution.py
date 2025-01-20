import time
from typing import List, Dict, Any
from decimal import Decimal
from chalicelib.exchanges import gemini, binance, bybit
from chalicelib import utils
from chalicelib.exceptions import OrderError, OrderFillError

class Exchange:
    def __init__(self, exchange_name: str, quote_currency: str):
        self.quote_currency = quote_currency
        if exchange_name == "gemini":
            self.client = gemini.GeminiClient(quote_currency)
        if exchange_name == "binance":
            self.client = binance.BinanceClient(quote_currency)
        if exchange_name == "bybit":
            self.client = bybit.BybitClient(quote_currency)
        

    def connect(self, secret_name, sandbox=False, max_retries=3):
        self.client.connect(secret_name, sandbox, max_retries)

    def create_limit_order(self, symbol: str, side: str, amount: float, order_price: float):
        return self.client.create_limit_order(symbol, side, amount, order_price)
    
    def get_order_status(self, order_id: str) -> str:
        return self.client.get_order_status(order_id)

    def get_total_base_asset(self, base_asset: str):
        return self.client.get_total_base_asset(base_asset)
    
    def get_last_price(self, symbol: str):
        return self.client.get_last_price(symbol)
    
    def get_account_allocation(self):
        return self.client.get_account_allocation()

    def get_total_usd(self):
        return self.client.get_total_usd()
    

def multi_strategy_allocation(   
    exchange: Exchange,
    trades: List[Dict[str, Any]],
    increment_pct: Decimal = Decimal(str(0))
) -> List[Dict[str, Any]]:
    """
    Place orders for multiple trading strategies using portfolio allocation.
    
    Handles both buy and sell orders:
    - Buy orders are sized based on the strategy's allocation percentage
    - Sell orders liquidate the entire position
    - Order prices are adjusted by increment_pct to account for slippage
    
    Args:
        exchange: Exchange instance for trading
        trades: List of trade dictionaries, each containing:
            - exchange_symbol: Trading pair (e.g., "BTC/USD")
            - base_asset: Base currency (e.g., "BTC")
            - order_action: Either "buy" or "sell"
            - percentage: Portfolio allocation for buys
        increment_pct: Percentage to adjust order price (default: 0)
            Positive values increase buy prices and decrease sell prices
            
    Returns:
        List of executed orders from the exchange
        
    Raises:
        ValueError: If trades list is empty or contains invalid actions
        OrderError: If order creation fails
    """
    if not trades:
        raise ValueError("Trades list is empty.")

    total_usd = exchange.get_total_usd()
    orders = []

    for trade in trades:
        try:
            symbol = trade["exchange_symbol"]
            base_asset = trade["base_asset"]
            order_action = trade["order_action"]

            if order_action not in ("buy", "sell"):
                raise ValueError(f"Invalid order action: {order_action}")
            
            last_price = exchange.get_last_price(symbol)
            
            if order_action == "sell":
                sell_amount = exchange.get_total_base_asset(base_asset)
                order_price = last_price * (1 - increment_pct)
                order = exchange.create_limit_order(symbol, order_action, sell_amount, order_price)

            elif order_action == "buy":
                percentage = trade["percentage"]
                allocated_usd = total_usd * percentage
                order_price = last_price * (1 + increment_pct)
                position_size = allocated_usd / order_price
                order = exchange.create_limit_order(symbol, order_action, position_size, order_price)
            
            orders.append(order)

        except KeyError as e:
            raise ValueError(f"Missing required filed in trade: {str(e)}")
        except ValueError as e:
            raise ValueError(f"Trades list is emptry or invalid order action: {str(e)}")
        except Exception as e:
            raise OrderError(f"Failed to create order for {symbol}: {str(e)}") from e

    return orders

def execute_long_stop(   
    exchange: Exchange,
    trade: Dict[str, Any],
    increment_pct: Decimal = Decimal(str(0))
) -> Dict[str, Any]:
    """
    Execute a stop loss order for a long position.

    Creates a sell order for the entire position at a price slightly below
    market price to ensure execution. The price discount is controlled by
    increment_pct.

    Args:
        exchange: Exchange instance for trading
        trade: Trade signal containing:
            - exchange_symbol: Trading pair (e.g., "BTC/USD")
            - base_asset: Base currency (e.g., "BTC")
            - order_action: Must be "sell" for stop loss
        increment_pct: Percentage to reduce sell price by (default: 0)
            
    Returns:
        Dictionary containing the executed order details
        
    Raises:
        ValueError: If order_action is not "sell"
        OrderError: If order creation fails
    """
    try:
        symbol = trade["exchange_symbol"]
        base_asset = trade["base_asset"]
        order_action = trade["order_action"]
    
        if order_action != "sell":
            raise ValueError(f"Stop loss requires sell order, got: {order_action}")

        last_price = exchange.get_last_price(symbol)
        
        sell_amount = exchange.get_total_base_asset(base_asset)
        order_price = last_price * (1 - increment_pct)
        
        return exchange.create_limit_order(symbol, order_action, sell_amount, order_price)
    
    except KeyError as e:
        raise ValueError(f"Missing required filed in trade: {str(e)}")
    except ValueError as e:
        raise ValueError(f"Trades list is emptry or invalid order action: {str(e)}")
    except Exception as e:
        raise OrderError(f"Failed to create order for {symbol}: {str(e)}") from e
    
def wait_for_order_fill(
    exchange: Exchange,
    order_id: str,
    wait_seconds: int = 15,
    max_attempts: int = 3
) -> bool:
    """
    Wait for a specific order to be filled.
    
    Polls the exchange at regular intervals to check order status.
    
    Args:
        exchange: Exchange instance for trading
        order_id: ID of the order to check
        wait_seconds: Seconds to wait between checks
        max_attempts: Maximum number of status checks
        
    Returns:
        True if order is filled, False if still open after max attempts
        
    Raises:
        OrderFillError: If order status check fails
    """
    for attempt in range(max_attempts):
        try:
            order_status = exchange.get_order_status(order_id)
            
            if order_status == "closed":
                return True
                
            if order_status == "canceled":
                return False
                
            time.sleep(wait_seconds)
            
        except Exception as e:
            raise OrderFillError(
                f"Failed to check order {order_id} status: {str(e)}"
            ) from e
            
    return False

def buy_side_boost(
        exchange: Exchange, 
        trades: List[dict], 
        increment_pct: Decimal = Decimal(str(0))
    ) -> List:
    """
    Most efficient way to allocate funds to multiple strategies.
    
    Buy side boost uses all available capital to purchase on buy signals. When 
    there is more than one strategy in an active trade, the strategy with the 
    higher allocation percentage will receive the otherwise available cash.  

    Args:
        exchange (Exchange): An instance of the exchange.
        trades (List[dict]): A list of trades. Each trade is a dictionary containing keys:
            - exchange_symbol: Symbol of the asset on the exchange.
            - base_asset: Name of the base asset.
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
            symbol = trade.get("exchange_symbol")
            base_asset = trade.get("base_asset")
            order_action = trade.get("order_action")

            last_price = exchange.get_last_price(symbol)

            sell_amount = exchange.get_total_base_asset(base_asset)
            order_price = last_price * (1 - increment_pct)
            order = exchange.create_limit_order(symbol, order_action, sell_amount, order_price)

            orders.append(order)

    if buy_signals:
        account_allocation_dict = exchange.get_account_allocation()
        print(f"[Trade Debug] Initial Balance: {account_allocation_dict}")

        total_account_value_usd = sum(account_allocation_dict.values())
        total_usd = account_allocation_dict.get(exchange.quote_currency, 0)

        incoming_trade_symbols = [buy_signal.get("exchange_symbol") for buy_signal in buy_signals]
        current_trade_symbols = [utils.get_exchange_symbol_from_base_asset(key) for key, value in account_allocation_dict.items() if key != exchange.quote_currency and value > 0]
        all_trade_symbols = incoming_trade_symbols + current_trade_symbols

        total_config_allocation_pct = utils.get_total_allocation_pct()
        unallocated_pct = 1 - total_config_allocation_pct # Configured percentage not allocated to any strategy for fees & flexibility

        incoming_trades_pct = sum([trade.get("percentage", 0) for trade in buy_signals])
        current_trades_config_pct = sum([utils.get_percentage_from_exchange_symbol(symbol) for symbol in current_trade_symbols])

        available_pct = total_config_allocation_pct - incoming_trades_pct - current_trades_config_pct 
        available_usd_pct = round(total_usd / total_account_value_usd, 4)

        trade_precedence_symbol = utils.get_trade_precedence(all_trade_symbols)

        # If active trades, reallocate funds to incoming trades, prioritizing the symbol with trade precedence.
        if current_trade_symbols:
            # Partially allocated account and trade precedence symbol stays in current trades
            if (trade_precedence_symbol in current_trade_symbols) & (incoming_trades_pct <= available_usd_pct):
                for trade in buy_signals:
                    symbol = trade.get("exchange_symbol")
                    base_asset = trade.get("base_asset")
                    order_action = trade.get("order_action")
                    percentage = trade.get("percentage")

                    last_price = exchange.get_last_price(symbol)
                    
                    allocated_usd = total_account_value_usd * percentage
                    order_price = last_price * (1 + increment_pct)
                    position_size = allocated_usd / order_price
                    order = exchange.create_limit_order(symbol, order_action, position_size, order_price)

                    orders.append(order)

            # Sell from symbol with trade precedence to make room for incoming trades
            elif (trade_precedence_symbol in current_trade_symbols) & (incoming_trades_pct > available_usd_pct):
                trade_precedence_base_asset = utils.get_base_asset_from_exchange_symbol(trade_precedence_symbol)
                trade_precedence_owned = exchange.get_total_base_asset(trade_precedence_base_asset)

                # Calculate proportion of current trade to sell to get account to target allocation
                account_sell_pct = (incoming_trades_pct - available_usd_pct) + unallocated_pct
                current_pct = account_allocation_dict.get(trade_precedence_base_asset) / total_account_value_usd
                position_sell_pct = round(account_sell_pct / current_pct, 2)

                last_price = exchange.get_last_price(trade_precedence_symbol)

                sell_amount = round(trade_precedence_owned * position_sell_pct, 4)
                order_price = last_price * (1 - increment_pct)
                order = exchange.create_limit_order(trade_precedence_symbol, "sell", sell_amount, order_price)

                orders.append(order)

                # Wait till order is filled
                if not wait_for_order_fill(exchange, order["id"], wait_seconds=15, max_attempts=4):
                    raise ValueError(f"Failed to fill sell order on {trade_precedence_symbol} in specified time.")

                time.sleep(5) # Add delay so balance gets updated in exchanges internal system

                account_allocation_dict = exchange.get_account_allocation()
                print(f"[Trade Debug] Balance after sell: {account_allocation_dict}")
                total_account_value_usd = sum(account_allocation_dict.values())

                for trade in buy_signals:
                    symbol = trade.get("exchange_symbol")
                    base_asset = trade.get("base_asset")
                    order_action = trade.get("order_action")
                    percentage = trade.get("percentage")

                    last_price = exchange.get_last_price(symbol)

                    allocated_usd = total_account_value_usd * percentage
                    order_price = last_price * (1 + increment_pct)
                    position_size = allocated_usd / order_price
                    order = exchange.create_limit_order(symbol, order_action, position_size, order_price)

                    orders.append(order)

            # No selling required
            elif (trade_precedence_symbol in incoming_trade_symbols) & (incoming_trades_pct + available_pct + unallocated_pct <= available_usd_pct):
                for trade in buy_signals:
                    symbol = trade.get("exchange_symbol")
                    base_asset = trade.get("base_asset")
                    order_action = trade.get("order_action")
                    if symbol == trade_precedence_symbol:
                        percentage = trade.get("percentage") + available_pct
                    else:
                        percentage = trade.get("percentage")

                    last_price = exchange.get_last_price(symbol)

                    allocated_usd = total_account_value_usd * percentage
                    order_price = last_price * (1 + increment_pct)
                    position_size = allocated_usd / order_price
                    order = exchange.create_limit_order(symbol, order_action, position_size, order_price)

                    orders.append(order)

            # Sell from current trades symbol with trade precedence to make room for incoming trades
            elif (trade_precedence_symbol in incoming_trade_symbols) & (incoming_trades_pct + available_pct + unallocated_pct > available_usd_pct):
                sell_from_symbol = utils.get_trade_precedence(current_trade_symbols)
                sell_from_base_asset = utils.get_base_asset_from_exchange_symbol(sell_from_symbol)
                sell_from_owned = exchange.get_total_base_asset(sell_from_base_asset)

                target_pct = utils.get_percentage_from_exchange_symbol(sell_from_symbol)
                current_pct = account_allocation_dict.get(sell_from_base_asset) / total_account_value_usd
                
                account_sell_pct = current_pct - target_pct
                position_sell_pct = round(account_sell_pct / current_pct, 2)

                last_price = exchange.get_last_price(sell_from_symbol)

                sell_amount = round(sell_from_owned * position_sell_pct, 4)
                order_price = last_price * (1 - increment_pct)
                order = exchange.create_limit_order(sell_from_symbol, "sell", sell_amount, order_price)

                orders.append(order)

                # Wait till order is filled
                if not wait_for_order_fill(exchange, order["id"], wait_seconds=15, max_attempts=4):
                    raise ValueError(f"Failed to fill sell order on {sell_from_symbol} in specified time.")
                
                time.sleep(5) # Add delay so balance gets updated in exchanges internal system

                account_allocation_dict = exchange.get_account_allocation()
                print(f"[Trade Debug] Balance after sell: {account_allocation_dict}")
                total_account_value_usd = sum(account_allocation_dict.values())

                for trade in buy_signals:
                    symbol = trade.get("exchange_symbol")
                    base_asset = trade.get("base_asset")
                    order_action = trade.get("order_action")

                    if symbol == trade_precedence_symbol:
                        percentage = trade.get("percentage") + available_pct
                    else:
                        percentage = trade.get("percentage")

                    last_price = exchange.get_last_price(symbol)

                    allocated_usd = total_account_value_usd * percentage
                    order_price = last_price * (1 + increment_pct)
                    position_size = allocated_usd / order_price
                    order = exchange.create_limit_order(symbol, order_action, position_size, order_price)

                    orders.append(order)

        # If no active trades, use full account value for incoming trades, prioritizing the symbol with trade precedence.
        elif not current_trade_symbols:
            for trade in buy_signals:
                symbol = trade.get("exchange_symbol")
                base_asset = trade.get("base_asset")
                order_action = trade.get("order_action")
                if symbol == trade_precedence_symbol:
                    percentage = trade.get("percentage") + available_pct
                else:
                    percentage = trade.get("percentage")

                last_price = exchange.get_last_price(symbol)

                allocated_usd = total_usd * percentage
                order_price = last_price * (1 + increment_pct)
                position_size = allocated_usd / order_price
                order = exchange.create_limit_order(symbol, order_action, position_size, order_price)

                orders.append(order)

    return orders