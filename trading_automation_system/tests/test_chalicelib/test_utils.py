from unittest.mock import patch

from chalicelib.utils import get_trade_precedence

def test_get_trade_precedence():
    """Test determining trade precedence based on allocation percentage."""
    
    # Mock config with some equal allocations
    mock_config = {
        "BTC": {
            "exchange_symbol": "BTC/USD",
            "percentage": 50
        },
        "ETH": {
            "exchange_symbol": "ETH/USD",
            "percentage": 30
        },
        "SOL": {
            "exchange_symbol": "SOL/USD",
            "percentage": 30
        }
    }
    
    test_cases = [
        {
            "name": "different allocations",
            "symbols": ["BTC/USD", "ETH/USD"],
            "expected": "BTC/USD"  # Highest allocation (50%)
        },
        {
            "name": "equal allocations",
            "symbols": ["ETH/USD", "SOL/USD"],
            "expected": "ETH/USD"  # Equal allocation (30%), ETH comes first alphabetically
        },
        {
            "name": "single trade",
            "symbols": ["SOL/USD"],
            "expected": "SOL/USD"
        },
        {
            "name": "empty list",
            "symbols": [],
            "expected": None
        }
    ]
    
    with patch('chalicelib.utils.load_strategy_config', return_value=mock_config):
        for case in test_cases:
            result = get_trade_precedence(case["symbols"])
            assert result == case["expected"], \
                f"Failed case '{case['name']}': expected {case['expected']}, got {result}"