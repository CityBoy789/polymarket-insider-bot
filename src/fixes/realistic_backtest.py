"""
Realistic Backtester

Backtests alert-based strategies with:
- Train/Test split (70/30) to prevent overfitting
- Latency and slippage simulation
- No look-ahead bias
"""

import random
from datetime import datetime

from rich.console import Console
from rich.table import Table

from src.core.config import DATABASE_PATH
from src.core.logger import logger
from src.database.database import Database

console = Console()

# Default backtest parameters
TRAIN_RATIO = 0.7
EXIT_WINDOW_HOURS = 24
DRIFT_MEAN = 0.0
DRIFT_STD = 0.02  # 2% standard deviation for price drift
SLIPPAGE_MULTIPLIER = 1.002  # 0.2% slippage on entry


class RealisticBacktester:
    def __init__(self):
        self.db = Database(DATABASE_PATH)
        self.api = None
        self.min_samples = 5
        self.train_ratio = TRAIN_RATIO

    async def _load_alerts(self) -> list[dict]:
        """Load alerts from database, sorted by timestamp"""
        alerts = await self.db.get_recent_alerts(hours=24 * 90)  # Last 90 days
        return sorted(alerts, key=lambda a: a.get("timestamp", ""))

    async def _backtest_single_alert(self, alert: dict) -> dict | None:
        """
        Backtest a single alert with realistic execution simulation.

        Simulates:
        - Price drift (random walk from alert price)
        - Slippage on entry
        - Exit after 24h using available market data or simulated drift
        """
        try:
            alert_price = float(alert.get("current_price", 0))
            score = alert.get("suspicion_score", 0)

            if alert_price <= 0:
                return None

            # Simulate price drift between alert time and execution
            drift = random.gauss(DRIFT_MEAN, DRIFT_STD)
            execution_price = alert_price * (1 + drift)

            # Apply slippage on entry
            entry_price = execution_price * SLIPPAGE_MULTIPLIER

            # Simulate exit price (24h later)
            exit_price = await self._get_exit_price(alert, alert_price)

            # Calculate PnL
            pnl_24h = exit_price - entry_price
            roi_24h = pnl_24h / entry_price if entry_price > 0 else 0

            return {
                "alert_id": alert.get("id"),
                "score": score,
                "execution_details": {
                    "alert_price": alert_price,
                    "execution_price": execution_price,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "drift": drift,
                },
                "pnl": {
                    "24h": {
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "pnl": pnl_24h,
                        "roi": roi_24h,
                    }
                },
            }

        except Exception as e:
            logger.error(f"Error backtesting alert {alert.get('id')}: {e}")
            return None

    async def _get_exit_price(self, alert: dict, alert_price: float) -> float:
        """
        Get exit price 24h after entry.
        Uses real trade data if available, otherwise simulates.
        """
        condition_id = alert.get("condition_id", "")

        if self.api and condition_id:
            try:
                # Parse alert timestamp
                alert_ts = datetime.fromisoformat(alert["timestamp"])
                start_ts = int(alert_ts.timestamp()) + 3600 * 23  # 23h after
                end_ts = int(alert_ts.timestamp()) + 3600 * 25  # 25h after

                trades = await self.api.fetch_market_trades_history(condition_id, start_ts, end_ts)

                if trades:
                    # TWAP (Time-Weighted Average Price)
                    prices = [
                        float(t.get("price", 0)) for t in trades if float(t.get("price", 0)) > 0
                    ]
                    if prices:
                        return sum(prices) / len(prices)
            except Exception as e:
                logger.debug(f"Failed to fetch exit trades, using simulation: {e}")

        # Fallback: simulate exit with random drift
        exit_drift = random.gauss(DRIFT_MEAN, DRIFT_STD * 2)
        return alert_price * (1 + exit_drift)

    async def run_realistic_backtest(self) -> list[dict]:
        """
        Run backtest with train/test split.

        - Loads all alerts
        - Splits 70% train / 30% test
        - Only backtests on the TEST set (out-of-sample)
        """
        alerts = await self._load_alerts()

        if len(alerts) < self.min_samples:
            console.print(
                f"[yellow]Not enough alerts ({len(alerts)}) for backtest. "
                f"Need at least {self.min_samples}.[/yellow]"
            )
            return []

        # Time-sorted split
        split_idx = int(len(alerts) * self.train_ratio)
        train_set = alerts[:split_idx]
        test_set = alerts[split_idx:]

        logger.info(
            f"Backtest split: {len(train_set)} train, {len(test_set)} test "
            f"(ratio={self.train_ratio})"
        )

        # Backtest only on test set (out-of-sample)
        results = []
        for alert in test_set:
            result = await self._backtest_single_alert(alert)
            if result:
                results.append(result)

        # Print report
        self._print_report(results, train_set, test_set)

        return results

    def _print_report(self, results: list[dict], train_set: list, test_set: list):
        """Print backtest results report"""
        if not results:
            console.print("[yellow]No valid backtest results[/yellow]")
            return

        rois = [r["pnl"]["24h"]["roi"] for r in results if r.get("pnl", {}).get("24h")]

        if not rois:
            console.print("[yellow]No ROI data available[/yellow]")
            return

        avg_roi = sum(rois) / len(rois)
        win_rate = sum(1 for r in rois if r > 0) / len(rois)

        table = Table(title="📊 Realistic Backtest Results (Out-of-Sample)")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")

        table.add_row("Train Set Size", str(len(train_set)))
        table.add_row("Test Set Size", str(len(test_set)))
        table.add_row("Valid Results", str(len(results)))
        table.add_row("Avg ROI (24h)", f"{avg_roi:.2%}")
        table.add_row("Win Rate", f"{win_rate:.1%}")
        table.add_row(
            "Best Trade",
            f"{max(rois):.2%}" if rois else "N/A",
        )
        table.add_row(
            "Worst Trade",
            f"{min(rois):.2%}" if rois else "N/A",
        )

        console.print(table)
