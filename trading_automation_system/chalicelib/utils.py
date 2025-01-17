import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timezone

from chalicelib.exceptions import ConfigError

STRATEGY_CONFIG_PATH = Path("chalicelib/strategy_config.json") #TODO: Find correct place for this

class ConfigFileNotFoundError(ConfigError):
    """Raised when the configuration file cannot be found."""
    pass

class ConfigParseError(ConfigError):
    """Raised when the configuration file cannot be parsed."""
    pass
            
def get_env_var(name: str, default_value: bool | None = None) -> bool:
    """Gets environment variable and returns as boolean."""
    true_ = ("true", "True")
    false_ = ("false", "False")  
    value: str | None = os.environ.get(name, None)
    if value is None:
        if default_value is None:
            raise ValueError(f'Variable `{name}` not set!')
        else:
            value = str(default_value)
    if value.lower() not in true_ + false_:
        raise ValueError(f'Invalid value `{value}` for variable `{name}`')
    return value in true_

def load_strategy_config() -> Dict[str, Any]:
    """
    Load strategy configuration from JSON file.
    
    Returns:
        Dict[str, Any]: The strategy configuration dictionary.
        
    Raises:
        ConfigFileNotFoundError: If the config file doesn't exist.
        ConfigParseError: If the config file contains invalid JSON.
    """
    try:
        with open(STRATEGY_CONFIG_PATH) as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise ConfigFileNotFoundError(
            f"Strategy configuration file not found at {STRATEGY_CONFIG_PATH}"
        ) from e
    except json.JSONDecodeError as e:
        raise ConfigParseError(
            f"Invalid JSON in strategy configuration file: {e.msg} at line {e.lineno}, column {e.colno}"
        ) from e

def convert_floats_to_decimals(data):
    """
    Recursively converts float values and numbers formatted as strings to 
    Decimal in a dictionary.

    Args:
        data: Dictionary containing float values and numbers formatted as 
        strings.

    Returns:
        Dictionary with float values and numbers formatted as strings converted 
        to Decimal.
    """
    if isinstance(data, dict):
        return {key: convert_floats_to_decimals(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_floats_to_decimals(item) for item in data]
    elif isinstance(data, float) or (isinstance(data, str) and data.replace(".", "", 1).isdigit()):
        return Decimal(str(data))
    else:
        return data

def get_utc_now_rounded():
    """Gets current time in utc rounded down to the hour."""
    utcnow = datetime.now(timezone.utc)
    return utcnow.replace(minute=0, second=0, microsecond=0)

def get_exchange_symbol_from_base_asset(base_asset):
    """Get the symbol from currency defined in strategy_config.json"""
    strategy_config_dict = load_strategy_config()
    for _, value in strategy_config_dict.items():
        if value.get("base_asset") == base_asset:
            return value.get("exchange_symbol")
        
def get_base_asset_from_exchange_symbol(exchange_symbol):
    """Get the currency from symbol defined in strategy_config.json"""
    strategy_config_dict = load_strategy_config()
    for _, value in strategy_config_dict.items():
        if value.get("exchange_symbol") == exchange_symbol:
            return value.get("base_asset")
        
def get_percentage_from_exchange_symbol(exchange_symbol):
    """Get the percentage from symbol defined in strategy_config.json"""
    strategy_config_dict = load_strategy_config()
    for _, value in strategy_config_dict.items():
        if value.get("exchange_symbol") == exchange_symbol:
            return Decimal(str(value.get("percentage", 0)))
        
def get_total_allocation_pct() -> Decimal:
    """Get total configured allocation pct to strategies on given asset type."""
    strategy_config_dict = load_strategy_config()
    total_config_allocation_pct = sum([
        strategy.get("percentage", 0) 
        for strategy in strategy_config_dict.values() 
    ])
    
    return Decimal(str(total_config_allocation_pct))

def get_trade_precedence(trade_symbols: List[str]) -> Optional[str]:
   """
   Get symbol with highest allocation percentage from list of trades.
   
   When multiple trades have the same highest allocation percentage,
   returns the first symbol alphabetically to ensure consistency.
   
   Args:
       trade_symbols: List of trading pair symbols (e.g., ['BTC/USD', 'ETH/USD'])
       
   Returns:
       Symbol with highest allocation percentage, or None if list is empty
       
   Raises:
       ConfigError: If loading strategy config fails
   """
   if not trade_symbols:
       return None

   # Group symbols by their allocation percentage    
   symbols_by_allocation = {}
   for symbol in trade_symbols:
       percentage = get_percentage_from_exchange_symbol(symbol)
       symbols_by_allocation.setdefault(percentage, []).append(symbol)
   
   if not symbols_by_allocation:
       return None
       
   # Get highest allocation percentage
   max_percentage = max(symbols_by_allocation.keys())
   
   # If multiple symbols have the same allocation, return first alphabetically
   return min(symbols_by_allocation[max_percentage])