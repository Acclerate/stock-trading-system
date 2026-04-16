"""Skeleton for the first v2 pilot strategy."""

from strategies_v2.base import BaseStrategy, StrategyContext


class LowVolumeBreakoutV2Strategy(BaseStrategy):
    """Pilot v2 strategy migrated from the existing breakout workflow."""

    strategy_name = "low_volume_breakout_v2"

    def run(self, context: StrategyContext):
        raise NotImplementedError("LowVolumeBreakoutV2Strategy is not implemented yet.")
