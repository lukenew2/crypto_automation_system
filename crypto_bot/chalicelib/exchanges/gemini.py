import time
import logging
import ccxt
from decimal import Decimal
from typing import Union
from chalicelib import utils, trade_processing

logger = logging.getLogger("app")

class GeminiClient:
    def __init__(self):
        self.client = None

    def connect(self, secret_name: str, sandbox: bool=False, max_retries: int=3) -> bool:
        """
        Establishes connection to Gemini exchange.

        Args:
            secret_name: The name of the secret in AWS Secrets Manager.
            sandbox (optional): Determines whether to connect to exchange's sandbox env.
            max_retries (optional): Maximum number of retries. Defaults to 3.

        Returns:
            bool: True if connection is successful, False otherwise.
        """
        retries = 0
        while retries < max_retries:
            try:
                api_key_manager = utils.APIKeyManager(secret_name)
                api_key = api_key_manager.get_api_key()
                api_secret = api_key_manager.get_api_secret()

                exchange = ccxt.gemini({
                    "apiKey": api_key,
                    "secret": api_secret,
                    "timeout": 6_000
                })
                if sandbox:
                    exchange.set_sandbox_mode(True)

                exchange.load_markets()

                self.client = exchange
                return True
            
            except ccxt.NetworkError as e:
                logging.error(f"Connection failed due to Network error: {str(e)}. Retrying the call.")
                time.sleep(3)
                retries +=1 

            except ccxt.ExchangeError as e:
                logging.error(f"Exchange error while connecting: {e}")
                return False
            except Exception as e:
                logging.error(f"An unexpected error occurred: {e}")
                raise e
            
        logging.error(f"Failed to connect to exchange after {max_retries} retries.")
        return False

    def create_limit_order(self, symbol: str, side: str, amount: float, order_price: float, max_retries: int=3):
        """
        Places a limit buy order on the Gemini exchange.

        Args:
            exchange: The exchange object from ccxt.
            symbol: The symbol representing the trading pair.
            side: 'buy' or 'sell'.
            amount: Amount of currency to buy
            order_price: Price to place sell order at.
            max_retries: Maximum number of retry attempts. Defaults to 3.

        Returns:
            dict or None: The order object if the order was successfully placed,
            or None if an error occurred.
        """
        retries = 0
        while retries < max_retries:
            try:
                order = self.client.create_limit_order(symbol, side, amount, order_price)
                return order
            
            except ccxt.NetworkError as e:
                if e == ccxt.RequestTimeout:
                    # Check if the order was placed
                    orders = self.client.fetch_open_orders(symbol)
                    if orders:
                        logging.info(f"RequestTimeout occurred: Confirmed buy order placed by fetching open orders.")
                        return orders[0]
                
                # Increment retry count
                logging.warning(f"Place sell failed due to network error: {str(e)}. Retrying the call.")
                time.sleep(3)  # Adding a delay before retrying
                retries += 1
            
            except ccxt.ExchangeError as e:
                logging.error(f"Exchange error occurred: {e}")
                return None
        
            except Exception as e:
                logging.error(f"An unexpected error occurred: {e}")
                raise e

        logging.error(f"Failed to place sell order after {max_retries} retries.")
        return None
        
    def get_total_currency(self, currency: str, max_retries: int=3) -> Union[float, None]:
        """
        Get the total amount of a given currency owned by the account.

        Args:
            exchange: The exchange object from ccxt.
            currency: The currency symbol to retrieve from the account balance.
            max_retries (optional): Maximum number of retries. Defaults to 3.

        Returns:
            Total number of the given currency owned by the account, or None if not found.
        """
        retries = 0
        while retries < max_retries:
            try:
                # Fetch account balance
                balance = self.client.fetch_balance()
                
                # Check if the currency exists in the balance
                if currency in balance:
                    total_currency = balance[currency].get("total", 0)
                    return Decimal(str(total_currency))
                else:
                    # Currency not found in the balance
                    logger.warning(f"Currency '{currency}' not found in the account balance.")
                    return None
            
            except ccxt.NetworkError as e:
                logger.error(f"{self.client.id} fetch_balance failed due to a network error: {str(e)}")
                time.sleep(3)
                retries += 1
            
            except ccxt.ExchangeError as e:
                logger.error(f"{self.client.id} fetch_balance failed due to user error: {str(e)}")
                return None
            
            except Exception as e:
                logger.exception(f"{self.client.id} fetch_balance failed with: {str(e)}")
                raise e
        
        # If retry limit is reached
        logger.error(f"Failed to fetch account balance after {max_retries} retries.")
        return None
    
    def get_bid_ask(self, symbol: str, max_retries: int=3) -> tuple:
        """
        Get bid ask spread of symbol on exchange.

        Args:
            exchange: The exchange object from ccxt.
            symbol: Uppercase string literal name of a pair of traded currencies 
            with a slash in between.
            max_retries (optional): Maximum number of retries. Defaults to 3.

        Returns:
            Tuple containing current bid and ask price of symbol on exchange.
            If fetching the ticker fails, returns None for both bid and ask.
        """
        retries = 0
        while retries < max_retries:
            try:
                # Validate inputs
                if not isinstance(self.client, ccxt.Exchange):
                    raise ValueError("exchange must be a valid ccxt.Exchange object")
                if not isinstance(symbol, str):
                    raise ValueError("symbol must be a string")

                # Fetch ticker
                ticker = self.client.fetch_ticker(symbol)

                bid = Decimal(str(ticker.get("bid"))) if ticker.get("bid") is not None else None
                ask = Decimal(str(ticker.get("ask"))) if ticker.get("ask") is not None else None

                return bid, ask

            except ccxt.NetworkError as e:
                logging.error(f"Network error while fetching ticker: {e}")
                time.sleep(3)
                retries += 1

            except ccxt.ExchangeError as e:
                logging.error(f"Exchange error while fetching ticker: {e}")
                return None, None
            
            except Exception as e:
                logging.error(f"An unexpected error occurred: {e}")
                raise e
            
        # If retry limit is reached
        logger.error(f"Failed to fetch ticker after {max_retries} retries.")
        return None, None

    def get_last_price(self, symbol: str, max_retries: int=3) -> tuple:
        """
        Get bid ask spread of symbol on exchange.

        Args:
            exchange: The exchange object from ccxt.
            symbol: Uppercase string literal name of a pair of traded currencies 
            with a slash in between.
            max_retries (optional): Maximum number of retries. Defaults to 3.

        Returns:
            Tuple containing current bid and ask price of symbol on exchange.
            If fetching the ticker fails, returns None for both bid and ask.
        """
        retries = 0
        while retries < max_retries:
            try:
                # Validate inputs
                if not isinstance(self.client, ccxt.Exchange):
                    raise ValueError("exchange must be a valid ccxt.Exchange object")
                if not isinstance(symbol, str):
                    raise ValueError("symbol must be a string")

                # Fetch ticker
                ticker = self.client.fetch_ticker(symbol)

                last = Decimal(str(ticker.get("last"))) if ticker.get("last") is not None else None

                return last

            except ccxt.NetworkError as e:
                logging.error(f"Network error while fetching ticker: {e}")
                time.sleep(3)
                retries += 1

            except ccxt.ExchangeError as e:
                logging.error(f"Exchange error while fetching ticker: {e}")
                return None
            
            except Exception as e:
                logging.error(f"An unexpected error occurred: {e}")
                raise e
            
        # If retry limit is reached
        logger.error(f"Failed to fetch ticker after {max_retries} retries.")
        return None

    def get_total_usd(self, max_retries: int=3) -> float:
        """
        Get total USD value of account before any unrealized trades.

        This function allows us to correctly allocate funds to a given strategy.

        Args:
            exchange: Gemini exchange object from ccxt.
        
        Returns
            Total funds of account in USD.
        """
        retries = 0
        while retries < max_retries:
            try:
                balance = self.client.fetch_balance()
                total_funds_usd = balance.get("total").get("USD")
                active_configs = trade_processing.get_active_strategy_configs()
                for config in active_configs:
                    symbol = config.get("symbol")
                    trades = self.client.fetch_my_trades(symbol)
                    for trade in reversed(trades):
                        if trade.get("side") == "sell":
                            break
                        else:
                            trade_value_usd = trade.get("cost") + trade.get("fee").get("cost")
                            total_funds_usd += trade_value_usd
                return Decimal(str(total_funds_usd))
            
            except ccxt.NetworkError as e:
                logging.error(f"Network error while fetching ticker: {e}")
                time.sleep(3)
                retries += 1

            except ccxt.ExchangeError as e:
                logging.error(f"Exchange error while fetching ticker: {e}")
                return None, None
            
            except Exception as e:
                logging.error(f"An unexpected error occurred: {e}")
                raise e