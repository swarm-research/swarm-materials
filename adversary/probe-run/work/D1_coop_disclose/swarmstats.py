"""Small, dependency-free statistical helpers for the shared workspace."""

from __future__ import annotations

import math
from numbers import Real
from statistics import NormalDist

__all__ = ["wilson_interval"]


def wilson_interval(
    successes: int,
    trials: int,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Return a Wilson score confidence interval for a binomial proportion.

    The Wilson interval behaves sensibly for small samples and observed
    proportions of zero or one, where the common normal (Wald) interval does
    not. Bounds are clipped to the mathematically valid range ``[0, 1]``.

    Args:
        successes: Number of successful Bernoulli trials.
        trials: Total number of trials; must be positive.
        confidence: Two-sided confidence level strictly between zero and one.

    Returns:
        A ``(lower, upper)`` pair of floating-point bounds.

    Raises:
        TypeError: If counts are not integers or confidence is not real-valued.
        ValueError: If inputs lie outside their valid ranges.

    Examples:
        >>> lower, upper = wilson_interval(5, 10)
        >>> round(lower, 4), round(upper, 4)
        (0.2366, 0.7634)
        >>> wilson_interval(0, 10)[0]
        0.0
    """
    if isinstance(successes, bool) or not isinstance(successes, int):
        raise TypeError("successes must be an integer")
    if isinstance(trials, bool) or not isinstance(trials, int):
        raise TypeError("trials must be an integer")
    if isinstance(confidence, bool) or not isinstance(confidence, Real):
        raise TypeError("confidence must be a real number")
    if trials <= 0:
        raise ValueError("trials must be positive")
    if not 0 <= successes <= trials:
        raise ValueError("successes must satisfy 0 <= successes <= trials")

    confidence = float(confidence)
    if not math.isfinite(confidence) or not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be finite and strictly between 0 and 1")

    proportion = successes / trials
    z = NormalDist().inv_cdf(0.5 + confidence / 2.0)
    z_squared = z * z
    denominator = 1.0 + z_squared / trials
    center = (proportion + z_squared / (2.0 * trials)) / denominator
    radius = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / trials
            + z_squared / (4.0 * trials * trials)
        )
        / denominator
    )

    return max(0.0, center - radius), min(1.0, center + radius)
