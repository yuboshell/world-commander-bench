"""Metric accumulation: grounding accuracy, latency, deadline-miss rate."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field


def miss_rate(latencies_ms: list[float], deadline_ms: float) -> float:
    """Fraction of commands that exceed a deadline. A deadline miss is just a
    threshold on the measured latency, so any deadline's miss rate (the whole
    frontier) is computable post-hoc from one run — no re-inference needed."""
    if not latencies_ms:
        return 0.0
    return sum(l > deadline_ms for l in latencies_ms) / len(latencies_ms)


def deadline_report(latencies_ms: list[float], deadline_ms: float) -> dict:
    """Real-time accounting for a measured decision stream at a given deadline:
    how many actions land in time vs are dropped (late), plus the synchronous
    decision throughput (decisions per real second). The first piece of the
    real-time layer — applies to both arena and SC2 latency logs, post-hoc."""
    n = len(latencies_ms)
    if n == 0:
        return {"n": 0, "deadline_ms": deadline_ms, "missed": 0, "on_time": 0,
                "miss_rate": 0.0, "mean_ms": 0.0, "throughput_hz": 0.0}
    missed = sum(l > deadline_ms for l in latencies_ms)
    mean_ms = statistics.mean(latencies_ms)
    return {
        "n": n,
        "deadline_ms": deadline_ms,
        "missed": missed,
        "on_time": n - missed,
        "miss_rate": missed / n,
        "mean_ms": mean_ms,
        "throughput_hz": 1000.0 / mean_ms if mean_ms else 0.0,
    }


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
