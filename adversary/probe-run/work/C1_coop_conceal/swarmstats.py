"""Small, dependency-free statistical helpers.

The module currently provides Benjamini-Hochberg correction for controlling the
false discovery rate across a family of hypothesis tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real
from typing import Iterable, Optional, Tuple

__all__ = ["FDRResult", "benjamini_hochberg"]


@dataclass(frozen=True)
class FDRResult:
    """Result of a Benjamini-Hochberg correction.

    Attributes:
        adjusted_pvalues: BH-adjusted p-values in the input order.
        reject: Decisions in the input order; ``True`` means reject the null.
        critical_pvalue: Largest raw p-value rejected, or ``None`` if no
            hypothesis was rejected.
        alpha: False-discovery-rate level used for the decisions.
    """

    adjusted_pvalues: Tuple[float, ...]
    reject: Tuple[bool, ...]
    critical_pvalue: Optional[float]
    alpha: float

    @property
    def n_rejected(self) -> int:
        """Return the number of rejected hypotheses."""

        return sum(self.reject)


def _as_probability(value: Real, *, name: str) -> float:
    """Validate and convert one real-valued probability."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number, got {type(value).__name__}")
    converted = float(value)
    if not isfinite(converted):
        raise ValueError(f"{name} must be finite, got {value!r}")
    if not 0.0 <= converted <= 1.0:
        raise ValueError(f"{name} must lie in [0, 1], got {value!r}")
    return converted


def benjamini_hochberg(
    pvalues: Iterable[Real], alpha: Real = 0.05
) -> FDRResult:
    """Control false discovery rate with the Benjamini-Hochberg procedure.

    The procedure assumes independent tests or positive dependence. It computes
    the usual step-up decisions and monotone adjusted p-values. Both returned
    tuples follow the original input order, not the sorted order used by the
    calculation. The iterable is consumed exactly once.

    Args:
        pvalues: Finite real p-values in the closed interval ``[0, 1]``.
        alpha: Desired false-discovery-rate level, strictly between zero and one.

    Returns:
        An :class:`FDRResult` containing adjusted values, decisions, and cutoff.
        Empty input produces empty tuples and a ``None`` cutoff.

    Raises:
        TypeError: If ``alpha`` or a p-value is not a real number.
        ValueError: If a value is non-finite or outside its allowed interval.

    Example:
        >>> result = benjamini_hochberg([0.01, 0.04, 0.03, 0.002], alpha=0.025)
        >>> result.adjusted_pvalues
        (0.02, 0.04, 0.04, 0.008)
        >>> result.reject
        (True, False, False, True)
        >>> result.critical_pvalue
        0.01
    """

    alpha_value = _as_probability(alpha, name="alpha")
    if alpha_value == 0.0 or alpha_value == 1.0:
        raise ValueError(f"alpha must lie strictly between 0 and 1, got {alpha!r}")

    try:
        raw_values = tuple(pvalues)
    except TypeError as exc:
        raise TypeError("pvalues must be an iterable of real numbers") from exc

    values = tuple(
        _as_probability(value, name=f"pvalues[{index}]")
        for index, value in enumerate(raw_values)
    )
    count = len(values)
    if count == 0:
        return FDRResult((), (), None, alpha_value)

    ordered = sorted(enumerate(values), key=lambda item: item[1])

    adjusted = [0.0] * count
    running_minimum = 1.0
    for rank_index in range(count - 1, -1, -1):
        rank = rank_index + 1
        original_index, pvalue = ordered[rank_index]
        running_minimum = min(running_minimum, pvalue * count / rank)
        adjusted[original_index] = running_minimum

    qualifying_ranks = [
        rank
        for rank, (_, pvalue) in enumerate(ordered, start=1)
        if pvalue <= alpha_value * rank / count
    ]
    if qualifying_ranks:
        cutoff = ordered[qualifying_ranks[-1] - 1][1]
        rejected = tuple(pvalue <= cutoff for pvalue in values)
    else:
        cutoff = None
        rejected = (False,) * count

    return FDRResult(tuple(adjusted), rejected, cutoff, alpha_value)
