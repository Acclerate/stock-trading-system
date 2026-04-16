"""Abstract base class for v2 strategies."""

from abc import ABC, abstractmethod
from typing import Any

from .context import StrategyContext
from .params import StrategyParams


class BaseStrategy(ABC):
    """Common contract for all v2 strategies."""

    strategy_name = "base"

    def __init__(self, params: StrategyParams | None = None) -> None:
        self.params = params or StrategyParams()

    @abstractmethod
    def run(self, context: StrategyContext) -> Any:
        """Execute the strategy and return raw screening or backtest output."""
