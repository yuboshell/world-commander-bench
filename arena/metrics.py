"""Metric accumulation: grounding accuracy, latency, deadline-miss rate."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field


@dataclass
class Metrics:
    n: int = 0
    correct: int = 0
    deadline_misses: int = 0
    latencies_ms: list[float] = field(default_factory=list)

    def record(self, correct: bool, latency_ms: float, missed: bool) -> None:
        self.n += 1
        self.correct += int(correct)
        self.deadline_misses += int(missed)
        self.latencies_ms.append(latency_ms)

    def _percentile(self, p: float) -> float:
        if not self.latencies_ms:
            return 0.0
        xs = sorted(self.latencies_ms)
        k = min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))
        return xs[k]

    def report(self) -> dict:
        n = self.n or 1  # avoid div-by-zero in an empty report
        return {
            "commands": self.n,
            "grounding_accuracy": round(self.correct / n, 4),
            "deadline_miss_rate": round(self.deadline_misses / n, 4),
            "latency_ms_mean": round(statistics.mean(self.latencies_ms), 1)
            if self.latencies_ms else 0.0,
            "latency_ms_p50": round(self._percentile(50), 1),
            "latency_ms_p95": round(self._percentile(95), 1),
        }
