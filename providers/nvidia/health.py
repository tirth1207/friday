from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class ProviderHealth:
    name: str
    consecutive_failures: int = 0
    last_error: str | None = None
    last_failure_at: float | None = None
    last_success_at: float | None = None

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.last_error = None
        self.last_success_at = time.time()

    def record_failure(self, error: Exception) -> None:
        self.consecutive_failures += 1
        self.last_error = str(error)[:500]
        self.last_failure_at = time.time()

    @property
    def status(self) -> str:
        if self.consecutive_failures >= 3:
            return "degraded"
        return "ready"


nvidia_health = ProviderHealth(name="nvidia")


def snapshot() -> dict[str, object]:
    return {
        "provider": nvidia_health.name,
        "status": nvidia_health.status,
        "consecutive_failures": nvidia_health.consecutive_failures,
        "last_error": nvidia_health.last_error,
        "last_failure_at": nvidia_health.last_failure_at,
        "last_success_at": nvidia_health.last_success_at,
    }
