from typing import List
from datetime import datetime
from chalicelib import utils

def preprocess_trade_signal(trade_signal: dict) -> dict:
    """
    Processes incoming trade signals before writing to database.

    Args:
        trade_signal: Json serialized object representing a trade that 
        contains the keys 'ticker', 'time', 'order_action' and 'order_price'.
        
    Returns:
        JSON object containing attributes required in database.

    Raises:
        ValueError: When trade signal is missing 'ticker' or 'time' attribute or
        no configuration found the the ticker.
    """
    try:   
        # Ensure required attributes exist
        configs = utils.get_strategy_config()
        ticker = trade_signal.get("ticker")
        if not ticker:
            raise ValueError("Trade signal missing 'ticker' attribute.")
        
        ticker_config = configs.get(ticker)
        if not ticker_config:
            raise ValueError(f"No configuration found for ticker '{ticker}'.")
        
        if "time" not in trade_signal:
            raise ValueError("Trade signal missing 'time' attribute")
        trade_signal["create_ts"] = trade_signal.pop("time")

        # Add features from configuration file
        for attribute, value in ticker_config.items():
            trade_signal[attribute] = value
        
        trade_signal = utils.convert_floats_to_decimals(trade_signal)

        return trade_signal

    except ValueError as e:
        raise e
    
def get_active_strategy_tickers(threshold: float=0) -> List:
    """
    Get tickers of active strategies based on a percentage threshold.

    Args:
        threshold: The minimum percentage threshold for a strategy to be 
        considered active.

    Returns:
        list: List of tickers for active strategies.
    """
    try:
        configs = utils.get_strategy_config()
    except Exception as e:
        print(f"Error retrieving strategy configs: {e}")
        return []

    if not isinstance(configs, dict):
        print("Strategy configurations should be provided as a dictionary.")
        return []

    active_tickers = [
        ticker for ticker, config in configs.items() 
        if config.get("percentage", 0) > threshold
    ]
    return active_tickers

def get_active_strategy_configs(threshold: float=0) -> List:
    """
    Get configs of active strategies based on a percentage threshold.

    Args:
        threshold: The minimum percentage threshold for a strategy to be 
        considered active.

    Returns:
        list: List of currencies for active strategies.
    """
    try:
        configs = utils.get_strategy_config()
    except Exception as e:
        print(f"Error retrieving strategy configs: {e}")
        return []

    if not isinstance(configs, dict):
        print("Strategy configurations should be provided as a dictionary.")
        return []

    config_dicts = [
        config_dict for config_dict in configs.values() 
        if config_dict.get("percentage", 0) > threshold
    ]
    return config_dicts

def get_ticker_recent_signals(ticker: str, cutoff_time: datetime, table_name: str) -> List:
    """
    Retrieves trade signals for a given ticker that are newer than cutoff_time.

    Args:
        ticker: Symbol representing a market on TradingView.
        cutoff_time: Filters trade signals by their create_ts >= cutoff_time.
        table_name: Name of DynamoDB table that stores trade signals

    Returns:
        List of JSON objects containing trades that meet the criteria.  If no 
        trades meet criteria returns an empty list.
    """
    try:
        dynamodb_manager = utils.DynamoDBManager()
        table = dynamodb_manager.get_table(table_name)
        response = table.query(
            KeyConditionExpression="#ticker = :ticker AND #create_ts >= :cutoff_time",
            ExpressionAttributeNames={
                "#ticker": "ticker",
                "#create_ts": "create_ts"
            },
            ExpressionAttributeValues={
                ":ticker": ticker,
                ":cutoff_time": cutoff_time.isoformat()  # Convert datetime to ISO 8601 format
            },
            ScanIndexForward=False  # To get results in descending order of create_ts
        )
        items = response.get("Items", [])

        return items
    
    except Exception as e:
        raise RuntimeError(f"An unexpected error occured: {e}")
    
def get_all_recent_signals(cutoff_time: datetime, table_name: str) -> List:
    """
    Get all recent trade signals for active strategies newer than the cutoff time.

    Args:
        cutoff_time: The cutoff time for retrieving recent signals.
        table_name: The name of the table where recent signals are stored.

    Returns:
        list: List of recent trade signals for active strategies.
    """
    try:
        active_tickers = get_active_strategy_tickers()
        trade_signals = []
        for ticker in active_tickers:
            trade_signals += get_ticker_recent_signals(ticker, cutoff_time, table_name)
        return trade_signals
    except Exception as e:
        print(f"Error in retrieving recent signals: {e}")
        return []