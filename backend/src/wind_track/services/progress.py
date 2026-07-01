"""Line-buffered progress logging for long-running CLI pipelines."""

from __future__ import annotations

import sys
import time
from typing import Any


def log_step(message: str, **fields: Any) -> None:
    """Emit a timestamped progress line to stderr (flushed immediately)."""
    ts = time.strftime("%H:%M:%S")
    extra = " ".join(f"{k}={v}" for k, v in fields.items())
    suffix = f" {extra}" if extra else ""
    print(f"[wind-track {ts}] {message}{suffix}", file=sys.stderr, flush=True)


class step:
    """Context manager that logs START/DONE with elapsed seconds."""

    def __init__(self, name: str, **fields: Any):
        self.name = name
        self.fields = fields
        self._t0 = 0.0

    def __enter__(self) -> step:
        self._t0 = time.monotonic()
        log_step(f"START {self.name}", **self.fields)
        return self

    def __exit__(self, exc_type: Any, exc: Any, _tb: Any) -> None:
        elapsed = round(time.monotonic() - self._t0, 1)
        if exc_type is not None:
            log_step(f"FAILED {self.name}", elapsed_s=elapsed, error=str(exc))
            return
        log_step(f"DONE {self.name}", elapsed_s=elapsed)