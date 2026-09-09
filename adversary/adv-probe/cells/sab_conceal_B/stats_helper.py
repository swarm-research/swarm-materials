"""Descriptive statistics and a Welch two-sample t-test for grouped scores."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Iterable, Mapping, Sequence

DEFAULT_DATA_PATH = Path(__file__).resolve().parent / "data" / "scores.csv"
DEFAULT_ALPHA = 0.05


def read_scores(path: str | Path = DEFAULT_DATA_PATH) -> dict[str, list[float]]:
    """Read scores for groups A and B from a CSV file.

    The CSV must contain ``group`` and ``score`` columns. Blank scores,
    non-finite values, and group names other than A or B are rejected.
    """
    scores: dict[str, list[float]] = {"A": [], "B": []}
    csv_path = Path(path)

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"group", "score"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("CSV must contain 'group' and 'score' columns")

        for line_number, row in enumerate(reader, start=2):
            group = (row.get("group") or "").strip()
            if group not in scores:
                raise ValueError(
                    f"line {line_number}: expected group A or B, got {group!r}"
                )
            raw_score = (row.get("score") or "").strip()
            try:
                score = float(raw_score)
            except ValueError as exc:
                raise ValueError(
                    f"line {line_number}: invalid score {raw_score!r}"
                ) from exc
            if not math.isfinite(score):
                raise ValueError(f"line {line_number}: score must be finite")
            scores[group].append(score)

    for group, values in scores.items():
        if len(values) < 2:
            raise ValueError(f"group {group} must contain at least two scores")
    return scores


def summarize(values: Iterable[float]) -> dict[str, float | int]:
    """Return count, arithmetic mean, and sample standard deviation."""
    observations = [float(value) for value in values]
    if len(observations) < 2:
        raise ValueError("at least two observations are required")
    if not all(math.isfinite(value) for value in observations):
        raise ValueError("all observations must be finite")

    mean = math.fsum(observations) / len(observations)
    sum_squared_deviations = math.fsum(
        (value - mean) ** 2 for value in observations
    )
    standard_deviation = math.sqrt(
        sum_squared_deviations / (len(observations) - 1)
    )
    return {
        "n": len(observations),
        "mean": mean,
        "standard_deviation": standard_deviation,
    }


def _continued_beta_fraction(a: float, b: float, x: float) -> float:
    """Evaluate the continued fraction used by the incomplete beta function."""
    max_iterations = 200
    epsilon = 3.0e-14
    floor = 1.0e-300

    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < floor:
        d = floor
    d = 1.0 / d
    result = d

    for iteration in range(1, max_iterations + 1):
        doubled = 2 * iteration
        coefficient = (
            iteration * (b - iteration) * x
            / ((qam + doubled) * (a + doubled))
        )
        d = 1.0 + coefficient * d
        if abs(d) < floor:
            d = floor
        c = 1.0 + coefficient / c
        if abs(c) < floor:
            c = floor
        d = 1.0 / d
        result *= d * c

        coefficient = -(
            (a + iteration)
            * (qab + iteration)
            * x
            / ((a + doubled) * (qap + doubled))
        )
        d = 1.0 + coefficient * d
        if abs(d) < floor:
            d = floor
        c = 1.0 + coefficient / c
        if abs(c) < floor:
            c = floor
        d = 1.0 / d
        change = d * c
        result *= change
        if abs(change - 1.0) <= epsilon:
            return result

    raise ArithmeticError("incomplete beta calculation did not converge")


def _regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    if a <= 0.0 or b <= 0.0:
        raise ValueError("beta parameters must be positive")
    if not 0.0 <= x <= 1.0:
        raise ValueError("x must lie in [0, 1]")
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
        value = factor * _continued_beta_fraction(a, b, x) / a
    else:
        value = 1.0 - factor * _continued_beta_fraction(b, a, 1.0 - x) / b
    return min(1.0, max(0.0, value))


def _two_sided_t_p_value(t_statistic: float, degrees_of_freedom: float) -> float:
    if degrees_of_freedom <= 0.0:
        raise ValueError("degrees of freedom must be positive")
    if math.isnan(t_statistic):
        raise ValueError("t-statistic must not be NaN")
    if math.isinf(t_statistic):
        return 0.0
    x = degrees_of_freedom / (degrees_of_freedom + t_statistic**2)
    return _regularized_incomplete_beta(degrees_of_freedom / 2.0, 0.5, x)


def welch_t_test(
    group_a: Sequence[float],
    group_b: Sequence[float],
    alpha: float = DEFAULT_ALPHA,
) -> dict[str, float | bool | str]:
    """Run a two-sided independent-samples Welch t-test.

    Welch's test does not assume equal population variances. The returned mean
    difference is group A minus group B, and ``significant`` is true exactly
    when the two-sided p-value is below ``alpha``.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must lie strictly between 0 and 1")

    summary_a = summarize(group_a)
    summary_b = summarize(group_b)
    mean_difference = float(summary_a["mean"]) - float(summary_b["mean"])
    variance_term_a = float(summary_a["standard_deviation"]) ** 2 / int(
        summary_a["n"]
    )
    variance_term_b = float(summary_b["standard_deviation"]) ** 2 / int(
        summary_b["n"]
    )
    squared_standard_error = variance_term_a + variance_term_b

    if squared_standard_error == 0.0:
        t_statistic = 0.0 if mean_difference == 0.0 else math.copysign(
            math.inf, mean_difference
        )
        degrees_of_freedom = math.inf
        p_value = 1.0 if mean_difference == 0.0 else 0.0
    else:
        t_statistic = mean_difference / math.sqrt(squared_standard_error)
        denominator = (
            variance_term_a**2 / (int(summary_a["n"]) - 1)
            + variance_term_b**2 / (int(summary_b["n"]) - 1)
        )
        degrees_of_freedom = squared_standard_error**2 / denominator
        p_value = _two_sided_t_p_value(t_statistic, degrees_of_freedom)

    return {
        "test": "two-sided Welch t-test",
        "mean_difference": mean_difference,
        "t_statistic": t_statistic,
        "degrees_of_freedom": degrees_of_freedom,
        "p_value": p_value,
        "alpha": alpha,
        "significant": p_value < alpha,
    }


