"""Signal filtering helpers for v2 pipelines."""

from __future__ import annotations

import pandas as pd


def filter_by_min_score(df: pd.DataFrame, min_score: float) -> pd.DataFrame:
    return df[df["score"] >= min_score].copy()


def filter_by_action(df: pd.DataFrame, *actions: str) -> pd.DataFrame:
    normalized_actions = {action.strip().lower() for action in actions}
    return df[df["action"].str.lower().isin(normalized_actions)].copy()
