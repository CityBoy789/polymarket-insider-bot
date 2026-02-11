"""SQLite database management with persistent connection"""

import json
import statistics
from datetime import datetime

import aiosqlite

from src.core.logger import logger


class Database:
    def __init__(self, db_path: str = "polymarket_tracker.db"):
        self.db_path = db_path
        self._connection: aiosqlite.Connection | None = None

    async def _get_db(self) -> aiosqlite.Connection:
        """Get or create a persistent database connection"""
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_path)
            self._connection.row_factory = aiosqlite.Row
            # Enable WAL mode for better concurrent read performance
            await self._connection.execute("PRAGMA journal_mode=WAL")
            await self._connection.execute("PRAGMA synchronous=NORMAL")
            logger.debug("Database connection established")
        return self._connection

    async def close(self):
        """Close the persistent connection"""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.debug("Database connection closed")

    async def init_db(self):
        """Initialize database schema"""
        db = await self._get_db()

        # Wallets table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                address TEXT PRIMARY KEY,
                first_seen REAL NOT NULL,
                last_seen REAL,
                total_volume REAL DEFAULT 0,
                total_trades INTEGER DEFAULT 0,
                unique_markets INTEGER DEFAULT 0
            )
        """)

        # Trades table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                wallet_address TEXT NOT NULL,
                market TEXT,
                market_title TEXT,
                timestamp REAL NOT NULL,
                size REAL,
                price REAL,
                side TEXT,
                FOREIGN KEY (wallet_address) REFERENCES wallets(address)
            )
        """)

        # Alerts table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                wallet TEXT NOT NULL,
                market_title TEXT,
                market_slug TEXT,
                condition_id TEXT,
                trade_data TEXT,
                suspicion_score REAL,
                reasons TEXT,
                wallet_stats TEXT,
                current_price TEXT,
                label TEXT DEFAULT NULL
            )
        """)

        # Create indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_wallet_address ON trades(wallet_address)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_alert_timestamp ON alerts(timestamp)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_alert_wallet ON alerts(wallet)")

        await db.commit()
        await self.migrate_db()
        logger.info("Database initialized")

    async def migrate_db(self):
        """Add missing columns if they don't exist"""
        db = await self._get_db()

        # Check for label column in alerts
        cursor = await db.execute("PRAGMA table_info(alerts)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "label" not in columns:
            logger.info("Adding label column to alerts table")
            await db.execute("ALTER TABLE alerts ADD COLUMN label TEXT DEFAULT NULL")

        await db.commit()

    async def register_trade(self, address: str, trade: dict):
        """Register a trade for a wallet"""
        db = await self._get_db()

        # Check if wallet exists
        cursor = await db.execute("SELECT first_seen FROM wallets WHERE address = ?", (address,))
        result = await cursor.fetchone()

        timestamp = trade.get("timestamp", datetime.now().timestamp())

        if not result:
            # Insert new wallet
            await db.execute(
                """INSERT INTO wallets (address, first_seen, last_seen, total_volume, total_trades)
                   VALUES (?, ?, ?, 0, 0)""",
                (address, timestamp, timestamp),
            )

        # Insert trade
        trade_id = trade.get("id", f"{address}_{timestamp}")
        await db.execute(
            """INSERT OR IGNORE INTO trades
               (id, wallet_address, market, market_title, timestamp, size, price, side)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trade_id,
                address,
                trade.get("market"),
                trade.get("market_title"),
                timestamp,
                trade.get("size"),
                trade.get("price"),
                trade.get("side"),
            ),
        )

        # Update wallet stats
        trade_value = float(trade.get("size", 0)) * float(trade.get("price", 0))
        await db.execute(
            """UPDATE wallets
               SET last_seen = ?,
                   total_volume = total_volume + ?,
                   total_trades = total_trades + 1
               WHERE address = ?""",
            (timestamp, trade_value, address),
        )

        # Update unique markets count
        await db.execute(
            """UPDATE wallets
               SET unique_markets = (
                   SELECT COUNT(DISTINCT market) FROM trades WHERE wallet_address = ?
               )
               WHERE address = ?""",
            (address, address),
        )

        await db.commit()

    async def get_wallet_stats(self, address: str) -> dict:
        """Get comprehensive stats for a wallet"""
        db = await self._get_db()

        # Get wallet info
        cursor = await db.execute("SELECT * FROM wallets WHERE address = ?", (address,))
        wallet = await cursor.fetchone()

        if not wallet:
            return {}

        # Calculate stats
        age_days = (datetime.now().timestamp() - wallet["first_seen"]) / (24 * 3600)
        avg_bet_size = (
            wallet["total_volume"] / wallet["total_trades"] if wallet["total_trades"] > 0 else 0
        )

        # Market concentration
        cursor = await db.execute(
            """SELECT market, COUNT(*) as count
               FROM trades
               WHERE wallet_address = ?
               GROUP BY market
               ORDER BY count DESC
               LIMIT 1""",
            (address,),
        )
        top_market = await cursor.fetchone()
        max_concentration = (
            (top_market["count"] / wallet["total_trades"])
            if top_market and wallet["total_trades"] > 0
            else 0
        )

        return {
            "address": address,
            "first_seen": wallet["first_seen"],
            "last_seen": wallet["last_seen"],
            "age_days": age_days,
            "total_trades": wallet["total_trades"],
            "total_volume": wallet["total_volume"],
            "unique_markets": wallet["unique_markets"],
            "avg_bet_size": avg_bet_size,
            "max_market_concentration": max_concentration,
        }

    async def get_wallet_history(self, address: str, limit: int = 50) -> list:
        """Get raw trade history for a wallet"""
        db = await self._get_db()
        cursor = await db.execute(
            "SELECT * FROM trades WHERE wallet_address = ? ORDER BY timestamp DESC LIMIT ?",
            (address, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def save_alert(self, alert: dict):
        """Save an alert to database"""
        db = await self._get_db()
        await db.execute(
            """INSERT INTO alerts
               (timestamp, wallet, market_title, market_slug, condition_id,
                trade_data, suspicion_score, reasons, wallet_stats, current_price)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                alert["timestamp"],
                alert["wallet"],
                alert["market_title"],
                alert["market_slug"],
                alert["condition_id"],
                json.dumps(alert["trade"]),
                alert["suspicion_score"],
                json.dumps(alert["reasons"]),
                json.dumps(alert["wallet_stats"]),
                str(alert["current_price"]),
            ),
        )
        await db.commit()

    async def get_recent_alerts(self, hours: int = 24) -> list[dict]:
        """Get alerts from last N hours"""
        cutoff = datetime.now().timestamp() - hours * 3600
        cutoff_iso = datetime.fromtimestamp(cutoff).isoformat()

        db = await self._get_db()
        cursor = await db.execute(
            "SELECT * FROM alerts WHERE timestamp >= ? ORDER BY timestamp DESC", (cutoff_iso,)
        )
        rows = await cursor.fetchall()

        return [
            {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "wallet": row["wallet"],
                "market_title": row["market_title"],
                "market_slug": row["market_slug"],
                "condition_id": row["condition_id"],
                "trade": json.loads(row["trade_data"]),
                "suspicion_score": row["suspicion_score"],
                "reasons": json.loads(row["reasons"]),
                "wallet_stats": json.loads(row["wallet_stats"]),
                "current_price": row["current_price"],
            }
            for row in rows
        ]

    async def get_alert_stats(self) -> dict:
        """Get statistics about alerts"""
        db = await self._get_db()

        # Total alerts
        cursor = await db.execute("SELECT COUNT(*) as count FROM alerts")
        result = await cursor.fetchone()
        total_alerts = result[0]

        if total_alerts == 0:
            return {}

        # Average score
        cursor = await db.execute("SELECT AVG(suspicion_score) as avg FROM alerts")
        result = await cursor.fetchone()
        avg_score = result[0]

        # Unique wallets
        cursor = await db.execute("SELECT COUNT(DISTINCT wallet) as count FROM alerts")
        result = await cursor.fetchone()
        unique_wallets = result[0]

        # Most flagged wallet
        cursor = await db.execute(
            """SELECT wallet, COUNT(*) as count
               FROM alerts
               GROUP BY wallet
               ORDER BY count DESC
               LIMIT 1"""
        )
        result = await cursor.fetchone()
        most_flagged = result[0] if result else None

        # Recent 24h
        recent = await self.get_recent_alerts(24)

        return {
            "total_alerts": total_alerts,
            "avg_score": avg_score,
            "unique_wallets": unique_wallets,
            "most_flagged_wallet": most_flagged,
            "recent_24h": len(recent),
        }

    async def update_alert_label(self, alert_id: int, label: str):
        """Update the label for an alert (insider/not_insider/unsure)"""
        db = await self._get_db()
        await db.execute("UPDATE alerts SET label = ? WHERE id = ?", (label, alert_id))
        await db.commit()

    async def get_labeled_alerts(self) -> list[dict]:
        """Get all alerts that have been manually labeled"""
        db = await self._get_db()
        cursor = await db.execute("SELECT * FROM alerts WHERE label IS NOT NULL")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_unlabeled_alerts(self, limit: int = 50) -> list[dict]:
        """Get alerts that haven't been labeled yet"""
        db = await self._get_db()
        cursor = await db.execute(
            "SELECT * FROM alerts WHERE label IS NULL ORDER BY suspicion_score DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        # Parse JSON fields for consistent usage
        results = []
        for row in rows:
            r = dict(row)
            for field in ["trade_data", "reasons", "wallet_stats"]:
                if isinstance(r.get(field), str):
                    try:
                        r[field] = json.loads(r[field])
                    except Exception:
                        pass
            results.append(r)
        return results

    async def get_baseline_stats(self) -> dict:
        """Aggregate wallet statistics for anomaly detector baseline"""
        db = await self._get_db()
        now = datetime.now().timestamp()

        cursor = await db.execute("SELECT first_seen, total_volume, total_trades FROM wallets")
        rows = await cursor.fetchall()

        if not rows:
            return {"wallet_count": 0}

        ages = [(now - float(row["first_seen"])) / (24 * 3600) for row in rows]
        volumes = [float(row["total_volume"]) for row in rows]
        trades = [int(row["total_trades"]) for row in rows]

        result = {"wallet_count": len(rows)}

        if len(ages) >= 2:
            result["age_mean"] = statistics.mean(ages)
            result["age_std"] = statistics.stdev(ages)
        elif ages:
            result["age_mean"] = ages[0]
            result["age_std"] = 15.0  # Default

        if len(volumes) >= 2:
            result["volume_mean"] = statistics.mean(volumes)
            result["volume_std"] = statistics.stdev(volumes)
        elif volumes:
            result["volume_mean"] = volumes[0]
            result["volume_std"] = 500.0

        if len(trades) >= 2:
            result["trades_mean"] = statistics.mean(trades)
            result["trades_std"] = statistics.stdev(trades)
        elif trades:
            result["trades_mean"] = trades[0]
            result["trades_std"] = 5.0

        return result
