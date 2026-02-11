"""
Detection Quality Metrics
Calculate Precision, Recall, and F1 Score based on labeled data.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from rich.console import Console
from rich.table import Table

from src.core.config import DATABASE_PATH
from src.database.database import Database

console = Console()


class QualityEvaluator:
    def __init__(self):
        self.db = Database(DATABASE_PATH)

    async def evaluate(self):
        """Calculate and display metrics"""
        alerts = await self.db.get_labeled_alerts()

        if not alerts:
            console.print(
                "[yellow]No labeled alerts found. Run 'src/validation/manual_labeling.py' first.[/yellow]"
            )
            return

        true_positives = [a for a in alerts if a["label"] == "insider"]
        false_positives = [a for a in alerts if a["label"] == "false_positive"]
        unsure = [a for a in alerts if a["label"] == "unsure"]

        tp = len(true_positives)
        fp = len(false_positives)

        total_labeled = tp + fp

        if total_labeled == 0:
            precision = 0.0
        else:
            precision = tp / total_labeled

        # Recall: Cannot be calculated purely from filtered alerts (we don't know False Negatives).
        # We assume standard Recall is N/A or we need random sampling of non-alerts (future feature).

        console.print("\n[bold cyan]📊 Detection Quality Report[/bold cyan]")
        console.print(f"Total Labeled: {len(alerts)} (TP: {tp}, FP: {fp}, Unsure: {len(unsure)})")

        table = Table(title="Metrics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")
        table.add_column("Target", style="dim")

        table.add_row(
            "Precision (True Positive Rate)",
            f"[green]{precision:.1%}[/green]" if precision > 0.5 else f"[red]{precision:.1%}[/red]",
            "> 60%",
        )
        table.add_row("Recall", "N/A*", "N/A")

        console.print(table)
        console.print("[dim]* Recall requires reviewing non-flagged trades (False Negatives)[/dim]")

        if fp > 0:
            console.print("\n[bold]Top False Positives (Fix these patterns):[/bold]")
            for alert in false_positives[:5]:
                console.print(
                    f"• {alert['wallet'][:10]}... Score: {alert['suspicion_score']} | Reasons: {alert['reasons']}"
                )


if __name__ == "__main__":
    evaluator = QualityEvaluator()
    try:
        asyncio.run(evaluator.evaluate())
    except KeyboardInterrupt:
        print("\nExiting...")
