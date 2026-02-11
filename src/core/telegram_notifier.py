"""Telegram notification system for insider trading alerts."""

import asyncio
from typing import Any

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from src.core.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED
from src.core.logger import logger


class TelegramNotifier:
    """
    Telegram push notifications for suspicious activity alerts.

    The Bot is created on-demand per send and shut down immediately after,
    so it does not keep background connections alive.
    """

    def __init__(self):
        self.enabled = TELEGRAM_ENABLED
        self.bot_token = TELEGRAM_BOT_TOKEN

        # Support multiple recipients via comma-separated chat IDs
        self.chat_ids: list[int] = []
        if TELEGRAM_CHAT_ID:
            self.chat_ids = [int(cid.strip()) for cid in TELEGRAM_CHAT_ID.split(",") if cid.strip()]

        if not self.enabled:
            logger.info("Telegram notifications disabled")
            return

        if not self.bot_token or not self.chat_ids:
            logger.warning("Telegram config incomplete, notifications disabled")
            self.enabled = False
            return

        logger.info(f"Telegram notifications enabled, recipients: {len(self.chat_ids)}")

    async def send_alert(self, alert: dict[str, Any]):
        """Send an alert to all configured Telegram recipients."""
        if not self.enabled:
            return

        try:
            message = self._format_alert_message(alert)
            async with Bot(token=self.bot_token) as bot:
                tasks = [self._send_to_chat(bot, chat_id, message) for chat_id in self.chat_ids]
                await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"Telegram send failed: {e}")

    async def _send_to_chat(self, bot: Bot, chat_id: int, message: str):
        """Send a message to a specific chat."""
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=False,
            )
            logger.debug(f"Telegram message sent to {chat_id}")

        except TelegramError as e:
            logger.error(f"Telegram send error ({chat_id}): {e}")

    def _format_alert_message(self, alert: dict[str, Any]) -> str:
        """Format alert as a Markdown message for Telegram."""
        score = alert["suspicion_score"]

        # Severity emoji
        if score >= 9:
            emoji = "🚨🚨🚨"
            severity = "CRITICAL"
        elif score >= 8:
            emoji = "⚠️⚠️"
            severity = "HIGH"
        elif score >= 7:
            emoji = "⚠️"
            severity = "MEDIUM"
        else:
            emoji = "ℹ️"
            severity = "LOW"

        # Shorten wallet address
        wallet = alert["wallet"]
        wallet_short = f"`{wallet[:8]}...{wallet[-6:]}`"

        message_parts = [
            f"{emoji} *Suspicious Trade Detected* {emoji}",
            "",
            f"*Severity:* {severity}",
            f"*Score:* `{score:.1f}/10`",
            "",
            "📊 *Trade Details*",
            f"• Wallet: {wallet_short}",
            f"• Market: {alert['market_title'][:50]}",
            f"• Trade: {alert['trade']['side']} `${alert['trade']['value_usd']:.2f}`",
            f"• Price: `${alert['trade']['price']}`",
            "",
            "👤 *Wallet Stats*",
            f"• Account age: `{alert['wallet_stats']['age_days']:.1f} days`",
            f"• Total trades: `{alert['wallet_stats']['total_trades']}`",
            f"• Markets traded: `{alert['wallet_stats']['unique_markets']}`",
            f"• Avg bet size: `${alert['wallet_stats']['avg_bet_size']:.2f}`",
            "",
            "🚩 *Red Flags*",
        ]

        # Add reasons (max 5)
        for i, reason in enumerate(alert["reasons"][:5], 1):
            message_parts.append(f"{i}. {reason}")

        # Links
        message_parts.extend(
            [
                "",
                "🔗 *Links*",
                f"[Polymarket](https://polymarket.com/event/{alert['market_slug']})",
                f"[Wallet on PolygonScan](https://polygonscan.com/address/{wallet})",
                "",
                "⏱ _Signal detected — price may have already moved._",
            ]
        )

        return "\n".join(message_parts)

    async def send_test_message(self) -> bool:
        """Send a test message to verify Telegram connectivity."""
        if not self.enabled:
            logger.error("Telegram not enabled")
            return False

        test_message = (
            "✅ *Polymarket Insider Tracker*\n\n"
            "Telegram notification test successful!\n"
            "System is ready and monitoring..."
        )

        try:
            async with Bot(token=self.bot_token) as bot:
                for chat_id in self.chat_ids:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=test_message,
                        parse_mode=ParseMode.MARKDOWN,
                    )
            logger.info("Telegram test message sent successfully")
            return True

        except TelegramError as e:
            logger.error(f"Telegram test failed: {e}")
            return False
