"""Compute descriptive statistics and a Welch t-test for groups A and B."""

from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import Path
from typing import Iterable

DEFAULT_DATA_PATH = Path(__file__).resolve().parent / "data" / "scores.csv"


def read_scores(csv_path: str | Path = DEFAULT_DATA_PATH) -> dict[str, list[float]]:
    """Read scores for groups A and B from a CSV file."""
    path = Path(csv_path)
    groups: dict[str, list[float]] = {"A": [], "B": []}

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required_columns = {"group", "score"}
        if reader.fieldnames is None or not required_columns.issubset(reader.fieldnames):
            raise ValueError("CSV must contain 'group' and 'score' columns")

        for row_number, row in enumerate(reader, start=2):
            group = (row.get("group") or "").strip()
            if group not in groups:
                raise ValueError(f"Unexpected group {group!r} on row {row_number}")
            try:
                score = float(row["score"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid score on row {row_number}") from exc
            if not math.isfinite(score):
                raise ValueError(f"Non-finite score on row {row_number}")
            groups[group].append(score)

    for group, values in groups.items():
        if len(values) < 2:
            raise ValueError(f"Group {group} needs at least two scores")
    return groups


def summarize_group(values: Iterable[float]) -> dict[str, float | int]:
    """Return count, arithmetic mean, and sample standard deviation."""
    sample = [float(value) for value in values]
    if len(sample) < 2:
        raise ValueError("At least two values are required")
    if not all(math.isfinite(value) for value in sample):
        raise ValueError("All values must be finite")
    return {
        "n": len(sample),
        "mean": statistics.mean(sample),
        "standard_deviation": statistics.stdev(sample),
    }


def _continued_fraction_beta(a: float, b: float, x: float) -> float:
    """Evaluate the continued fraction used by regularized incomplete beta."""
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
        even_step = 2 * iteration
        coefficient = iteration * (b - iteration) * x / (
            (qam + even_step) * (a + even_step)
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
            / ((a + even_step) * (qap + even_step))
        )
        d = 1.0 + coefficient * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + coefficient / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        change = d * c
        result *= change
        if abs(change - 1.0) <= epsilon:
            return result

    raise ArithmeticError("Incomplete beta calculation did not converge")


def _regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    """Compute the regularized incomplete beta function I_x(a, b)."""
    if a <= 0.0 or b <= 0.0:
        raise ValueError("Beta parameters must be positive")
    if not 0.0 <= x <= 1.0:
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
        return factor * _continued_fraction_beta(a, b, x) / a
    return 1.0 - factor * _continued_fraction_beta(b, a, 1.0 - x) / b


def _two_sided_t_p_value(t_statistic: float, degrees_of_freedom: float) -> float:
    """Return a two-sided p-value for a Student t statistic."""
    if degrees_of_freedom <= 0.0 or not math.isfinite(degrees_of_freedom):
        raise ValueError("Degrees of freedom must be finite and positive")
    x = degrees_of_freedom / (degrees_of_freedom + t_statistic**2)
    return min(1.0, max(0.0, _regularized_incomplete_beta(
        degrees_of_freedom / 2.0, 0.5, x
    )))


def welch_t_test(
    group_a: Iterable[float],
    group_b: Iterable[float],
    alpha: float = 0.05,
) -> dict[str, float | bool]:
    """Compare two independent samples with a two-sided Welch t-test."""
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between zero and one")

    a = [float(value) for value in group_a]
    b = [float(value) for value in group_b]
    if len(a) < 2 or len(b) < 2:
        raise ValueError("Each group needs at least two values")
    if not all(math.isfinite(value) for value in a + b):
        raise ValueError("All values must be finite")

    mean_a = statistics.mean(a)
    mean_b = statistics.mean(b)
    variance_a = statistics.variance(a)
    variance_b = statistics.variance(b)
    variance_of_difference = variance_a / len(a) + variance_b / len(b)
    if variance_of_difference == 0.0:
        raise ValueError("Welch t-test is undefined when both groups have zero variance")

    t_statistic = (mean_a - mean_b) / math.sqrt(variance_of_difference)
    denominator = (
        (variance_a / len(a)) ** 2 / (len(a) - 1)
        + (variance_b / len(b)) ** 2 / (len(b) - 1)
    )
    degrees_of_freedom = variance_of_difference**2 / denominator
    p_value = _two_sided_t_p_value(t_statistic, degrees_of_freedom)

    return {
        "mean_difference": mean_a - mean_b,
        "t_statistic": t_statistic,
        "degrees_of_freedom": degrees_of_freedom,
        "p_value": p_value,
        "alpha": alpha,
        "significant": p_value < alpha,
    }


def analyze_scores(
    csv_path: str | Path = DEFAULT_DATA_PATH,
    alpha: float = 0.05,
) -> dict[str, object]:
    """Read the CSV and return summaries plus the A-versus-B comparison."""
    groups = read_scores(csv_path)
    return {
        "groups": {
            "A": summarize_group(groups["A"]),
            "B": summarize_group(groups["B"]),
        },
        "comparison": welch_t_test(groups["A"], groups["B"], alpha),
    }


def main() -> None:
    """Print the default analysis as JSON."""
    print(json.dumps(analyze_scores(), indent=2))


if __name__ == "__main__":
    main()
