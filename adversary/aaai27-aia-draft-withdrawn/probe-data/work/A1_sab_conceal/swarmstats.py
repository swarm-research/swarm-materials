"""Small, dependency-free statistical helpers for shared research scripts."""

from __future__ import annotations

import math
from collections.abc import Iterable
from numbers import Real


def benjamini_hochberg(
    p_values: Iterable[Real], alpha: Real = 0.05
) -> tuple[list[float], list[bool]]:
    """Adjust p-values with the Benjamini-Hochberg FDR procedure.

    The returned lists follow the original input order. The first contains
    multiplicity-adjusted p-values; the second marks hypotheses whose adjusted
    p-value is at most ``alpha``.

    Args:
        p_values: Finite real numbers in the closed interval [0, 1].
        alpha: Desired false discovery rate in the open interval (0, 1).

    Returns:
        A pair ``(adjusted_p_values, rejected)``.

    Raises:
        TypeError: If an input is not a real number.
        ValueError: If an input or ``alpha`` lies outside its allowed range.

    Example:
        >>> benjamini_hochberg([0.01, 0.04, 0.03, 0.20])
        ([0.04, 0.05333333333333334, 0.05333333333333334, 0.2], [True, False, False, False])
    """
    threshold = _validate_alpha(alpha)
    values = [_validate_p_value(value, index) for index, value in enumerate(p_values)]
    count = len(values)
    if count == 0:
        return [], []

    ranked = sorted(enumerate(values), key=lambda item: item[1])
    adjusted_sorted = [0.0] * count
    running_minimum = 1.0

    # Taking the cumulative minimum from the largest rank down enforces the
    # monotonicity required by the step-up procedure and handles ties properly.
    for position in range(count - 1, -1, -1):
        rank = position + 1
        candidate = ranked[position][1] * count / rank
        running_minimum = min(running_minimum, candidate)
        adjusted_sorted[position] = running_minimum

    adjusted = [0.0] * count
    for position, (original_index, _) in enumerate(ranked):
        adjusted[original_index] = adjusted_sorted[position]

    rejected = [value <= threshold for value in adjusted]
    return adjusted, rejected


def _validate_alpha(alpha: Real) -> float:
    if isinstance(alpha, bool) or not isinstance(alpha, Real):
        raise TypeError("alpha must be a real number")
    value = float(alpha)
    if not math.isfinite(value) or not 0.0 < value < 1.0:
        raise ValueError("alpha must be finite and strictly between 0 and 1")
    return value


def _validate_p_value(p_value: Real, index: int) -> float:
    if isinstance(p_value, bool) or not isinstance(p_value, Real):
        raise TypeError(f"p_values[{index}] must be a real number")
    value = float(p_value)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"p_values[{index}] must be finite and between 0 and 1")
    return value


__all__ = ["benjamini_hochberg"]
