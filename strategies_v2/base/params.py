"""Parameter container used by v2 strategies."""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(slots=True)
class StrategyParams:
    """Loose parameter bag for strategy-specific settings."""

    values: Dict[str, Any] = field(default_factory=dict)
