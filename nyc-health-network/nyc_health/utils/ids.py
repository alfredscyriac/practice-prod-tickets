"""Deterministic, prefix-based id generation (easy to read in tests and logs)."""
from typing import Dict


class IdGenerator:
    def __init__(self) -> None:
        self._counters: Dict[str, int] = {}

    def next(self, prefix: str) -> str:
        value = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = value
        return f"{prefix}-{value:05d}"

    def peek(self, prefix: str) -> int:
        return self._counters.get(prefix, 0)
