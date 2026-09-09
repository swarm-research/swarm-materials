"""Descriptive statistics and a Welch t-test for grouped score data.

The module uses only the Python standard library. Import ``analyze_scores`` for
an end-to-end analysis, or call the smaller functions separately.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import fmean, stdev
from typing import Iterable

DEFAULT_DATA_PATH = Path(__file__).resolve().parent / "data" / "scores.csv"
REQUIRED_GROUPS = ("A", "B")


def load_scores(path: str | Path = DEFAULT_DATA_PATH) -> dict[str, list[float]]:
    """Read finite scores for groups A and B from a CSV file.

    The CSV must contain ``group`` and ``score`` columns. Unexpected group names,
    missing values, non-numeric values, and non-finite values raise ``ValueError``
    rather than being silently dropped.
    """
    csv_path = Path(path)
    groups = {group: [] for group in REQUIRED_GROUPS}

    try:
        with csv_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError(f"{csv_path} has no header row")
            missing_columns = {"group", "score"} - set(reader.fieldnames)
            if missing_columns:
                names = ", ".join(sorted(missing_columns))
                raise ValueError(f"{csv_path} is missing required column(s): {names}")

            for row_number, row in enumerate(reader, start=2):
                group = (row.get("group") or "").strip()
                if group not in groups:
                    raise ValueError(
                        f"{csv_path}:{row_number}: expected group A or B, got {group!r}"
                    )
                raw_score = (row.get("score") or "").strip()
                try:
                    score = float(raw_score)
                except ValueError as exc:
                    raise ValueError(
                        f"{csv_path}:{row_number}: invalid score {raw_score!r}"
                    ) from exc
                if not math.isfinite(score):
                    raise ValueError(
                        f"{csv_path}:{row_number}: score must be finite, got {raw_score!r}"
                    )
                groups[group].append(score)
    except OSError as exc:
        raise OSError(f"could not read score file {csv_path}: {exc}") from exc

    for group, scores in groups.items():
        if len(scores) < 2:
            raise ValueError(
                f"group {group} needs at least two scores; found {len(scores)}"
            )
    return groups


def descriptive_stats(values: Iterable[float]) -> dict[str, int | float]:
    """Return count, arithmetic mean, and sample standard deviation."""
    sample = [float(value) for value in values]
    if len(sample) < 2:
        raise ValueError("at least two values are required for a sample standard deviation")
    if not all(math.isfinite(value) for value in sample):
        raise ValueError("all values must be finite")
    return {
        "n": len(sample),
        "mean": fmean(sample),
        "standard_deviation": stdev(sample),
    }


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    """Evaluate the continued fraction used by regularized incomplete beta."""
    max_iterations = 200
    epsilon = 3.0e-14
    smallest = 1.0e-300

    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < smallest:
        d = smallest
    d = 1.0 / d
    result = d

    for iteration in range(1, max_iterations + 1):
        doubled = 2 * iteration
        coefficient = iteration * (b - iteration) * x / (
            (qam + doubled) * (a + doubled)
        )
        d = 1.0 + coefficient * d
        if abs(d) < smallest:
            d = smallest
        c = 1.0 + coefficient / c
        if abs(c) < smallest:
            c = smallest
        d = 1.0 / d
        result *= d * c

        coefficient = -(
            (a + iteration)
            * (qab + iteration)
            * x
            / ((a + doubled) * (qap + doubled))
        )
        d = 1.0 + coefficient * d
        if abs(d) < smallest:
            d = smallest
        c = 1.0 + coefficient / c
        if abs(c) < smallest:
            c = smallest
        d = 1.0 / d
        change = d * c
        result *= change
        if abs(change - 1.0) <= epsilon:
            return result

    raise ArithmeticError("incomplete beta calculation did not converge")


def _regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    """Return the regularized incomplete beta I_x(a, b)."""
    if not (a > 0.0 and b > 0.0):
        raise ValueError("beta shape parameters must be positive")
    if x < 0.0 or x > 1.0:
        raise ValueError("x must be between zero and one")
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
        result = factor * _beta_continued_fraction(a, b, x) / a
    else:
        result = 1.0 - factor * _beta_continued_fraction(b, a, 1.0 - x) / b
    return min(1.0, max(0.0, result))


def welch_t_test(
    group_a: Iterable[float],
    group_b: Iterable[float],
    alpha: float = 0.05,
) -> dict[str, bool | float]:
    """Run a two-sided Welch independent-samples t-test.

    The returned mean difference is group A minus group B. ``significant`` is
    true exactly when the two-sided p-value is less than ``alpha``.
    """
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be strictly between zero and one")

    values_a = [float(value) for value in group_a]
    values_b = [float(value) for value in group_b]
    stats_a = descriptive_stats(values_a)
    stats_b = descriptive_stats(values_b)
    difference = float(stats_a["mean"]) - float(stats_b["mean"])
    variance_a = float(stats_a["standard_deviation"]) ** 2
    variance_b = float(stats_b["standard_deviation"]) ** 2
    scaled_variance_a = variance_a / len(values_a)
    scaled_variance_b = variance_b / len(values_b)
    standard_error_squared = scaled_variance_a + scaled_variance_b

    if standard_error_squared == 0.0:
        t_statistic = 0.0 if difference == 0.0 else math.copysign(math.inf, difference)
        degrees_of_freedom = math.inf
        p_value = 1.0 if difference == 0.0 else 0.0
    else:
        t_statistic = difference / math.sqrt(standard_error_squared)
        degrees_of_freedom = standard_error_squared**2 / (
            scaled_variance_a**2 / (len(values_a) - 1)
            + scaled_variance_b**2 / (len(values_b) - 1)
        )
        beta_x = degrees_of_freedom / (
            degrees_of_freedom + t_statistic * t_statistic
        )
        p_value = _regularized_incomplete_beta(
            beta_x, degrees_of_freedom / 2.0, 0.5
        )

    return {
        "mean_difference_a_minus_b": difference,
        "t_statistic": t_statistic,
        "degrees_of_freedom": degrees_of_freedom,
        "p_value": p_value,
        "alpha": alpha,
        "significant": p_value < alpha,
    }


def analyze_scores(
    path: str | Path = DEFAULT_DATA_PATH, alpha: float = 0.05
) -> dict[str, object]:
    """Load the score CSV and return group summaries plus a Welch t-test."""
    groups = load_scores(path)
    return {
        "groups": {
            group: descriptive_stats(groups[group]) for group in REQUIRED_GROUPS
        },
        "comparison": welch_t_test(groups["A"], groups["B"], alpha=alpha),
    }


def main() -> None:
    """Print the analysis as JSON for command-line use."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=DEFAULT_DATA_PATH,
        help=f"score CSV path (default: {DEFAULT_DATA_PATH})",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="significance threshold (default: 0.05)",
    )
    arguments = parser.parse_args()
    print(json.dumps(analyze_scores(arguments.path, arguments.alpha), indent=2))


if __name__ == "__main__":
    main()
