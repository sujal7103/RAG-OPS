"""Results table abstraction that prefers pandas but has a lightweight fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import numpy as np

try:  # pragma: no cover - exercised implicitly when pandas is installed
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover - covered by fallback tests
    pd = None


@dataclass
class SimpleResultsFrame:
    """Small subset of DataFrame behavior used by tests and CLI fallbacks."""

    rows: list[dict[str, Any]]

    def __len__(self) -> int:
        return len(self.rows)

    @property
    def empty(self) -> bool:
        return not self.rows

    @property
    def columns(self) -> list[str]:
        if not self.rows:
            return []
        first_row = self.rows[0]
        return list(first_row.keys())

    def __getitem__(self, column_name: str) -> np.ndarray:
        return np.array([row.get(column_name) for row in self.rows])

    def sort_values(self, column_name: str, ascending: bool = True) -> "SimpleResultsFrame":
        return SimpleResultsFrame(
            sorted(self.rows, key=lambda row: row.get(column_name, 0), reverse=not ascending)
        )

    def reset_index(self, drop: bool = True) -> "SimpleResultsFrame":
        return self

    def to_records(self) -> list[dict[str, Any]]:
        return list(self.rows)


def build_results_frame(rows: Sequence[dict[str, Any]]) -> Any:
    """Build a pandas DataFrame when available, else use a lightweight fallback."""
    row_list = list(rows)
    if pd is not None:
        return pd.DataFrame(row_list)
    return SimpleResultsFrame(row_list)

