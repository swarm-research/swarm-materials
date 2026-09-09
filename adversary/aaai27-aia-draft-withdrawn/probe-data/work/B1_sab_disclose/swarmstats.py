"""Small, dependency-free statistical helpers for the shared workspace."""

from __future__ import annotations

import math
from numbers import Real
from typing import Iterable

__all__ = ["benjamini_hochberg"]


def benjamini_hochberg(pvalues: Iterable[Real]) -> list[float]:
    """Adjust p-values with the Benjamini-Hochberg FDR procedure.

    The returned values follow the input order. Inputs must be finite real
    numbers in the closed interval [0, 1]. An empty iterable returns an empty
    list.

    The adjustment sorts the p-values, computes ``m * p_(i) / i``, and applies
    a reverse cumulative minimum. That final step makes the adjusted values
    monotone in sorted p-value order and handles ties correctly.

    Parameters
    ----------
    pvalues:
        Any finite iterable of unadjusted p-values.

    Returns
    -------
    list[float]
        Benjamini-Hochberg adjusted p-values in the original order.

    Examples
    --------
    >>> benjamini_hochberg([0.01, 0.04, 0.03, 0.002])
    [0.02, 0.04, 0.04, 0.008]
    >>> benjamini_hochberg([0.01, 0.01, 0.5])
    [0.015, 0.015, 0.5]
    """
    raw = list(pvalues)
    values: list[float] = []

    for position, value in enumerate(raw):
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError(
                f"p-value at position {position} must be a real number; "
                f"got {type(value).__name__}"
            )
        converted = float(value)
        if not math.isfinite(converted) or not 0.0 <= converted <= 1.0:
            raise ValueError(
                f"p-value at position {position} must be finite and within "
                f"[0, 1]; got {value!r}"
            )
        values.append(converted)

    count = len(values)
    if count == 0:
        return []

    order = sorted(range(count), key=values.__getitem__)
    adjusted = [0.0] * count
    running_minimum = 1.0

    for sorted_position in range(count - 1, -1, -1):
        original_position = order[sorted_position]
        rank = sorted_position + 1
        candidate = count * values[original_position] / rank
        running_minimum = min(running_minimum, candidate)
        adjusted[original_position] = running_minimum

    return adjusted
