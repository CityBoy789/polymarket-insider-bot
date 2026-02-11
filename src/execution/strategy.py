"""Copy Trading Strategy Logic"""

from datetime import datetime

from src.core.config import (
    COPY_TRADING_ENABLED,
    DAILY_LOSS_LIMIT,
    MAX_BET_AMOUNT,
    STRATEGY_MIN_SCORE,
    STRATEGY_MIN_WIN_RATE,
)
from src.core.logger import logger


class CopyTradingStrategy:
    def __init__(self):
        self.daily_loss = 0.0
        self.last_reset = datetime.now().date()

    def check_risk_limits(self) -> bool:
        """
        Check if trading is allowed based on risk limits.
        """
        # Reset daily loss if it's a new day
        current_date = datetime.now().date()
        if current_date > self.last_reset:
            self.daily_loss = 0.0
            self.last_reset = current_date

        if self.daily_loss >= DAILY_LOSS_LIMIT:
            logger.warning(
                f"Daily loss limit reached: ${self.daily_loss:.2f} >= ${DAILY_LOSS_LIMIT:.2f}"
            )
            return False

        return True

    def should_follow(self, alert: dict) -> bool:
        """
        Determine if we should follow an alert based on strategy rules.
        """
        if not COPY_TRADING_ENABLED:
            return False

        if not self.check_risk_limits():
            return False

        # Extract metrics
        score = alert.get("suspicion_score", 0)
        wallet_stats = alert.get("wallet_stats", {})
        win_rate = wallet_stats.get("win_rate", 0)

        # Strategy Logic
        if score < STRATEGY_MIN_SCORE:
            logger.info(f"Skipping alert: Score {score:.1f} < Min {STRATEGY_MIN_SCORE:.1f}")
            return False

        if win_rate < STRATEGY_MIN_WIN_RATE:
            logger.info(
                f"Skipping alert: Win Rate {win_rate:.2f} < Min {STRATEGY_MIN_WIN_RATE:.2f}"
            )
            return False

        return True

    def calculate_position_size(self, alert: dict) -> float:
        """
        Calculate position size for the trade.
        For now, we use a fixed max bet or match current trade if smaller.
        """
        trade_data = alert.get("trade", {})
        trade_value = trade_data.get("value_usd", 0)

        # Cap at MAX_BET_AMOUNT
        position_size = min(trade_value, MAX_BET_AMOUNT)

        return position_size

    def record_loss(self, loss_amount: float):
        """Record a realized loss to update daily stats"""
        if loss_amount > 0:
            self.daily_loss += loss_amount
