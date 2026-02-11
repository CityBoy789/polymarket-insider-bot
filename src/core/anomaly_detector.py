"""Detect anomalous/suspicious trading patterns"""

import statistics
from collections import defaultdict

from src.core.config import (
    FRESH_WALLET_DAYS,
    LARGE_BET_MULTIPLIER,
    MIN_BET_SIZE,
    MIN_WALLET_CONCENTRATION,
    NICHE_MARKET_VOLUME_THRESHOLD,
)
from src.core.logger import logger


class AnomalyDetector:
    def __init__(self, db):
        self.db = db
        self.baseline = {
            "age_mean": 30.0,
            "age_std": 15.0,
            "volume_mean": 1000.0,
            "volume_std": 500.0,
            "trades_mean": 10.0,
            "trades_std": 5.0,
        }

    async def initialize(self):
        """Calculate statistical baseline from DB"""
        try:
            stats = await self.db.get_baseline_stats()
            if stats and stats.get("wallet_count", 0) >= 10:
                self.baseline["age_mean"] = stats.get("age_mean", self.baseline["age_mean"])
                self.baseline["age_std"] = max(stats.get("age_std", self.baseline["age_std"]), 1.0)
                self.baseline["volume_mean"] = stats.get(
                    "volume_mean", self.baseline["volume_mean"]
                )
                self.baseline["volume_std"] = max(
                    stats.get("volume_std", self.baseline["volume_std"]), 1.0
                )
                self.baseline["trades_mean"] = stats.get(
                    "trades_mean", self.baseline["trades_mean"]
                )
                self.baseline["trades_std"] = max(
                    stats.get("trades_std", self.baseline["trades_std"]), 1.0
                )
                logger.info(
                    f"Baseline initialized from {stats['wallet_count']} wallets: "
                    f"age={self.baseline['age_mean']:.1f}±{self.baseline['age_std']:.1f}, "
                    f"vol={self.baseline['volume_mean']:.0f}±{self.baseline['volume_std']:.0f}"
                )
            else:
                logger.info("Not enough wallet data for baseline, using defaults")
        except Exception as e:
            logger.warning(f"Error initializing baseline, using defaults: {e}")

    async def calculate_score(
        self, address: str, history: list, wallet_stats: dict, trade: dict, market_stats: dict
    ) -> tuple[float, list[str]]:
        """
        Calculate final suspicion score for a trade/wallet.
        """
        score, reasons = self.score_wallet_suspiciousness(wallet_stats, trade, market_stats)

        # Add Z-Score boost
        z_score = self.calculate_anomaly_z_score(wallet_stats)
        if z_score > 2.0:
            score += min(z_score - 2.0, 2.0)  # Cap boost at +2
            reasons.append(f"Statistically anomalous (Z-Score: {z_score:.1f})")

        return float(min(score, 10.0)), reasons

    def calculate_anomaly_z_score(self, wallet_stats: dict) -> float:
        """Calculate statistical anomaly score (Z-Score accumulation)"""
        scores = []

        # Age Anomaly (Younger is suspicious?)
        # Actually user example: absolute deviation.
        # But for 'insider', "Fresh" is suspicious.
        # So (Mean - Age) / Std ?
        # If Age is small, (30 - 1) / 15 = 2.0 sigma.
        age = wallet_stats.get("age_days", 0)
        age_z = (self.baseline["age_mean"] - age) / self.baseline["age_std"]
        if age_z > 0:
            scores.append(age_z)

        # Volume Anomaly (High volume is suspicious if outlier)
        vol = wallet_stats.get("total_volume", 0)
        vol_z = (vol - self.baseline["volume_mean"]) / self.baseline["volume_std"]
        if vol_z > 0:
            # Dampen volume Z because whales exist
            scores.append(vol_z * 0.5)

        if not scores:
            return 0.0

        return statistics.mean(scores)

    def calculate_market_stats(self, trades: list[dict]) -> dict:
        """Calculate statistics for a market"""
        if not trades:
            return {}

        sizes = [float(t.get("size", 0)) * float(t.get("price", 0)) for t in trades]

        return {
            "total_volume": sum(sizes),
            "avg_trade_size": statistics.mean(sizes) if sizes else 0,
            "median_trade_size": statistics.median(sizes) if sizes else 0,
            "std_trade_size": statistics.stdev(sizes) if len(sizes) > 1 else 0,
            "num_trades": len(trades),
            "unique_traders": len({t.get("maker", "") for t in trades}),
        }

    def score_wallet_suspiciousness(
        self, wallet_stats: dict, trade: dict, market_stats: dict
    ) -> tuple[float, list[str]]:
        """
        Score how suspicious a wallet/trade is (0-10 scale)
        Returns (score, list of reasons)
        """
        score = 0.0
        reasons = []

        # Fresh wallet check
        age_days = wallet_stats.get("age_days", 0)
        if age_days < 1:
            score += 2
            reasons.append("Brand new wallet (< 1 day old)")
        elif age_days < FRESH_WALLET_DAYS:
            score += 1
            reasons.append(f"Fresh wallet ({age_days:.1f} days old)")

        # Unusual bet sizing
        trade_size = float(trade.get("size", 0)) * float(trade.get("price", 0))
        avg_size = market_stats.get("avg_trade_size", 0)

        if trade_size > MIN_BET_SIZE:
            if avg_size > 0 and trade_size > avg_size * LARGE_BET_MULTIPLIER:
                score += 3
                reasons.append(f"Unusually large bet: ${trade_size:.0f} (avg: ${avg_size:.0f})")
            elif trade_size > MIN_BET_SIZE * 10:
                score += 2
                reasons.append(f"Very large bet: ${trade_size:.0f}")
            elif trade_size > MIN_BET_SIZE * 5:
                score += 1
                reasons.append(f"Large bet: ${trade_size:.0f}")

        # Market concentration
        concentration = wallet_stats.get("max_market_concentration", 0)
        if concentration >= MIN_WALLET_CONCENTRATION:
            score += 2
            reasons.append(
                f"High market concentration: {concentration * 100:.0f}% of trades in one market"
            )
        elif concentration >= MIN_WALLET_CONCENTRATION * 0.7:
            score += 1
            reasons.append(f"Moderate market concentration: {concentration * 100:.0f}%")

        # Niche market activity
        market_volume = market_stats.get("total_volume", float("inf"))
        if market_volume < NICHE_MARKET_VOLUME_THRESHOLD:
            if market_volume < NICHE_MARKET_VOLUME_THRESHOLD / 5:
                score += 2
                reasons.append(f"Very low liquidity market: ${market_volume:.0f} volume")
            else:
                score += 1
                reasons.append(f"Niche market: ${market_volume:.0f} volume")

        # Repeated aggressive entries
        total_trades = wallet_stats.get("total_trades", 0)
        unique_markets = wallet_stats.get("unique_markets", 1)
        if total_trades > 5 and unique_markets < 3:
            score += 1
            reasons.append(f"Repeated entries: {total_trades} trades in {unique_markets} markets")

        return min(score, 10), reasons

    def detect_coordinated_activity(self, trades: list[dict]) -> list[dict]:
        """Detect potential coordinated wallet activity"""
        time_windows = defaultdict(list)

        for trade in trades:
            ts = trade.get("timestamp", 0)
            window = int(ts / 300) * 300
            time_windows[window].append(trade)

        suspicious_groups = []

        for window, window_trades in time_windows.items():
            if len(window_trades) < 3:
                continue

            sizes = [float(t.get("size", 0)) for t in window_trades]
            avg_size = statistics.mean(sizes) if sizes else 0

            if avg_size > 0:
                similar_size_trades = [
                    t
                    for t in window_trades
                    if abs(float(t.get("size", 0)) - avg_size) / avg_size < 0.1
                ]

                if len(similar_size_trades) >= 3:
                    suspicious_groups.append(
                        {
                            "window": window,
                            "trades": similar_size_trades,
                            "pattern": "similar_sizing",
                            "count": len(similar_size_trades),
                        }
                    )

        return suspicious_groups
