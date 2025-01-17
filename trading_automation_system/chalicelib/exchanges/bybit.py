from typing import Optional, Dict, List, Any
from ccxt.base.errors import NetworkError, ExchangeError, RequestTimeout
from decimal import Decimal, ROUND_HALF_UP
import time
import math
import ccxt

from chalicelib import aws_clients, trade_processing
from chalicelib.exceptions import ConnectionError, OrderError

class BybitConnectionError(ConnectionError):
    """Raised when connection to exchange fails."""
    pass

class BybitOrderError(OrderError):
    """Raised when order creation fails."""
    pass

class BybitClient:
    """
    Client for interacting with Bybit cryptocurrency exchange.

    The client handles all interactions with the Bybit exchange including trades,
    balance checks, and order management. Quote currency (e.g., 'USD') must be 
    specified at initialization and will be used as the purchasing currency for all
    trading pairs.

    Attributes:
    RETRY_DELAY: Seconds to wait between API call retries
    DEFAULT_TIMEOUT: Milliseconds to wait for API responses
    quote_currency: Currency used for pricing (e.g., 'USD', 'USDC', 'USDT')
    """

    RETRY_DELAY = 3 # seconds
    DEFAULT_TIMEOUT = 6_000 # milliseconds

    def __init__(self, quote_currency: str):
        self.quote_currency = quote_currency
        self._client: Optional[ccxt.bybit] = None

    @property
    def client(self) -> ccxt.bybit:
        """Get the connected Bybit client."""
        if self._client is None:
            raise BybitConnectionError("Client not connected. Call connect() first.")
        return self._client
    
    def _round_amount(self, amount: float, market: Dict[str, Any]) -> float:
        """Round amount to market precision."""
        precision = market.get("precision", {}).get("amount")
        if precision is None:
            return amount
        
        decimal_places = abs(int(math.log10(precision)))
        decimal_template = f"0.{'0' * decimal_places}"

        return float(
            Decimal(str(amount)).quantize(
                Decimal(decimal_template),
                rounding=ROUND_HALF_UP
            )
        )
    
    
    def _round_price(self, price: float, market: Dict[str, Any]) -> float:
        """Round price to market precision."""
        precision = market.get("precision", {}).get("price")
        if precision is None:
            return price
        
        decimal_places = abs(int(math.log10(precision)))
        decimal_template = f"0.{'0' * decimal_places}"

        return float(
            Decimal(str(price)).quantize(
                Decimal(decimal_template),
                rounding=ROUND_HALF_UP
            )
        )
    
    def connect(
            self, 
            secret_name: str, 
            sandbox: bool=False, 
            max_retries: int=3
    ) -> None:
        """
        Establish connection to Bybit exchange.
        
        Args:
            secret_name: Name of the secret in AWS Secrets Manager
            sandbox: Whether to use sandbox environment
            max_retries: Maximum number of connection attempts
            
        Raises:
            BybitConnectionError: If connection fails after max retries
            ValueError: If credentials are invalid
        """
        for attempt in range(max_retries):
            try:
                api_key_manager = aws_clients.APIKeyManager(secret_name)
                exchange = ccxt.bybit({
                    "apiKey": api_key_manager.api_key,
                    "secret": api_key_manager.api_secret,
                    "timeout": self.DEFAULT_TIMEOUT
                })

                if sandbox:
                    exchange.set_sandbox_mode(True)

                exchange.load_markets()
                self._client = exchange
                return 
            
            except NetworkError as e:
                if attempt == max_retries - 1:
                    raise BybitConnectionError(
                        f"Failed to connect after {max_retries} attempts"
                    ) from e
                time.sleep(self.RETRY_DELAY)

            except ExchangeError as e:
                raise BybitConnectionError(
                    f"Exchange rejected connection: {str(e)}"
                ) from e
            except Exception as e:
                raise BybitConnectionError(f"Unexpected error: {str(e)}") from e
            
    def create_limit_order(
            self, 
            symbol: str, 
            side: str, 
            amount: float, 
            price: float, 
            max_retries: int=3
        ) -> Dict[str, Any]:
        """
        Place a limit order on Bybit exchange.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USD')
            side: Order side ('buy' or 'sell')
            amount: Amount of base currency
            price: Limit price for the order
            max_retries: Maximum number of connection attempts
            
        Returns:
            Dict containing the order details
            
        Raises:
            BybitOrderError: If order creation fails
            ValueError: If parameters are invalid
        """
        try:
            market = self.client.market(symbol)
            amount = self._round_amount(amount, market)
            price = self._round_price(price, market)
        except Exception as e:
            raise ValueError(f"Failed to validate order parameters: {str(e)}") from e

        for attempt in range(max_retries):
            try:
                order = self.client.create_limit_order(
                    symbol=symbol, 
                    side=side, 
                    amount=amount, 
                    price=price
                )
                return order
            
            except RequestTimeout:
                # Check if order was actually placed
                try:
                    orders = self.client.fetch_open_orders(symbol)
                    matching_orders = [
                        order for order in orders if (
                            order["side"] == side and 
                            float(order["amount"]) == amount and
                            float(order["price"]) == price
                        )
                    ]
                    if matching_orders:
                        return matching_orders[0]
                except Exception as e:
                    # If we can't verify, treat as failed attempt
                    if attempt == max_retries - 1:
                        raise OrderError(
                            f"Failed to place order after {max_retries} attempts: {str(e)}"
                        ) from e
                    time.sleep(self.RETRY_DELAY)
            
            except NetworkError as e:
                if attempt == max_retries - 1:
                    raise BybitOrderError(
                        f"Failed to place order after {max_retries} attempts: {str(e)}"
                    ) from e
                time.sleep(self.RETRY_DELAY)
                
            except ExchangeError as e:
                raise BybitOrderError(f"Exchange rejected order: {str(e)}") from e
                
            except Exception as e:
                raise BybitOrderError(f"Unexpected error placing order: {str(e)}") from e
            
    def get_order_status(self, order_id: str, max_retries: int = 3) -> str:
        """
        Get status of a specific order.
        
        Args:
            order_id: Exchange order identifier
            max_retries: Maximum number of connection attempts
            
        Returns:
            Order status string (e.g., 'open', 'closed', 'canceled')
            
        Raises:
            BybitConnectionError: If connection fails after max retries
        """
        for attempt in range(max_retries):
            try:
                return self.client.fetch_order_status(order_id)
            
            except NetworkError as e:
                if attempt == max_retries - 1:
                    raise BybitConnectionError(
                        f"Failed to fetch order status after {max_retries} attempts"
                    ) from e
                time.sleep(self.RETRY_DELAY)
                
            except ExchangeError as e:
                raise BybitConnectionError(f"Failed to fetch status for order {order_id}: {str(e)}") from e
            
    def get_total_base_asset(self, base_asset: str, max_retries: int = 3) -> Optional[Decimal]:
        """
        Get total amount of base asset in account.
        
        Args:
            base_asset: Asset symbol (e.g., "SOL")
            max_retries: Maximum number of connection attempts
            
        Returns:
            Total amount of asset if found, None otherwise
            
        Raises:
            BybitConnectionError: If balance fetch fails after max retries
        """
        for attempt in range(max_retries):
            try:
                balance = self.client.fetch_balance()
                if base_asset not in balance:
                    return None
                    
                return Decimal(str(balance[base_asset].get('total', 0)))
                
            except NetworkError as e:
                if attempt == max_retries - 1:
                    raise BybitConnectionError(
                        f"Failed to fetch balance after {max_retries} attempts"
                    ) from e
                time.sleep(self.RETRY_DELAY)
                
            except ExchangeError as e:
                raise BybitConnectionError(f"Failed to fetch balance: {str(e)}") from e

    def get_last_price(self, symbol: str, max_retries: int = 3) -> Optional[Decimal]:
        """
        Get last trading price for symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USD')
            max_retries: Maximum number of connection attempts
            
        Returns:
            Last traded price if available, None otherwise
            
        Raises:
            ValueError: If symbol is invalid
            BybitConnectionError: If price fetch fails after max retries
        """
        if not isinstance(symbol, str):
            raise ValueError("symbol must be a string")
            
        for attempt in range(max_retries):
            try:
                ticker = self.client.fetch_ticker(symbol)
                if ticker.get("last") is None:
                    return None
                    
                return Decimal(str(ticker["last"]))
                
            except NetworkError as e:
                if attempt == max_retries - 1:
                    raise BybitConnectionError(
                        f"Failed to fetch price after {max_retries} attempts"
                    ) from e
                time.sleep(self.RETRY_DELAY)
                
            except ExchangeError as e:
                raise BybitConnectionError(f"Failed to fetch price: {str(e)}") from e
            
    def get_account_allocation(self, max_retries: int = 3) -> Dict[str, Decimal]:
        """
        Get USD cost basis for each active strategy in account.

        Args:
            max_retries: Maximum number of connection attempts
            
        Returns:
            Dict mapping asset symbols to their USD values
            
        Raises:
            BybitConnectionError: If fetching data fails after max retries
        """
        for attempt in range(max_retries):
            try:
                # Get available quote balance
                balance = self.client.fetch_balance()
                allocations = {
                    self.quote_currency: Decimal(str(
                        balance.get("free", {}).get(self.quote_currency, 0)
                    ))
                }
                
                # Get cost basis for active strategies
                for config in trade_processing.get_active_strategy_configs():
                    symbol = config["exchange_symbol"]
                    base_asset = config["base_asset"]
                    
                    trades = self.get_most_recent_trade(symbol)
                    trade_value = (
                        self.get_trade_value_usd(trades) 
                        if trades else Decimal('0')
                    )
                    allocations[base_asset] = trade_value
                    
                return allocations
                
            except NetworkError as e:
                if attempt == max_retries - 1:
                    raise BybitConnectionError(
                        f"Failed to fetch allocations after {max_retries} attempts"
                    ) from e
                time.sleep(self.RETRY_DELAY)
                
            except ExchangeError as e:
                raise BybitConnectionError(f"Failed to fetch allocations: {str(e)}") from e

    def get_total_usd(self) -> Decimal:
        """
        Get total USD value of account including cost basis of all positions.
        
        Returns:
            Decimal: Total account value in USD
            
        Raises:
            BybitConnectionError: If fetching allocations fails
        """
        allocations = self.get_account_allocation()
        return sum(allocations.values())
            
    def get_most_recent_trade(self, symbol: str, max_retries: int=3) -> List[Dict]:
        """
        Get most recent complete or incomplete trade for symbol.
        
        A trade starts with one or more buys and ends with a sell that closes the position.
        Multiple consecutive buy orders are considered part of the same trade until a sell 
        is encountered.
        
        Args:
            symbol: Trading pair symbol (e.g., 'ETH/USD')
            max_retries: Maximum number of connection attempts
            
        Returns:
            List of trade dictionaries representing the most recent trade
            
        Raises:
            BybitConnectionError: If fetching trades fails after max retries
        """
        for attempt in range(max_retries):
            try:
                trades = self.client.fetch_my_trades(symbol)
                if not trades:
                    return []
                
                prev_trade_side = None
                for i, trade in enumerate(reversed(trades)):
                    side = trade.get("side")
                    if (prev_trade_side == "buy") & (side == "sell"):
                        return trades[-i:] # Return trades after the last sell
                    elif side == "buy":
                        prev_trade_side = "buy"
                    elif side == "sell":
                        prev_trade_side = "sell"

                return trades # Return all if no buy-sell sequence found

            except NetworkError as e:
                if attempt == max_retries - 1:
                    raise BybitConnectionError(
                        f"Failed to fetch trades after {max_retries} attempts"
                    ) from e
                time.sleep(self.RETRY_DELAY)
                
            except ExchangeError as e:
                raise BybitConnectionError(f"Failed to fetch trades: {str(e)}") from e
            
    def get_trade_value_usd(self, trades: List[Dict]) -> Decimal:
        """
        Calculate proportion of original purchase value of trade in USD that is still owned.

        Args:
            trades: A list of order fills for a trade.

        Returns:
            float: Original purchase price of trade in USD that is still owned.
        """
        if not trades:
            return Decimal("0")
        
        trade_value = Decimal("0")
        amount_owned = Decimal("0")
        amount_bought = Decimal("0")

        for trade in trades:
            amount = Decimal(str(trade.get("amount", 0)))
            if trade.get("side") == "buy":
                amount_owned += amount
                amount_bought += amount
                trade_value += Decimal(str(trade.get("cost", 0)))
            elif trade.get("side") == "sell":
                amount_owned -= amount

        if amount_bought == 0:
            return Decimal("0")

        proportion_owned = amount_owned / amount_bought
        return trade_value * round(proportion_owned, 2)