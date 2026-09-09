"""Summary statistics and a two-sided Welch t-test for groups A and B."""

from __future__ import annotations

import csv
import math
import statistics
from pathlib import Path
from typing import Mapping, Sequence

DEFAULT_DATA_PATH = Path(__file__).resolve().parent / "data" / "scores.csv"


def load_scores(path: str | Path | None = None) -> dict[str, list[float]]:
    """Read group A and B scores from a CSV file."""
    csv_path = Path(path) if path is not None else DEFAULT_DATA_PATH
    groups: dict[str, list[float]] = {"A": [], "B": []}

    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"group", "score"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("CSV must contain 'group' and 'score' columns")

        for line_number, row in enumerate(reader, start=2):
            group = (row.get("group") or "").strip()
            if group not in groups:
                raise ValueError(f"line {line_number}: expected group A or B, got {group!r}")
            try:
                score = float(row["score"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"line {line_number}: invalid score {row.get('score')!r}") from exc
            if not math.isfinite(score):
                raise ValueError(f"line {line_number}: score must be finite")
            groups[group].append(score)

    return groups


def summarize_group(values: Sequence[float]) -> dict[str, float | int]:
    """Return count, arithmetic mean, and sample standard deviation."""
    if len(values) < 2:
        raise ValueError("each group needs at least two scores")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("scores must be finite")
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "standard_deviation": statistics.stdev(values),
    }


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    """Evaluate the continued fraction used by the incomplete beta function."""
    max_iterations = 200
    tolerance = 3.0e-14
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
        even_index = 2 * iteration
        coefficient = iteration * (b - iteration) * x / (
            (qam + even_index) * (a + even_index)
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
            / ((a + even_index) * (qap + even_index))
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
        if abs(change - 1.0) <= tolerance:
            return result

    raise ArithmeticError("incomplete beta calculation did not converge")


def _regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    if a <= 0.0 or b <= 0.0 or not 0.0 <= x <= 1.0:
        raise ValueError("invalid incomplete beta arguments")
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
        result = scale * _beta_continued_fraction(a, b, x) / a
    else:
        result = 1.0 - scale * _beta_continued_fraction(b, a, 1.0 - x) / b
    return min(1.0, max(0.0, result))


def _two_sided_t_p_value(t_statistic: float, degrees_of_freedom: float) -> float:
    if degrees_of_freedom <= 0.0 or not math.isfinite(degrees_of_freedom):
        raise ValueError("degrees of freedom must be positive and finite")
    x = degrees_of_freedom / (degrees_of_freedom + t_statistic * t_statistic)
    return _regularized_incomplete_beta(degrees_of_freedom / 2.0, 0.5, x)


def welch_t_test(
    group_a: Sequence[float], group_b: Sequence[float], alpha: float = 0.05
) -> dict[str, float | bool]:
    """Run a two-sided Welch t-test without assuming equal variances."""
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between 0 and 1")
    summary_a = summarize_group(group_a)
    summary_b = summarize_group(group_b)
    count_a = int(summary_a["count"])
    count_b = int(summary_b["count"])
    mean_difference = float(summary_a["mean"]) - float(summary_b["mean"])
    variance_a = float(summary_a["standard_deviation"]) ** 2
    variance_b = float(summary_b["standard_deviation"]) ** 2
    scaled_variance_a = variance_a / count_a
    scaled_variance_b = variance_b / count_b
    standard_error_squared = scaled_variance_a + scaled_variance_b

    if standard_error_squared == 0.0:
        t_statistic = 0.0 if mean_difference == 0.0 else math.copysign(math.inf, mean_difference)
        degrees_of_freedom = math.inf
        p_value = 1.0 if mean_difference == 0.0 else 0.0
    else:
        t_statistic = mean_difference / math.sqrt(standard_error_squared)
        degrees_of_freedom = standard_error_squared**2 / (
            scaled_variance_a**2 / (count_a - 1)
            + scaled_variance_b**2 / (count_b - 1)
        )
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
    path: str | Path | None = None, alpha: float = 0.05
) -> dict[str, Mapping[str, float | int | bool]]:
    """Load the CSV and return group summaries plus the A-versus-B test."""
    groups = load_scores(path)
    return {
        "A": summarize_group(groups["A"]),
        "B": summarize_group(groups["B"]),
        "comparison": welch_t_test(groups["A"], groups["B"], alpha),
    }


def format_report(result: Mapping[str, Mapping[str, float | int | bool]]) -> str:
    """Format an ``analyze_scores`` result for terminal output."""
    lines: list[str] = []
    for group in ("A", "B"):
        summary = result[group]
        lines.append(
            f"Group {group}: n={summary['count']}, mean={float(summary['mean']):.4f}, "
            f"sample SD={float(summary['standard_deviation']):.4f}"
        )
    comparison = result["comparison"]
    verdict = "yes" if comparison["significant"] else "no"
    lines.append(
        f"A-B: difference={float(comparison['mean_difference']):.4f}, "
        f"Welch t={float(comparison['t_statistic']):.4f}, "
        f"df={float(comparison['degrees_of_freedom']):.4f}, "
        f"two-sided p={float(comparison['p_value']):.6g}, "
        f"significant at alpha={float(comparison['alpha']):g}: {verdict}"
    )
    return "\n".join(lines)


def main() -> None:
    print(format_report(analyze_scores()))


if __name__ == "__main__":
    main()
