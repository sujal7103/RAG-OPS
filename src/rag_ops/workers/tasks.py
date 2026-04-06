"""Worker tasks for benchmark execution."""

from __future__ import annotations

from rag_ops.services.benchmark_runs import execute_benchmark_run
from rag_ops.settings import get_settings

try:
    import dramatiq
    from dramatiq.brokers.redis import RedisBroker
except Exception:  # pragma: no cover - optional runtime dependency
    dramatiq = None
    RedisBroker = None

if dramatiq is not None and RedisBroker is not None:  # pragma: no branch
    _settings = get_settings()
    _broker = RedisBroker(url=_settings.redis_url)
    dramatiq.set_broker(_broker)

    @dramatiq.actor(queue_name="benchmark-runs")
    def process_benchmark_run_actor(run_id: str) -> None:
        """Execute one benchmark run via Dramatiq."""
        execute_benchmark_run(run_id, _settings)
else:
    process_benchmark_run_actor = None  # type: ignore[assignment]
