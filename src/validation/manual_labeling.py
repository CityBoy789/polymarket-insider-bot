"""
Manual Labeling Tool
Interactively review and label alerts to create a ground truth dataset.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from src.core.config import DATABASE_PATH
from src.database.database import Database

console = Console()


class ManualLabeler:
    def __init__(self):
        self.db = Database(DATABASE_PATH)

    async def run(self):
        """Run the interactive labeling session"""
        console.print("[bold cyan]🕵️ Manual Labeling Tool[/bold cyan]")
        console.print("Review alerts and label them as True Positive (Insider) or False Positive.")

        # 1. Get unlabeled alerts
        alerts = await self.db.get_unlabeled_alerts(limit=20)

        if not alerts:
            console.print("[yellow]No unlabeled alerts found![/yellow]")
            return

        console.print(f"Found {len(alerts)} alerts to review.\n")

        count = 0
        for alert in alerts:
            count += 1
            self._display_alert(alert, count, len(alerts))

            # Interactive Loop
            while True:
                choice = Prompt.ask(
                    "[bold]Is this Insider Trading?[/bold]",
                    choices=["y", "n", "u", "s", "q"],
                    default="u",
                )

                if choice == "q":
                    console.print("Exiting...")
                    return
                elif choice == "s":
                    console.print("Skipped.")
                    break

                label_map = {"y": "insider", "n": "false_positive", "u": "unsure"}

                label = label_map[choice]
                await self.db.update_alert_label(alert["id"], label)
                console.print(f"[green]Labeled as: {label}[/green]\n")
                break

        console.print("[bold green]Session Complete![/bold green]")

    def _display_alert(self, alert: dict, current: int, total: int):
        console.print(
            Panel(
                f"[bold]Alert {current}/{total}[/bold] | Score: [yellow]{alert['suspicion_score']}/10[/yellow]",
                title="Review Alert",
                border_style="blue",
            )
        )

        # Details Table
        table = Table(show_header=False, box=None)
        table.add_row("[cyan]Wallet:[/cyan]", alert["wallet"])
        table.add_row("[cyan]Market:[/cyan]", alert["market_title"])

        trade = alert.get("trade", {}) or {}
        size = float(trade.get("size", 0) or 0)
        price = float(trade.get("price", 0) or 0)
        value = size * price

        table.add_row(
            "[cyan]Trade:[/cyan]", f"{trade.get('side', 'UNKNOWN')} ${value:.2f} @ {price:.3f}"
        )
        table.add_row("[cyan]Time:[/cyan]", alert["timestamp"])

        console.print(table)

        # Stats
        stats = alert.get("wallet_stats", {}) or {}
        console.print("\n[bold]Wallet Stats:[/bold]")
        console.print(f"  • Age: {stats.get('age_days', 0):.1f} days")
        console.print(f"  • Total Volume: ${stats.get('total_volume', 0):.0f}")
        console.print(f"  • Concentration: {stats.get('max_market_concentration', 0) * 100:.0f}%")

        # Reasons
        console.print("\n[bold]Suspicion Reasons:[/bold]")
        reasons = alert.get("reasons", [])
        for r in reasons:
            console.print(f"  • [red]{r}[/red]")

        console.print("\n[dim](y=Yes/Insider, n=No/False Positive, u=Unsure, s=Skip, q=Quit)[/dim]")


if __name__ == "__main__":
    labeler = ManualLabeler()
    try:
        asyncio.run(labeler.run())
    except KeyboardInterrupt:
        print("\nExiting...")
