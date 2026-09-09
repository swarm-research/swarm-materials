"""Descriptive statistics and a Welch two-sample t-test for score data."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from pathlib import Path
from typing import Iterable

DEFAULT_DATA_PATH = Path(__file__).resolve().parent / "data" / "scores.csv"
EXPECTED_GROUPS = ("A", "B")


def load_scores(path: str | Path = DEFAULT_DATA_PATH) -> dict[str, list[float]]:
    """Load and validate scores for groups A and B from a CSV file."""
    scores = {group: [] for group in EXPECTED_GROUPS}
    csv_path = Path(path)

    with csv_path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        required_columns = {"group", "score"}
        if reader.fieldnames is None or not required_columns.issubset(reader.fieldnames):
            raise ValueError("CSV must contain 'group' and 'score' columns")

        for row_number, row in enumerate(reader, start=2):
            group = (row.get("group") or "").strip()
            if group not in scores:
                raise ValueError(
                    f"row {row_number}: expected group A or B, got {group!r}"
                )
            try:
                score = float(row["score"])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"row {row_number}: invalid score {row.get('score')!r}"
                ) from exc
            if not math.isfinite(score):
                raise ValueError(f"row {row_number}: score must be finite")
            scores[group].append(score)

    for group, values in scores.items():
        if len(values) < 2:
            raise ValueError(
                f"group {group} needs at least two scores to compute sample statistics"
            )
    return scores


def summarize(values: Iterable[float]) -> dict[str, int | float]:
    """Return count, arithmetic mean, and sample standard deviation."""
    sample = list(values)
    if len(sample) < 2:
        raise ValueError("at least two values are required")
    if not all(math.isfinite(value) for value in sample):
        raise ValueError("all values must be finite")
    return {
        "n": len(sample),
        "mean": statistics.fmean(sample),
        "standard_deviation": statistics.stdev(sample),
    }


def _continued_beta_fraction(a: float, b: float, x: float) -> float:
    """Evaluate the continued fraction used by the incomplete beta function."""
    max_iterations = 200
    epsilon = 3.0e-14
    minimum = 1.0e-300

    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < minimum:
        d = minimum
    d = 1.0 / d
    result = d

    for iteration in range(1, max_iterations + 1):
        twice_iteration = 2 * iteration
        coefficient = (
            iteration * (b - iteration) * x
            / ((qam + twice_iteration) * (a + twice_iteration))
        )
        d = 1.0 + coefficient * d
        if abs(d) < minimum:
            d = minimum
        c = 1.0 + coefficient / c
        if abs(c) < minimum:
            c = minimum
        d = 1.0 / d
        result *= d * c

        coefficient = -(
            (a + iteration)
            * (qab + iteration)
            * x
            / ((a + twice_iteration) * (qap + twice_iteration))
        )
        d = 1.0 + coefficient * d
        if abs(d) < minimum:
            d = minimum
        c = 1.0 + coefficient / c
        if abs(c) < minimum:
            c = minimum
        d = 1.0 / d
        change = d * c
        result *= change
        if abs(change - 1.0) <= epsilon:
            return result

    raise ArithmeticError("incomplete beta calculation did not converge")


def _regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    """Compute the regularized incomplete beta function I_x(a, b)."""
    if not 0.0 <= x <= 1.0:
        raise ValueError("x must be between zero and one")
    if a <= 0.0 or b <= 0.0:
        raise ValueError("a and b must be positive")
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0

    scale = math.exp(
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return scale * _continued_beta_fraction(a, b, x) / a
    return 1.0 - scale * _continued_beta_fraction(b, a, 1.0 - x) / b


def _two_sided_t_p_value(t_statistic: float, degrees_of_freedom: float) -> float:
    """Return the two-sided p-value for a Student t statistic."""
    if degrees_of_freedom <= 0.0:
        raise ValueError("degrees of freedom must be positive")
    if math.isnan(t_statistic):
        raise ValueError("t statistic cannot be NaN")
    if math.isinf(t_statistic):
        return 0.0
    if math.isinf(degrees_of_freedom):
        return math.erfc(abs(t_statistic) / math.sqrt(2.0))

    x = degrees_of_freedom / (degrees_of_freedom + t_statistic**2)
    p_value = _regularized_incomplete_beta(
        x, degrees_of_freedom / 2.0, 0.5
    )
    return min(1.0, max(0.0, p_value))


def welch_t_test(
    group_a: Iterable[float],
    group_b: Iterable[float],
    alpha: float = 0.05,
) -> dict[str, float | bool]:
    """Run a two-sided Welch t-test for two independent groups."""
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between zero and one")

    values_a = list(group_a)
    values_b = list(group_b)
    summary_a = summarize(values_a)
    summary_b = summarize(values_b)
    variance_a = float(summary_a["standard_deviation"]) ** 2
    variance_b = float(summary_b["standard_deviation"]) ** 2
    component_a = variance_a / len(values_a)
    component_b = variance_b / len(values_b)
    standard_error_squared = component_a + component_b
    mean_difference = float(summary_a["mean"]) - float(summary_b["mean"])

    if standard_error_squared == 0.0:
        if mean_difference == 0.0:
            t_statistic = 0.0
            degrees_of_freedom = math.inf
            p_value = 1.0
        else:
            t_statistic = math.copysign(math.inf, mean_difference)
            degrees_of_freedom = math.inf
            p_value = 0.0
    else:
        t_statistic = mean_difference / math.sqrt(standard_error_squared)
        denominator = (
            component_a**2 / (len(values_a) - 1)
            + component_b**2 / (len(values_b) - 1)
        )
        degrees_of_freedom = standard_error_squared**2 / denominator
        p_value = _two_sided_t_p_value(t_statistic, degrees_of_freedom)

    return {
        "mean_difference": mean_difference,
        "t_statistic": t_statistic,
        "degrees_of_freedom": degrees_of_freedom,
        "p_value": p_value,
        "alpha": alpha,
        "significant": p_value < alpha,
    }


def analyze_scores(
    path: str | Path = DEFAULT_DATA_PATH,
    alpha: float = 0.05,
) -> dict[str, dict[str, int | float] | dict[str, float | bool]]:
    """Load the CSV and return group summaries plus a Welch t-test result."""
    scores = load_scores(path)
    return {
        "A": summarize(scores["A"]),
        "B": summarize(scores["B"]),
        "comparison": welch_t_test(scores["A"], scores["B"], alpha),
    }


def format_report(
    result: dict[str, dict[str, int | float] | dict[str, float | bool]],
) -> str:
    """Format an ``analyze_scores`` result as a human-readable report."""
    group_a = result["A"]
    group_b = result["B"]
    comparison = result["comparison"]
    verdict = "yes" if comparison["significant"] else "no"
    return "\n".join(
        (
            f"Group A: n={group_a['n']}, mean={group_a['mean']:.4f}, "
            f"sample SD={group_a['standard_deviation']:.4f}",
            f"Group B: n={group_b['n']}, mean={group_b['mean']:.4f}, "
            f"sample SD={group_b['standard_deviation']:.4f}",
            f"Welch two-sided t-test: t={comparison['t_statistic']:.4f}, "
            f"df={comparison['degrees_of_freedom']:.4f}, "
            f"p={comparison['p_value']:.6g}; statistically significant at "
            f"alpha={comparison['alpha']:.4g}: {verdict}",
        )
    )


def main() -> None:
    """Run the helper as a command-line report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=DEFAULT_DATA_PATH,
        help="score CSV path (default: data/scores.csv beside this module)",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="significance threshold (default: 0.05)",
    )
    arguments = parser.parse_args()
    print(format_report(analyze_scores(arguments.path, arguments.alpha)))


if __name__ == "__main__":
    main()
