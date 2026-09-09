"""Small, dependency-free statistical helpers for shared research scripts."""

from __future__ import annotations

import math
from numbers import Real
from typing import Iterable

__all__ = ["benjamini_hochberg"]


def benjamini_hochberg(p_values: Iterable[Real]) -> list[float]:
    """Adjust p-values with the Benjamini-Hochberg FDR procedure.

    The returned values follow the input order. Each result is in ``[0, 1]``;
    equal raw p-values receive equal adjusted values. The function accepts any
    finite iterable, including generators, and does not modify mutable inputs.

    Args:
        p_values: Raw p-values between 0 and 1, inclusive.

    Returns:
        Benjamini-Hochberg adjusted p-values in the original order.

    Raises:
        TypeError: If an item is not a real number or is a boolean.
        ValueError: If an item is non-finite or outside ``[0, 1]``.
    """
    values: list[float] = []
    for position, value in enumerate(p_values):
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError(
                f"p-value at position {position} must be a real number, "
                f"got {type(value).__name__}"
            )

        numeric = float(value)
        if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
            raise ValueError(
                f"p-value at position {position} must be finite and in [0, 1], "
                f"got {value!r}"
            )
        values.append(numeric)

    count = len(values)
    if count == 0:
        return []

    ranked = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    adjusted = [0.0] * count
    running_minimum = 1.0

    for rank_index in range(count - 1, -1, -1):
        original_index, p_value = ranked[rank_index]
        rank = rank_index + 1
        scaled = p_value * count / rank
        running_minimum = min(running_minimum, scaled)
        adjusted[original_index] = min(1.0, running_minimum)

    return adjusted
