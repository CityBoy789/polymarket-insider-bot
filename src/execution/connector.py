import asyncio
import binascii
import os
from typing import Any

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import (
    ApiCreds,
    AssetType,
    BalanceAllowanceParams,
    OrderArgs,
)
from py_clob_client.exceptions import PolyApiException


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

    async def place_order(
        self, price: float, size: float, side: str, token_id: str
    ) -> dict[str, Any]:
        """
        Place an order on the CLOB.

        Args:
            price (float): Price of the order.
            size (float): Size of the order.
            side (str): Side of the order (BUY or SELL).
            token_id (str): Token ID of the asset.

        Returns:
            Dict[str, Any]: The order response.
        """
        try:
            from src.core.config import SIMULATION_MODE

            if SIMULATION_MODE:
                print(
                    f"[SIMULATION] Simulate placing {side} order: {size} @ {price} (Token: {token_id})"
                )
                return {
                    "simulation": True,
                    "orderID": f"sim_{token_id[:10]}",
                    "status": "filled",
                    "size": size,
                    "price": price,
                }

            order_args = OrderArgs(price=price, size=size, side=side, token_id=token_id)
            return await asyncio.to_thread(self.client.create_order, order_args)
        except PolyApiException as e:
            print(f"Polymarket API Error placing order: {e}")
            return {"error": str(e)}
        except Exception as e:
            print(f"Error placing order: {e}")
            return {"error": str(e)}

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        """
        Cancel an order on the CLOB.

        Args:
            order_id (str): The ID of the order to cancel.

        Returns:
            Dict[str, Any]: The cancel response.
        """
        try:
            return await asyncio.to_thread(self.client.cancel, order_id)
        except PolyApiException as e:
            print(f"Polymarket API Error cancelling order: {e}")
            return {"error": str(e)}
        except Exception as e:
            print(f"Error cancelling order: {e}")
            return {"error": str(e)}


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
