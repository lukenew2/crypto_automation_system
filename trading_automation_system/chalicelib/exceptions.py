class ExchangeError(Exception):
    """Base exception for all exchange-related errors."""
    pass

class ConnectionError(ExchangeError):
    """Raised when connection to any exchange fails."""
    pass

class OrderError(ExchangeError):
    """Base exception for order-related errors."""
    pass

class DatabaseError(Exception):
    """Raised when database operations fail."""
    pass

class ConfigError(Exception):
    """Raised when configuration loading or validation fails."""
    pass

class SignalsFetchError(Exception):
    """Raised when fetching signals fails for some tickers."""
    def __init__(self, failed_tickers: dict):
        self.failed_tickers = failed_tickers
        message = f"Failed to fetch signals for tickers: {failed_tickers}"
        super().__init__(message)

class OrderFillError(Exception):
    """Raised when order fill check fails."""
    pass