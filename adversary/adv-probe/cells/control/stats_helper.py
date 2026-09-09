"""Compute descriptive statistics and a Welch t-test for groups A and B.

The module uses only the Python standard library.  Run it directly to print a
report, or import :func:`read_scores`, :func:`calculate_group_stats`,
:func:`welch_t_test`, or :func:`analyze_scores`.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import Path
from typing import Iterable, Mapping, Sequence

DEFAULT_DATA_PATH = Path(__file__).resolve().parent / "data" / "scores.csv"
DEFAULT_ALPHA = 0.05
_REQUIRED_GROUPS = ("A", "B")


def read_scores(csv_path: str | Path = DEFAULT_DATA_PATH) -> dict[str, list[float]]:
    """Read finite scores for groups A and B from ``csv_path``.

    The CSV must contain ``group`` and ``score`` columns.  A descriptive
    ``ValueError`` is raised for malformed rows, unexpected groups, or groups
    with fewer than two observations (the minimum needed for a sample standard
    deviation and a Welch t-test).
    """

    path = Path(csv_path)
    grouped: dict[str, list[float]] = {group: [] for group in _REQUIRED_GROUPS}

    try:
        handle = path.open("r", encoding="utf-8", newline="")
    except OSError as exc:
        raise OSError(f"Could not open scores CSV {path}: {exc}") from exc

    with handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"Scores CSV {path} is empty")
        missing_columns = {"group", "score"}.difference(reader.fieldnames)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"Scores CSV {path} is missing column(s): {missing}")

        for row_number, row in enumerate(reader, start=2):
            group = (row.get("group") or "").strip()
            if group not in grouped:
                raise ValueError(
                    f"Unexpected group {group!r} on row {row_number}; expected A or B"
                )
            raw_score = (row.get("score") or "").strip()
            try:
                score = float(raw_score)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid score {raw_score!r} on row {row_number}"
                ) from exc
            if not math.isfinite(score):
                raise ValueError(f"Non-finite score {raw_score!r} on row {row_number}")
            grouped[group].append(score)

    for group, values in grouped.items():
        if len(values) < 2:
            raise ValueError(
                f"Group {group} has {len(values)} observation(s); at least 2 are required"
            )
    return grouped


def _finite_values(values: Iterable[float], label: str) -> list[float]:
    """Materialize and validate a numeric sample."""

    try:
        sample = [float(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} contains a non-numeric value") from exc
    if len(sample) < 2:
        raise ValueError(f"{label} needs at least 2 observations")
    if not all(math.isfinite(value) for value in sample):
        raise ValueError(f"{label} contains a non-finite value")
    return sample


def calculate_group_stats(
    grouped_scores: Mapping[str, Iterable[float]],
) -> dict[str, dict[str, int | float]]:
    """Return count, arithmetic mean, and sample standard deviation by group."""

    output: dict[str, dict[str, int | float]] = {}
    for group in _REQUIRED_GROUPS:
        if group not in grouped_scores:
            raise ValueError(f"Missing required group {group}")
        values = _finite_values(grouped_scores[group], f"Group {group}")
        output[group] = {
            "count": len(values),
            "mean": statistics.fmean(values),
            "standard_deviation": statistics.stdev(values),
        }
    return output


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    """Evaluate the continued fraction used by the incomplete beta function."""

    max_iterations = 200
    epsilon = 3.0e-14
    tiny = 1.0e-300

    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    result = d

    for iteration in range(1, max_iterations + 1):
        twice_iteration = 2 * iteration
        coefficient = (
            iteration * (b - iteration) * x
            / ((qam + twice_iteration) * (a + twice_iteration))
        )
        d = 1.0 + coefficient * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + coefficient / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        result *= d * c

        coefficient = -(
            (a + iteration)
            * (qab + iteration)
            * x
            / ((a + twice_iteration) * (qap + twice_iteration))
        )
        d = 1.0 + coefficient * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + coefficient / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        step = d * c
        result *= step
        if abs(step - 1.0) <= epsilon:
            return result

    raise ArithmeticError("Incomplete beta calculation did not converge")


def _regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    """Return the regularized incomplete beta I_x(a, b)."""

    if a <= 0.0 or b <= 0.0:
        raise ValueError("Beta parameters must be positive")
    if not 0.0 <= x <= 1.0:
        raise ValueError("x must be between 0 and 1")
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0

    factor = math.exp(
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        value = factor * _beta_continued_fraction(a, b, x) / a
    else:
        value = 1.0 - factor * _beta_continued_fraction(b, a, 1.0 - x) / b
    # Suppress harmless floating-point excursions just outside [0, 1].
    return min(1.0, max(0.0, value))


def welch_t_test(
    group_a: Iterable[float],
    group_b: Iterable[float],
    alpha: float = DEFAULT_ALPHA,
) -> dict[str, float | bool]:
    """Perform a two-sided Welch independent-samples t-test.

    Welch's test does not assume equal population variances.  The returned
    mean difference and t statistic use the direction ``A - B``.
    """

    if not math.isfinite(alpha) or not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be a finite number strictly between 0 and 1")

    a_values = _finite_values(group_a, "Group A")
    b_values = _finite_values(group_b, "Group B")
    mean_a = statistics.fmean(a_values)
    mean_b = statistics.fmean(b_values)
    variance_a = statistics.variance(a_values)
    variance_b = statistics.variance(b_values)
    component_a = variance_a / len(a_values)
    component_b = variance_b / len(b_values)
    squared_standard_error = component_a + component_b
    difference = mean_a - mean_b

    if squared_standard_error == 0.0:
        # Both samples are constant.  Equal constants provide no evidence of a
        # difference; unequal constants imply a difference with zero SE.
        t_statistic = 0.0 if difference == 0.0 else math.copysign(math.inf, difference)
        degrees_of_freedom = math.inf
        p_value = 1.0 if difference == 0.0 else 0.0
    else:
        standard_error = math.sqrt(squared_standard_error)
        t_statistic = difference / standard_error
        denominator = (
            component_a**2 / (len(a_values) - 1)
            + component_b**2 / (len(b_values) - 1)
        )
        degrees_of_freedom = squared_standard_error**2 / denominator
        beta_x = degrees_of_freedom / (
            degrees_of_freedom + t_statistic * t_statistic
        )
        p_value = _regularized_incomplete_beta(
            beta_x, degrees_of_freedom / 2.0, 0.5
        )

    return {
        "mean_difference_A_minus_B": difference,
        "t_statistic": t_statistic,
        "degrees_of_freedom": degrees_of_freedom,
        "p_value": p_value,
        "alpha": alpha,
        "significant": p_value < alpha,
    }


def analyze_scores(
    csv_path: str | Path = DEFAULT_DATA_PATH,
    alpha: float = DEFAULT_ALPHA,
) -> dict[str, object]:
    """Read the CSV and return group summaries plus a Welch t-test result."""

    grouped = read_scores(csv_path)
    return {
        "groups": calculate_group_stats(grouped),
        "comparison": welch_t_test(grouped["A"], grouped["B"], alpha),
    }


def format_report(analysis: Mapping[str, object]) -> str:
    """Format an :func:`analyze_scores` result as a human-readable report."""

    groups = analysis["groups"]
    comparison = analysis["comparison"]
    if not isinstance(groups, Mapping) or not isinstance(comparison, Mapping):
        raise ValueError("analysis must contain 'groups' and 'comparison' mappings")

    lines: list[str] = []
    for group in _REQUIRED_GROUPS:
        stats = groups[group]
        if not isinstance(stats, Mapping):
            raise ValueError(f"Statistics for group {group} must be a mapping")
        lines.append(
            f"Group {group}: n={stats['count']}, mean={float(stats['mean']):.6f}, "
            f"sample SD={float(stats['standard_deviation']):.6f}"
        )
    decision = "yes" if comparison["significant"] else "no"
    lines.append(
        "Welch two-sided t-test (A - B): "
        f"difference={float(comparison['mean_difference_A_minus_B']):.6f}, "
        f"t={float(comparison['t_statistic']):.6f}, "
        f"df={float(comparison['degrees_of_freedom']):.6f}, "
        f"p={float(comparison['p_value']):.6g}; "
        f"significant at alpha={float(comparison['alpha']):g}: {decision}"
    )
    return "\n".join(lines)


def main() -> None:
    """Print the default analysis as JSON and as a compact text report."""

    analysis = analyze_scores()
    print(json.dumps(analysis, indent=2, sort_keys=True))
    print()
    print(format_report(analysis))


if __name__ == "__main__":
    main()
