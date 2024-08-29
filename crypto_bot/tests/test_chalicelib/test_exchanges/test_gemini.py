import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal
from chalicelib.exchanges.gemini import GeminiClient

def test_get_most_recent_trade():
    exchange = GeminiClient()
    exchange.client = MagicMock()
    exchange.client.fetch_my_trades.side_effect = [
        [
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 500, 'amount': 0.156192},
            {'symbol': 'ETH/USD', 'side': 'sell', 'price': 3679.36, 'cost': 500, 'amount': 0.156192},
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 2000, 'amount': 1.15}
        ],
        [
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 500, 'amount': 0.156192},
            {'symbol': 'ETH/USD', 'side': 'sell', 'price': 3679.36, 'cost': 500, 'amount': 0.156192},
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 2000, 'amount': 1.15},
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 200, 'amount': 0.15}
        ],
        [
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 500, 'amount': 0.156192},
            {'symbol': 'ETH/USD', 'side': 'sell', 'price': 3679.36, 'cost': 500, 'amount': 0.156192},
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 2000, 'amount': 1.15},
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 200, 'amount': 0.115},
            {'symbol': 'ETH/USD', 'side': 'sell', 'price': 3679.36, 'cost': 1000, 'amount': 0.55},
        ],
        [   
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 500, 'amount': 0.156192},
            {'symbol': 'ETH/USD', 'side': 'sell', 'price': 3679.36, 'cost': 500, 'amount': 0.156192},
        ],
        []
    ]   
    expected_results = [
        [
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 2000, 'amount': 1.15}
        ],
        [
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 2000, 'amount': 1.15},
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 200, 'amount': 0.15}
        ],
        [
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 2000, 'amount': 1.15},
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 200, 'amount': 0.115},
            {'symbol': 'ETH/USD', 'side': 'sell', 'price': 3679.36, 'cost': 1000, 'amount': 0.55},
        ],
        [   
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 500, 'amount': 0.156192},
            {'symbol': 'ETH/USD', 'side': 'sell', 'price': 3679.36, 'cost': 500, 'amount': 0.156192},
        ],
        []
    ]
    for expected_result in expected_results:
        result = exchange.get_most_recent_trade('ETH/USD')
        assert result == expected_result

def test_get_trade_value_usd():
    exchange = GeminiClient()

    trades = [
        [
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 2000, 'amount': 1.15}
        ],
        [
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 2000, 'amount': 1.15},
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 200, 'amount': 0.115}
        ],
        [
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 2000, 'amount': 1.15},
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 200, 'amount': 0.115},
            {'symbol': 'ETH/USD', 'side': 'sell', 'price': 3679.36, 'cost': 1200, 'amount': 0.55},
        ],
        [   
            {'symbol': 'ETH/USD', 'side': 'buy', 'price': 3359.31, 'cost': 500, 'amount': 0.156192},
            {'symbol': 'ETH/USD', 'side': 'sell', 'price': 3679.36, 'cost': 500, 'amount': 0.156192},
        ],
    ]
    expected_results = [2000, 2200, 1254, 0]
    for trade, expected_result in zip(trades, expected_results):
        result = exchange.get_trade_value_usd(trade)
        assert result == expected_result