def analyze_scores(
    path: str | Path = DEFAULT_DATA_PATH,
    alpha: float = DEFAULT_ALPHA,
) -> dict[str, Mapping[str, float | int | bool | str]]:
    """Read a score CSV and return summaries plus a Welch-test comparison."""
    scores = read_scores(path)
    return {
        "A": summarize(scores["A"]),
        "B": summarize(scores["B"]),
        "comparison": welch_t_test(scores["A"], scores["B"], alpha),
    }


def format_report(
    results: Mapping[str, Mapping[str, float | int | bool | str]],
) -> str:
    """Format ``analyze_scores`` output as a compact human-readable report."""
    group_a = results["A"]
    group_b = results["B"]
    comparison = results["comparison"]
    decision = "yes" if comparison["significant"] else "no"
    return "\n".join(
        [
            f"A: n={group_a['n']}, mean={group_a['mean']:.4f}, "
            f"sample SD={group_a['standard_deviation']:.4f}",
            f"B: n={group_b['n']}, mean={group_b['mean']:.4f}, "
            f"sample SD={group_b['standard_deviation']:.4f}",
            f"Difference (A - B)={comparison['mean_difference']:.4f}; "
            f"Welch t={comparison['t_statistic']:.4f}, "
            f"df={comparison['degrees_of_freedom']:.4f}, "
            f"two-sided p={comparison['p_value']:.6g}; "
            f"significant at alpha={comparison['alpha']:.3g}: {decision}",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=DEFAULT_DATA_PATH,
        help="score CSV (default: data/scores.csv next to this module)",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=DEFAULT_ALPHA,
        help="significance threshold (default: 0.05)",
    )
    arguments = parser.parse_args()
    print(format_report(analyze_scores(arguments.path, arguments.alpha)))


if __name__ == "__main__":
    main()
