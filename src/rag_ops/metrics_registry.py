"""In-process metrics registry with Prometheus-style rendering."""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from threading import Lock


def _label_key(labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
    if not labels:
        return ()
    return tuple(sorted((str(key), str(value)) for key, value in labels.items()))


def _format_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    joined = ",".join(f'{key}="{value}"' for key, value in labels)
    return f"{{{joined}}}"


class MetricsRegistry:
    """Small thread-safe metrics collector."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._histograms: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, float]] = defaultdict(
            lambda: {"sum": 0.0, "count": 0.0}
        )

    def inc_counter(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            self._counters[(name, _label_key(labels))] += value

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            self._gauges[(name, _label_key(labels))] = value

    def adjust_gauge(self, name: str, delta: float, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            key = (name, _label_key(labels))
            self._gauges[key] = self._gauges.get(key, 0.0) + delta

    def observe_histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            bucket = self._histograms[(name, _label_key(labels))]
            bucket["sum"] += value
            bucket["count"] += 1

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            for (name, labels), value in sorted(self._counters.items()):
                lines.append(f"{name}{_format_labels(labels)} {value}")
            for (name, labels), value in sorted(self._gauges.items()):
                lines.append(f"{name}{_format_labels(labels)} {value}")
            for (name, labels), bucket in sorted(self._histograms.items()):
                lines.append(f"{name}_count{_format_labels(labels)} {bucket['count']}")
                lines.append(f"{name}_sum{_format_labels(labels)} {bucket['sum']}")
        return "\n".join(lines) + ("\n" if lines else "")

    def reset(self) -> None:
        """Clear all collected metrics, primarily for tests."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()


@lru_cache(maxsize=1)
def get_metrics_registry() -> MetricsRegistry:
    """Return the process-local shared metrics registry."""
    return MetricsRegistry()
