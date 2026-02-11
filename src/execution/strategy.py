"""
Copy Trading Strategy

Decides whether to follow a suspicious wallet's trade based on:
- Alert score threshold
- Wallet performance metrics
- Risk limits
"""

import os

from src.core.logger import logger

# Read from environment; defaults to False (safety first)
COPY_TRADING_ENABLED = os.getenv("COPY_TRADING_ENABLED", "false").lower() == "true"

# Strategy thresholds
MIN_SCORE_TO_FOLLOW = 7.0
MIN_WIN_RATE = 0.55
MAX_CONCURRENT_POSITIONS = 5
MAX_SINGLE_POSITION_USD = 500


class CopyTradingStrategy:
    def __init__(self):
        self.active_positions = 0
        self.max_concurrent = MAX_CONCURRENT_POSITIONS
        self.max_position_usd = MAX_SINGLE_POSITION_USD

    def should_follow(self, alert: dict) -> bool:
        """
        Decide whether to copy a flagged wallet's trade.

        Args:
            alert: Alert dict with suspicion_score, wallet_stats, trade info

        Returns:
            True if the trade should be followed
        """
        if not COPY_TRADING_ENABLED:
            logger.debug("Copy trading disabled")
            return False

        score = alert.get("suspicion_score", 0)
        if score < MIN_SCORE_TO_FOLLOW:
            logger.debug(f"Score {score} below threshold {MIN_SCORE_TO_FOLLOW}")
            return False

        # Check wallet quality
        wallet_stats = alert.get("wallet_stats", {})
        win_rate = wallet_stats.get("win_rate", 0)
        if win_rate < MIN_WIN_RATE:
            logger.debug(f"Win rate {win_rate} below threshold {MIN_WIN_RATE}")
            return False

        # Check risk limits
        if not self.check_risk_limits():
            return False

        logger.info(f"Following trade: score={score}, win_rate={win_rate}")
        return True

    def check_risk_limits(self) -> bool:
        """
        Check if we're within risk limits.

        Returns:
            True if within limits
        """
        if self.active_positions >= self.max_concurrent:
            logger.warning(
                f"Max concurrent positions reached ({self.active_positions}/{self.max_concurrent})"
            )
            return False

        return True
