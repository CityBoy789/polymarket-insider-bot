import asyncio
import binascii
import os
from typing import Any

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, AssetType, BalanceAllowanceParams


class PolymarketTrader:
    """
    Trader interface for Polymarket CLOB.
    """

    def __init__(self):
        """
        Initialize the trader with credentials from environment variables.
        """
        self.host = os.getenv("CLOB_API_URL", "https://clob.polymarket.com")
        self.key = os.getenv("CLOB_API_KEY")
        self.secret = os.getenv("CLOB_SECRET")
        self.passphrase = os.getenv("CLOB_PASSPHRASE")
        self.private_key = os.getenv("PRIVATE_KEY")
        self.chain_id = int(os.getenv("CHAIN_ID", "137"))  # Polygon Mainnet

        if not all([self.key, self.secret, self.passphrase, self.private_key]):
            raise ValueError("Missing CLOB API credentials in environment variables.")

        try:
            creds = ApiCreds(
                api_key=self.key,
                api_secret=self.secret,
                api_passphrase=self.passphrase,
            )
            self.client = ClobClient(
                host=self.host,
                key=self.private_key,
                chain_id=self.chain_id,
                creds=creds,
            )
        except Exception as e:
            raise ValueError(f"Failed to initialize ClobClient: {e}") from e

    async def check_balance(self) -> dict[str, Any]:
        """
        Check current USDC balance (collateral).

        Returns:
            Dict[str, Any]: The raw balance response from the CLOB.
        """
        try:
            params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            # wrapping synchronous call
            return await asyncio.to_thread(self.client.get_balance_allowance, params)
        except binascii.Error:
            print(
                "Error: content of CLOB_SECRET or keys is not valid base64 (Incorrect padding). "
                "Check your .env credentials."
            )
            return {}
        except Exception as e:
            if "padding" in str(e).lower():
                print("Error: Incorrect padding detected. Check CLOB_SECRET in .env.")
            else:
                print(f"Error checking balance: {e}")
            return {}


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    async def main():
        try:
            trader = PolymarketTrader()
            balance = await trader.check_balance()
            print(f"Balance: {balance}")
        except ValueError as e:
            print(f"Config Error: {e}")
        except Exception as e:
            print(f"Runtime Error: {e}")

    asyncio.run(main())
