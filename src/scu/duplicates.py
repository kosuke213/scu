from __future__ import annotations

from typing import Set


class SimpleDuplicateDetector:
    """In-memory duplicate detector for capture hashes."""

    def __init__(self) -> None:
        self._hashes: Set[str] = set()

    def is_duplicate(self, hash_value: str) -> bool:
        return hash_value in self._hashes

    def remember(self, hash_value: str) -> None:
        self._hashes.add(hash_value)
