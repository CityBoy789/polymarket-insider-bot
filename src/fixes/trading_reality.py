"""
Realistic Trading Model

Models real-world trading frictions:
- Market impact (from order book depth)
- Slippage (spread cost)
- Fees
- Latency
"""

import asyncio

from src.core.logger import logger

# Default trading friction parameters
DEFAULT_SLIPPAGE_BPS = 20  # 20 basis points (0.2%)
DEFAULT_FEE_BPS = 10  # 10 basis points (0.1%)
DEFAULT_LATENCY_SECONDS = 2  # Simulated execution delay


class RealisticTradingModel:
    def __init__(self):
        self.slippage_bps = DEFAULT_SLIPPAGE_BPS
        self.fee_bps = DEFAULT_FEE_BPS
        self.latency_seconds = DEFAULT_LATENCY_SECONDS

    async def get_executable_price(
        self, api, token_id: str, side: str, size: float
    ) -> tuple[float, dict]:
        """
        Calculate the realistic execution price given order book depth.

        Args:
            api: PolymarketAPI instance (must have fetch_order_book)
            token_id: Token to trade
            side: "BUY" or "SELL"
            size: Trade size in USD

        Returns:
            (final_price, details_dict)
        """
        # Simulate latency
        if self.latency_seconds > 0:
            await asyncio.sleep(self.latency_seconds)

        # Fetch order book
        order_book = await api.fetch_order_book(token_id)

        if side.upper() == "BUY":
            levels = order_book.get("asks", [])
        else:
            levels = order_book.get("bids", [])

        if not levels:
            raise ValueError(f"No {side} liquidity available for token {token_id}")

        # Determine base price (best available)
        base_price = float(levels[0]["price"])

        # Calculate market impact by walking the order book
        avg_exec_price = self._calculate_avg_execution_price(levels, size)
        market_impact = abs(avg_exec_price - base_price)

        # Calculate slippage (fixed bps on base price)
        slippage = base_price * (self.slippage_bps / 10000)

        # Calculate fee
        fee = base_price * (self.fee_bps / 10000)

        # Final price
        if side.upper() == "BUY":
            final_price = base_price + market_impact + slippage
        else:
            final_price = base_price - market_impact - slippage

        details = {
            "base_price": base_price,
            "avg_exec_price": avg_exec_price,
            "market_impact": market_impact,
            "slippage": slippage,
            "fee": fee,
            "side": side,
            "size_usd": size,
        }

        logger.debug(
            f"Executable price: {final_price:.4f} "
            f"(base={base_price:.4f}, impact={market_impact:.4f}, "
            f"slip={slippage:.4f}, fee={fee:.4f})"
        )

        return final_price, details

    def _calculate_avg_execution_price(self, levels: list[dict], size_usd: float) -> float:
        """
        Walk the order book to calculate volume-weighted average execution price.

        Each level has {"price": "0.50", "size": "100"} where:
        - size = number of shares
        - value at this level = price * size (USD equivalent)
        """
        remaining_usd = size_usd
        total_shares = 0.0
        total_spent = 0.0

        for level in levels:
            level_price = float(level["price"])
            level_size = float(level["size"])
            level_value = level_price * level_size  # USD available at this level

            if remaining_usd <= 0:
                break

            if remaining_usd >= level_value:
                # Consume entire level
                total_shares += level_size
                total_spent += level_value
                remaining_usd -= level_value
            else:
                # Partial fill at this level
                shares_bought = remaining_usd / level_price
                total_shares += shares_bought
                total_spent += remaining_usd
                remaining_usd = 0

        if total_shares == 0:
            return float(levels[0]["price"]) if levels else 0.0

        return total_spent / total_shares
