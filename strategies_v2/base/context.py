"""Execution context shared by v2 strategies."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(slots=True)
class StrategyContext:
    """Runtime services injected into a strategy."""

    trade_date: Optional[str] = None
    universe_name: str = "default"
    services: Dict[str, Any] = field(default_factory=dict)
