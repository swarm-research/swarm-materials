#!/usr/bin/env python3
"""Generate deterministic MASO cost and execution audit figures."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent

DEPTH_LABELS = ["1–25", "26–50", "51–100", "101–200", "201–300", "301–400", "401+"]
AVG_PROMPT_K = [53.778, 107.608, 168.176, 228.514, 264.247, 443.949, 662.971]

PERCENT_METRICS = [
    ("Prompt / total tokens", 99.6018, "two-round local total"),
    ("Depth >100 / P1 prompt", 80.6313, "Phase-1 prompt"),
    ("Cached / prompt", 71.3275, "two-round prompt"),
    ("Lifecycle duplication upper bound", 17.6950, "two-round total"),
    ("Completion / total tokens", 0.3982, "two-round local total"),
]

FUNNEL = [
    ("Launcher-planned IDs", 964),
    ("Identity log paths", 316),
    ("Entered runner loop", 123),
    ("IDs with HTTP 200", 97),
    ("HTTP 200 + Finished", 64),
]


def style() -> None:
    mpl.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "DejaVu Sans",
            "font.size": 10.5,
            "axes.titlesize": 13,
            "axes.labelsize": 10.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def save(fig: plt.Figure, stem: str) -> None:
    fig.savefig(ROOT / f"{stem}.png", bbox_inches="tight", facecolor="white")
    fig.savefig(ROOT / f"{stem}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def cost_figure() -> None:
    navy = "#183153"
    blue = "#2F6B9A"
    teal = "#2A9D8F"
    orange = "#F4A261"
    red = "#C84630"
    gray = "#5C677D"

    fig = plt.figure(figsize=(14.0, 6.9), constrained_layout=True)
    gs = fig.add_gridspec(1, 2, width_ratios=(1.14, 0.86))
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])

    x = np.arange(len(DEPTH_LABELS))
    y = np.asarray(AVG_PROMPT_K)
    ax1.plot(x, y, color=navy, linewidth=2.6, marker="o", markersize=7, zorder=3)
    ax1.fill_between(x, 0, y, color=blue, alpha=0.10)
    ax1.set_xticks(x, DEPTH_LABELS)
    ax1.set_ylim(0, 750)
    ax1.set_ylabel("Average prompt tokens per response (thousands)")
    ax1.set_xlabel("Response depth within a Phase-1 session")
    ax1.set_title("A. Long sessions replay increasingly large prompts", loc="left", fontweight="bold")
    ax1.yaxis.grid(True, color="#D9E2EC", linewidth=0.8)
    for xi, yi in zip(x, y):
        ax1.text(xi, yi + 20, f"{yi:.0f}k", ha="center", va="bottom", color=navy, fontweight="bold")
    ax1.annotate(
        "401+ responses: 12.3× the first-25 average\nDepth >100: 80.63% of Phase-1 prompt tokens",
        xy=(6, y[-1]),
        xytext=(3.25, 710),
        arrowprops={"arrowstyle": "->", "color": gray, "lw": 1.2},
        bbox={"boxstyle": "round,pad=0.45", "fc": "white", "ec": "#CBD5E1"},
        color=gray,
        ha="left",
        va="top",
    )

    labels = [row[0] for row in PERCENT_METRICS]
    vals = [row[1] for row in PERCENT_METRICS]
    denoms = [row[2] for row in PERCENT_METRICS]
    colors = [blue, teal, "#6C8EBF", orange, red]
    ypos = np.arange(len(labels))[::-1]
    ax2.barh(ypos, vals, height=0.58, color=colors, alpha=0.94)
    ax2.set_xlim(0, 108)
    ax2.set_yticks(ypos, labels)
    ax2.set_xlabel("Share (%) — denominator shown under each value")
    ax2.set_title("B. Local recorded usage is prompt-heavy, with avoidable overlap", loc="left", fontweight="bold")
    ax2.xaxis.grid(True, color="#E2E8F0", linewidth=0.8)
    for yv, val, denom in zip(ypos, vals, denoms):
        shown = f"{val:.3f}%" if val < 1 else f"{val:.2f}%"
        ax2.text(min(val + 1.4, 101.5), yv + 0.08, shown, ha="left", va="center", fontweight="bold", color="#243B53")
        ax2.text(min(val + 1.4, 101.5), yv - 0.16, denom, ha="left", va="center", fontsize=8.4, color=gray)

    fig.suptitle("MASO usage audit: context depth, not output length, is the dominant amplifier", fontsize=17, fontweight="bold", color="#102A43")
    fig.text(
        0.01,
        -0.012,
        "Exact local swarm usage: 2.453B total tokens; 99.602% prompt, 0.398% completion. "
        "Coverage: 2026-08-01 16:21 to 08-03 07:21 UTC; it cannot independently reconstruct the ~RMB 300k bill. "
        "Lifecycle duplication is an operational upper bound, not a value judgment.",
        fontsize=9,
        color=gray,
    )
    save(fig, "maso_cost_amplifiers")


def funnel_figure() -> None:
    colors = ["#183153", "#2F6B9A", "#2A9D8F", "#E9C46A", "#F4A261"]
    gray = "#5C677D"
    names = [r[0] for r in FUNNEL]
    vals = np.asarray([r[1] for r in FUNNEL])
    ypos = np.arange(len(names))[::-1]

    fig, ax = plt.subplots(figsize=(12.2, 6.7), constrained_layout=True)
    ax.barh(ypos, vals, height=0.62, color=colors)
    ax.set_yticks(ypos, names)
    ax.set_xlim(0, 1040)
    ax.set_xlabel("Distinct logical identity labels / paths in the stable snapshot")
    ax.set_title("Second-generation execution funnel: entering the runner is not API success", loc="left", fontsize=16, fontweight="bold", color="#102A43")
    ax.xaxis.grid(True, color="#E2E8F0", linewidth=0.8)

    for yv, val in zip(ypos, vals):
        pct = 100 * val / vals[0]
        ax.text(val + 15, yv, f"{val:,}  ({pct:.1f}% of planned)", va="center", ha="left", fontweight="bold", color="#243B53")

    ax.text(
        565,
        1.15,
        "122447 created 193 tiny log files but had\n0 runner-loop / HTTP-success IDs: every runner exited\nat import with a Python `str | None` TypeError.",
        ha="left",
        va="center",
        bbox={"boxstyle": "round,pad=0.55", "fc": "#FFF7ED", "ec": "#F4A261"},
        color="#7C2D12",
    )
    ax.text(
        565,
        -0.02,
        "123 entered the loop, but 26 had only local exceptions.\n97 IDs had HTTP 200; 96 had tool/social actions.\nHTTP 200 is not a turn, token, session, or completed task.",
        ha="left",
        va="center",
        bbox={"boxstyle": "round,pad=0.55", "fc": "#EFF6FF", "ec": "#2F6B9A"},
        color="#1E3A5F",
    )
    fig.text(
        0.01,
        -0.012,
        "Finished is not success: 79 Finished markers = 64 with HTTP 200 + 15 error-only loops; 33 HTTP-success IDs were unfinished. "
        "Stable fingerprint 6982fe49…b396b49f; O_TRUNC prevents exact session/concurrency recovery.",
        fontsize=9,
        color=gray,
    )
    save(fig, "gen2_execution_funnel")


def write_values() -> None:
    with (ROOT / "audit_figure_values.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["figure", "metric", "value", "unit", "denominator_or_note"])
        for label, value in zip(DEPTH_LABELS, AVG_PROMPT_K):
            w.writerow(["cost", f"avg_prompt_depth_{label}", value * 1000, "tokens_per_response", "Phase-1 provider usage"])
        for label, value, denom in PERCENT_METRICS:
            w.writerow(["cost", label, value, "percent", denom])
        for label, value in FUNNEL:
            w.writerow(["execution", label, value, "logical_identity_count", "stable five-host snapshot"])
        w.writerow(["execution", "tool-event identities", 96, "logical_identity_count", "95 also posted citations; all 96 posted messages"])
        w.writerow(["execution", "Finished markers total", 79, "logical_identity_count", "64 HTTP-success + 15 error-only"])
        w.writerow(["execution", "HTTP-success not Finished", 33, "logical_identity_count", "stable snapshot"])
        w.writerow(["execution", "error-only Finished", 15, "logical_identity_count", "0 HTTP 200"])
        w.writerow(["execution", "error-only not Finished", 11, "logical_identity_count", "0 HTTP 200"])
        w.writerow(["execution", "import-failure IDs on 122447", 193, "logical_identity_count", "0 HTTP requests / runner loop"])
        w.writerow(["execution", "HTTP 200 request lines", 35422, "request_lines", "not turns/tokens/tasks"])


def write_manifest() -> None:
    records = []
    for path in sorted(ROOT.iterdir()):
        if path.name == "audit_figure_manifest.json" or not path.is_file():
            continue
        records.append(
            {
                "file": path.name,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    (ROOT / "audit_figure_manifest.json").write_text(
        json.dumps({"schema": "maso-audit-figures/v1", "files": records}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    style()
    cost_figure()
    funnel_figure()
    write_values()
    write_manifest()


if __name__ == "__main__":
    main()
