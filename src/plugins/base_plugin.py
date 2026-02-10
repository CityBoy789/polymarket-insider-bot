import logging
from abc import ABC, abstractmethod


class BasePlugin(ABC):
    """
    Abstract base class for all plugins in the Polymarket Insider Plus system.
    """

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"plugin.{name}")

    @abstractmethod
    async def check(self, wallet: str) -> bool:
        """
        Perform a check on a specific wallet address.

        Args:
            wallet (str): The wallet address to check.

        Returns:
            bool: True if the wallet matches the plugin's criteria, False otherwise.
        """
        pass

    @abstractmethod
    async def analyze(self, trade: dict) -> float:
        """
        Analyze a specific trade record.

        Args:
            trade (dict): The trade data to analyze.

        Returns:
            float: A score or impact factor calculated by the plugin.
        """
        pass
