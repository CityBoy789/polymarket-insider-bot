from unittest.mock import AsyncMock

import pytest
from src.fixes.trading_reality import RealisticTradingModel


class MockPolymarketAPI:
    def __init__(self, order_book_data=None):
        self.fetch_order_book = AsyncMock(return_value=order_book_data)

@pytest.mark.asyncio
async def test_small_order_minimal_impact():
    """Test that small orders have minimal market impact"""
    # Mock order book with deep liquidity
    order_book = {
        "asks": [
            {"price": "0.50", "size": "1000"},  # $500 liquidity at 0.50
            {"price": "0.51", "size": "1000"}   # $510 liquidity at 0.51
        ],
        "bids": [
            {"price": "0.49", "size": "1000"}
        ]
    }

    api = MockPolymarketAPI(order_book)
    model = RealisticTradingModel()
    model.latency_seconds = 0 # Disable latency for test speed

    # BUY $50 (Small order)
    price, details = await model.get_executable_price(
        api, token_id="test", side="BUY", size=50.0
    )

    # Base price should be 0.50
    assert details["base_price"] == 0.50

    # Market impact should be 0 because 50 < 500 (first level depth)
    # Actually logic: avg price should be 0.50. 0.50 - 0.50 = 0.
    assert details["market_impact"] == 0.0

    # Slippage (fixed bps) should be 0.50 * 0.002 = 0.001
    assert details["slippage"] == 0.50 * 0.0020

    # Final price logic check
    assert price == 0.50 + 0.0 + (0.50 * 0.0020)

@pytest.mark.asyncio
async def test_large_order_significant_impact():
    """Test that large orders create significant market impact"""
    # Mock order book
    order_book = {
        "asks": [
            {"price": "0.50", "size": "100"},   # $50 liquidity
            {"price": "0.55", "size": "100"},   # $55 liquidity
            {"price": "0.60", "size": "1000"}   # Deep liquidity higher up
        ]
    }

    api = MockPolymarketAPI(order_book)
    model = RealisticTradingModel()
    model.latency_seconds = 0

    # BUY $105 (Exceeds first two levels)
    # Level 1: $50 @ 0.50
    # Level 2: $55 @ 0.55
    # Total so far: $105. It should just clear first two levels.

    price, details = await model.get_executable_price(
        api, token_id="test", side="BUY", size=105.0
    )

    # Calculation:
    # 1. $50 @ 0.50 -> 100 shares
    # 2. $55 @ 0.55 -> 100 shares
    # Total spent: $105. Total shares: 200.
    # Avg Price = 105 / 200 = 0.525

    # Base Price = 0.50
    # Impact = |0.525 - 0.50| = 0.025

    assert abs(details["market_impact"] - 0.025) < 0.0001
    assert details["base_price"] == 0.50

@pytest.mark.asyncio
async def test_sell_side_impact():
    """Test market impact on SELL side"""
    order_book = {
        "bids": [
            {"price": "0.50", "size": "100"}, # $50
            {"price": "0.40", "size": "100"}  # $40
        ]
    }

    api = MockPolymarketAPI(order_book)
    model = RealisticTradingModel()
    model.latency_seconds = 0

    # SELL $90
    # Level 1: $50 @ 0.50 -> 100 shares
    # Remainder: $40.
    # Level 2: $40 @ 0.40 -> 100 shares
    # Total Sold Value: $90. Total Shares Sold: 200.
    # Avg Price = 90 / 200 = 0.45

    # Base Price (Best Bid) = 0.50
    # Impact = |0.45 - 0.50| = 0.05

    price, details = await model.get_executable_price(
        api, token_id="test", side="SELL", size=90.0
    )

    assert abs(details["market_impact"] - 0.05) < 0.0001

    # Final price for SELL = Base - Impact - Slippage
    # 0.50 - 0.05 - (0.50 * 0.002) = 0.45 - 0.001 = 0.449
    # Wait, my logic for sell final price:
    # final_price = base_price - market_impact - slippage

    expected_slippage = 0.50 * 0.002
    expected_price = 0.50 - 0.05 - expected_slippage

    assert abs(price - expected_price) < 0.0001
