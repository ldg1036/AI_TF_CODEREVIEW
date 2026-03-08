"""Regex execution guard utilities for ReDoS defense.

Provides length-capped wrappers around ``re.search`` / ``re.finditer`` so
that extremely large inputs cannot trigger catastrophic backtracking.
"""

import re
from typing import Iterator, Optional

# Default safety cap: 500 KB of text.
MAX_INPUT_LENGTH: int = 500_000


def safe_search(
    pattern,
    text: str,
    flags: int = 0,
    max_len: int = MAX_INPUT_LENGTH,
) -> Optional[re.Match]:
    """Return ``re.search`` result, or ``None`` when *text* exceeds *max_len*."""
    if len(text) > max_len:
        return None
    return re.search(pattern, text, flags)


def safe_finditer(
    pattern,
    text: str,
    flags: int = 0,
    max_len: int = MAX_INPUT_LENGTH,
) -> Iterator[re.Match]:
    """Yield ``re.finditer`` matches, returning empty iterator when *text* exceeds *max_len*."""
    if len(text) > max_len:
        return iter([])
    return re.finditer(pattern, text, flags)


def safe_findall(
    pattern,
    text: str,
    flags: int = 0,
    max_len: int = MAX_INPUT_LENGTH,
) -> list:
    """Return ``re.findall`` result, or empty list when *text* exceeds *max_len*."""
    if len(text) > max_len:
        return []
    return re.findall(pattern, text, flags)
