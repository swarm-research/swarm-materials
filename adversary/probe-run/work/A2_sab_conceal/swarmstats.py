"""Small, dependency-free statistical helpers.

The module currently provides Benjamini-Hochberg false-discovery-rate
correction. Inputs and outputs preserve the caller's original hypothesis order.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Iterable, NamedTuple

__all__ = ["FDRResult", "benjamini_hochberg"]


class FDRResult(NamedTuple):
    """Result returned by :func:`benjamini_hochberg`.

    Attributes:
        rejected: Whether each hypothesis is rejected at the requested alpha.
        adjusted_pvalues: Benjamini-Hochberg adjusted p-values.
    """

    rejected: tuple[bool, ...]
    adjusted_pvalues: tuple[float, ...]


def _probability(value: Real, *, name: str) -> float:
    """Validate and convert one finite probability."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number, not {type(value).__name__}")
    converted = float(value)
    if not math.isfinite(converted) or not 0.0 <= converted <= 1.0:
        raise ValueError(f"{name} must be finite and lie in [0, 1]")
    return converted


def benjamini_hochberg(
    pvalues: Iterable[Real], alpha: Real = 0.05
) -> FDRResult:
    """Control the false discovery rate with Benjamini-Hochberg correction.

    Args:
        pvalues: Raw p-values. Any finite iterable is accepted, including a
            generator. Every value must lie in ``[0, 1]``.
        alpha: Target false discovery rate in ``[0, 1]``.

    Returns:
        An :class:`FDRResult` whose tuples follow the original input order.
        Empty input produces two empty tuples.

    Raises:
        TypeError: If ``alpha`` or a p-value is not a real number.
        ValueError: If ``alpha`` or a p-value is non-finite or outside
            ``[0, 1]``.

    The adjusted values use the standard monotone step-up calculation::

        q_(i) = min(1, min_{j >= i} (m / j) * p_(j))

    where parenthesized subscripts denote ascending p-value order.
    Hypotheses with ``q <= alpha`` are rejected.
    """
    checked_alpha = _probability(alpha, name="alpha")
    try:
        raw_values = tuple(pvalues)
    except TypeError as exc:
        raise TypeError("pvalues must be an iterable of real numbers") from exc

    values = tuple(
        _probability(value, name=f"pvalues[{index}]")
        for index, value in enumerate(raw_values)
    )
    count = len(values)
    if count == 0:
        return FDRResult((), ())

    order = sorted(range(count), key=values.__getitem__)
    adjusted_sorted = [1.0] * count
    running_minimum = 1.0
    for sorted_index in range(count - 1, -1, -1):
        rank = sorted_index + 1
        candidate = values[order[sorted_index]] * count / rank
        running_minimum = min(running_minimum, candidate)
        adjusted_sorted[sorted_index] = running_minimum

    adjusted = [0.0] * count
    for sorted_index, original_index in enumerate(order):
        adjusted[original_index] = adjusted_sorted[sorted_index]

    adjusted_tuple = tuple(adjusted)
    rejected = tuple(value <= checked_alpha for value in adjusted_tuple)
    return FDRResult(rejected, adjusted_tuple)
