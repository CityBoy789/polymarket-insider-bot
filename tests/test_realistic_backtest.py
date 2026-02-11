from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.fixes.realistic_backtest import RealisticBacktester


@pytest.mark.asyncio
async def test_no_lookahead_bias():
    """Test that execution price differs from alert price (latency/slippage)"""
    backtester = RealisticBacktester()

    # Mock Alert
    alert = {
        "id": "test_1",
        "timestamp": datetime.now().isoformat(),
        "current_price": 0.50,
        "condition_id": "0x123",
        "suspicion_score": 8.5,
        "trade": {"value_usd": 100}
    }

    # Mock API for exit price
    backtester.api = AsyncMock()
    backtester.api.fetch_market_trades_history.return_value = [] # Return empty to trigger fallback or mock real trades

    # Run single alert backtest
    # We patch random.gauss to ensure deterministic drift or check range
    with patch("random.gauss", return_value=0.01): # 1% drift UP
        result = await backtester._backtest_single_alert(alert)

    assert result is not None

    # Verification
    # Alert Price: 0.50
    # Drift: +1% -> 0.505
    # Slippage: +0.2% -> 0.505 * 1.002 = 0.50601

    execution_price = result["execution_details"]["execution_price"]
    entry_price = result["pnl"]["24h"]["entry_price"]

    assert execution_price == 0.505
    assert entry_price > execution_price # Entry includes slippage
    assert entry_price > 0.50 # Definitely changed from alert price

@pytest.mark.asyncio
async def test_train_test_split():
    """Test that data is split correctly"""
    backtester = RealisticBacktester()
    backtester.min_samples = 1 # Lower for test

    # Create 10 mock alerts sorted by time
    alerts = [
        {"timestamp": (datetime.now() + timedelta(days=i)).isoformat(), "id": i}
        for i in range(10)
    ]

    # Mock _load_alerts
    backtester._load_alerts = AsyncMock(return_value=alerts)

    # Mock internal methods to avoid API calls
    backtester._backtest_single_alert = AsyncMock(return_value={"score": 8.0, "pnl": {}})
    backtester._print_report = MagicMock()

    # Run
    await backtester.run_realistic_backtest()

    # Check split
    # 70% train = 7 items. 30% test = 3 items.
    # The backtester runs on TEST set (last 3).

    assert backtester._backtest_single_alert.call_count == 3
