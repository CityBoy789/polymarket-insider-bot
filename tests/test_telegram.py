"""Test Telegram notification connectivity and alert formatting."""

import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path so `src` is importable
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from src.core.telegram_notifier import TelegramNotifier  # noqa: E402


async def test_connection():
    """Test basic Telegram bot connectivity."""
    notifier = TelegramNotifier()

    if not notifier.enabled:
        print("❌ Telegram not enabled. Check your .env:")
        print("   TELEGRAM_ENABLED=true")
        print("   TELEGRAM_BOT_TOKEN=<your token>")
        print("   TELEGRAM_CHAT_ID=<your chat id>")
        return False

    success = await notifier.send_test_message()

    if success:
        print("✅ Telegram connection test passed!")
    else:
        print("❌ Telegram test failed. Check:")
        print("  1. TELEGRAM_BOT_TOKEN is correct")
        print("  2. TELEGRAM_CHAT_ID is correct")
        print("  3. You have sent /start to your bot")
    return success


async def test_alert_format():
    """Test alert message formatting (no network call)."""
    notifier = TelegramNotifier()

    mock_alert = {
        "suspicion_score": 8.5,
        "wallet": "0x1234567890abcdef1234567890abcdef12345678",
        "market_title": "Will Bitcoin reach $100k by end of 2025?",
        "market_slug": "will-bitcoin-reach-100k",
        "trade": {"side": "BUY", "value_usd": 5000.0, "price": "0.35"},
        "wallet_stats": {
            "age_days": 3.5,
            "total_trades": 2,
            "unique_markets": 1,
            "avg_bet_size": 5000.0,
        },
        "reasons": [
            "Fresh wallet (3.5 days old)",
            "Large first trade ($5,000)",
            "Single market focus",
            "Price moved 15% after trade",
        ],
    }

    message = notifier._format_alert_message(mock_alert)
    print("--- Formatted Alert Message ---")
    print(message)
    print("--- End ---")
    return True


async def main():
    print("=== Telegram Notifier Tests ===\n")

    # Always test formatting
    print("[1/2] Testing alert formatting...")
    await test_alert_format()
    print()

    # Test connection if --send flag is passed
    if "--send" in sys.argv:
        print("[2/2] Testing live connection...")
        await test_connection()
    else:
        print("[2/2] Skipped live send (use --send to test)")


if __name__ == "__main__":
    asyncio.run(main())
