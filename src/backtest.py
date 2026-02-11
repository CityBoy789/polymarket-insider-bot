import asyncio
import statistics
from datetime import datetime, timedelta

import aiosqlite
from rich.console import Console
from rich.table import Table

from src.core.config import DATABASE_PATH
from src.core.polymarket_api import PolymarketAPI

console = Console()


class Backtester:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.api = PolymarketAPI()

    async def run(self):
        """Run the backtest analysis"""
        console.print("[bold cyan]🚀 Starting Backtest Analysis...[/bold cyan]")

        # 1. Load Alerts
        alerts = await self._load_alerts()
        if not alerts:
            console.print("[yellow]No alerts found in database.[/yellow]")
            return

        console.print(f"Loaded [bold]{len(alerts)}[/bold] alerts.")

        # 2. Analyze PnL
        results = []
        async with self.api as api:
            # simple loop for now as track with async generator is tricky
            # we can iterate over list normally
            for i, alert in enumerate(alerts):
                console.print(
                    f"Analyzing {i + 1}/{len(alerts)}: {alert.get('market_title', '')[:30]}..."
                )
                pnl_data = await self._analyze_alert(api, alert)
                if pnl_data:
                    results.append(pnl_data)

        # 3. Generate Report
        self._print_report(results)

    async def _load_alerts(self) -> list[dict]:
        """Load all alerts from the database"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM alerts ORDER BY timestamp DESC")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def _analyze_alert(self, api: PolymarketAPI, alert: dict) -> dict | None:
        """Calculate PnL for a single alert"""
        try:
            timestamp_str = alert["timestamp"]
            # Flexible parsing for ISO format
            try:
                alert_time = datetime.fromisoformat(timestamp_str)
            except ValueError:
                # Fallback for simpler formats if any
                return None

            condition_id = alert["condition_id"]
            if not condition_id:
                return None

            entry_price = (
                float(alert["current_price"]) if alert["current_price"] != "Unknown" else 0.5
            )  # Fallback
            if entry_price <= 0:
                return None

            # Time horizons
            horizons = {
                "1h": alert_time + timedelta(hours=1),
                "4h": alert_time + timedelta(hours=4),
                "24h": alert_time + timedelta(hours=24),
            }

            pnl = {}

            # Optimization: Try to fetch a chunk of history instead of 3 separate calls if horizons are close?
            # Or just make 3 fast calls. API rate limit might be an issue.
            # Let's simple fetch: start=T, end=T+24h

            int(alert_time.timestamp())
            int((alert_time + timedelta(hours=25)).timestamp())

            # Fetch trades for the 24h period
            # Note: This might be heavy if many alerts.
            # Limitation: Clob API might not give arbitrary range easily or it might be paginated.
            # safe fetch: fetch small windows around target times

            for name, target_time in horizons.items():
                target_ts = int(target_time.timestamp())
                # Search window: +/- 30 mins
                window_start = target_ts - 1800
                window_end = target_ts + 1800

                trades = await api.fetch_market_trades_history(
                    condition_id, window_start, window_end
                )

                exit_price = entry_price  # Default to break-even/no-change if no data

                if trades:
                    # Find trade closest to target_time
                    # Trades are usually refined.
                    # Assuming trades list has 'timestamp' or 'time'
                    # API returns list of trades.

                    # Sort by distance to target_ts
                    # Trade timestamp from API is usually in seconds or ms.
                    # Need to verify API response format. Assuming seconds for now based on py-clob-client usually.

                    # actually fetch_market_trades_history uses /trades endpoint.

                    closest_trade = min(
                        trades, key=lambda t: abs(int(t.get("timestamp", 0)) - target_ts)
                    )
                    exit_price = float(closest_trade.get("price", entry_price))

                # Calculate ROI
                # Strategy: Long (Buy)
                roi = (exit_price - entry_price) / entry_price
                pnl[name] = roi

            return {"score": alert["suspicion_score"], "pnl": pnl}

        except Exception:
            # console.print(f"[red]Error analyzing alert {alert.get('id')}: {e}[/red]")
            return None

    def _print_report(self, results: list[dict]):
        """Print aggregated stats"""
        if not results:
            console.print("[yellow]No results to report.[/yellow]")
            return

        buckets = {"7.0-8.0": [], "8.0-9.0": [], "9.0+": []}

        for r in results:
            score = r["score"]
            if score >= 9.0:
                buckets["9.0+"].append(r)
            elif score >= 8.0:
                buckets["8.0-9.0"].append(r)
            elif score >= 7.0:
                buckets["7.0-8.0"].append(r)

        table = Table(title="📊 Backtest Results (Strategy: Long/Buy)", show_header=True)
        table.add_column("Score Bucket", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("Avg ROI (1h)", justify="right")
        table.add_column("Avg ROI (4h)", justify="right")
        table.add_column("Avg ROI (24h)", justify="right")
        table.add_column("Win Rate (24h)", justify="right")

        for bucket_name, items in buckets.items():
            if not items:
                table.add_row(bucket_name, "0", "-", "-", "-", "-")
                continue

            count = len(items)

            avg_1h = statistics.mean([x["pnl"]["1h"] for x in items])
            avg_4h = statistics.mean([x["pnl"]["4h"] for x in items])
            avg_24h = statistics.mean([x["pnl"]["24h"] for x in items])

            wins_24h = len([x for x in items if x["pnl"]["24h"] > 0])
            win_rate = (wins_24h / count) * 100

            def color_roi(val):
                return f"[green]+{val:.2%}[/green]" if val > 0 else f"[red]{val:.2%}[/red]"

            table.add_row(
                bucket_name,
                str(count),
                color_roi(avg_1h),
                color_roi(avg_4h),
                color_roi(avg_24h),
                f"{win_rate:.1f}%",
            )

        console.print(table)


if __name__ == "__main__":
    backtester = Backtester()
    asyncio.run(backtester.run())
