from typing import List, Dict, Any
from decimal import Decimal
from datetime import datetime
from chalicelib import utils, aws_clients
from chalicelib.exceptions import DatabaseError, SignalsFetchError

def preprocess_trade_signal(trade_signal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process trade signal and enrich with configuration data.
    
    Args:
        trade_signal: Trading signal dictionary containing:
            - ticker: Trading symbol
            - time: Signal timestamp
            - order_action: Buy/Sell action
            - order_price: Price for the order
            
    Returns:
        Processed trade signal with additional configuration attributes
        and decimal conversions
        
    Raises:
        ValueError: If required fields are missing or ticker has no config
    """
    # Validate required fields
    ticker = trade_signal.get("ticker")
    if not ticker:
        raise ValueError("Trade signal missing 'ticker' attribute")
        
    if "time" not in trade_signal:
        raise ValueError("Trade signal missing 'time' attribute")
    
    trade_signal["create_ts"] = trade_signal.pop("time")
        
    # Get and validate config
    configs = utils.load_strategy_config()
    ticker_config = configs.get(ticker, {})
    if not ticker_config:
        raise ValueError(f"No configuration found for ticker '{ticker}'")
    
    # Create new signal with all data
    processed_signal = {
        **trade_signal,
        **ticker_config
    }
    
    return utils.convert_floats_to_decimals(processed_signal)
    
def get_active_strategy_tickers(threshold: Decimal = Decimal('0')) -> List[str]:
   """
   Get tickers of strategies with allocation above threshold.
   
   Args:
       threshold: Minimum percentage allocation for active strategy
           Default is 0, meaning all strategies are considered active
           
   Returns:
       List of ticker symbols for active strategies
       
   Raises:
       ConfigError: If strategy config cannot be loaded or is invalid
   """
   configs = utils.load_strategy_config()  # Raises appropriate errors
       
   return [
       ticker for ticker, config in configs.items()
       if Decimal(str(config.get("percentage", 0))) > threshold
   ]

def get_active_strategy_configs(threshold: Decimal = Decimal('0')) -> List[Dict[str, Any]]:
   """
   Get configuration dictionaries for strategies above allocation threshold.
   
   Args:
       threshold: Minimum percentage allocation for active strategy.
           Default is 0, meaning all strategies are considered active.
           
   Returns:
       List of configuration dictionaries for active strategies.
       Each dictionary contains strategy parameters like:
       - exchange_symbol: Trading pair symbol
       - base_asset: Base currency of the pair
       - percentage: Allocation percentage
       - other strategy-specific parameters
       
   Raises:
       ConfigError: If strategy config cannot be loaded or is invalid
   """
   configs = utils.load_strategy_config()  # Raises appropriate errors
       
   return [
       config for config in configs.values()
       if Decimal(str(config.get("percentage", 0))) > threshold
   ]

def get_ticker_recent_signals(
    ticker: str,
    cutoff_time: datetime,
    table_name: str
) -> List[Dict[str, Any]]:
    """
    Get trade signals for ticker newer than cutoff time.
    
    Queries DynamoDB table for trade signals matching:
    - ticker matches provided symbol
    - create_ts >= cutoff_time
    Results are returned in descending timestamp order.
    
    Args:
        ticker: Trading pair symbol
        cutoff_time: Minimum timestamp for signals
        table_name: DynamoDB table name containing signals
        
    Returns:
        List of trade signal dictionaries ordered by timestamp descending.
        Empty list if no signals found.
        
    Raises:
        DatabaseError: If querying DynamoDB fails
    """
    dynamodb = aws_clients.DynamoDBManager()
    table = dynamodb.get_table(table_name)
    
    try:
        response = table.query(
            KeyConditionExpression="#ticker = :ticker AND #create_ts >= :cutoff_time",
            ExpressionAttributeNames={
                "#ticker": "ticker",
                "#create_ts": "create_ts"
            },
            ExpressionAttributeValues={
                ":ticker": ticker,
                ":cutoff_time": cutoff_time.isoformat()
            },
            ScanIndexForward=False  # Descending order
        )
        return response.get("Items", [])
        
    except Exception as e:
        raise DatabaseError(
            f"Failed to query recent signals for {ticker}: {str(e)}"
        ) from e
    
def get_all_recent_signals(
   cutoff_time: datetime,
   table_name: str,
   threshold: Decimal = Decimal('0')
) -> List[Dict[str, Any]]:
    """
    Get recent trade signals for all active trading strategies.

    Retrieves signals newer than cutoff_time for all tickers with
    allocation percentage above threshold.

    Args:
        cutoff_time: Minimum timestamp for signals
        table_name: DynamoDB table name containing signals
        threshold: Minimum allocation % for active strategies
        
    Returns:
        List of trade signal dictionaries from all active tickers
        
    Raises:
        DatabaseError: If querying signals fails
        ConfigError: If loading strategy config fails
    """
    active_tickers = get_active_strategy_tickers(threshold)
    trade_signals = []
    failed_tickers = {}

    for ticker in active_tickers:
        try:
            signals = get_ticker_recent_signals(ticker, cutoff_time, table_name)
            trade_signals.extend(signals)
        except DatabaseError as e:
            failed_tickers[ticker] = str(e)

    if failed_tickers:
        raise SignalsFetchError(failed_tickers)
            
    return trade_signals