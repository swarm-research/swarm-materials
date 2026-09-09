#!/usr/bin/env python3
"""Read-only, reproducible MASO usage audit for the 2026-08-01/02 swarm.

The script reads local MASO session JSON and metadata only.  It never connects to
Merlin, starts/resumes a session, or changes MASO configuration.  It extracts the
authoritative per-response ``usage`` fields, joins compaction archives back to
their logical Phase-1 session, deduplicates by ``response_id``, and writes one
JSON report.

Usage:
    python3 audit_maso_usage.py [output.json]
"""

from __future__ import annotations

import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SESSION_DIR = Path("/Users/bytedance/.maso/sessions")
SWARM_DIR = Path("/Users/bytedance/Downloads/swarm")
CANONICAL_MAP = SWARM_DIR / "swarm_sessions.json"
DEFAULT_OUTPUT = Path(__file__).with_name("maso_usage_audit.json")

# These are intentionally narrow launch windows, established from local session
# metadata and launcher logs.  America/New_York renderings are included in the
# report so the numeric epochs are auditable.
PHASE1_START = 1785601280.0  # 2026-08-01 12:21:20 EDT
PHASE1_END = 1785601400.0    # 2026-08-01 12:23:20 EDT
PHASE2_START = 1785658800.0  # 2026-08-02 04:20:00 EDT
PHASE2_END = 1785661200.0    # 2026-08-02 05:00:00 EDT

AGENT_RE = re.compile(r"\bagent[-_ ]?(\d{3,4})\b", re.IGNORECASE)
TOKEN_KEYS = (
    "prompt_tokens",
    "cached_tokens",
    "noncached_prompt_tokens",
    "completion_tokens",
    "total_tokens",
)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def iso_utc(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def percentile(values: list[int], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(ordered[lo])
    return ordered[lo] * (hi - pos) + ordered[hi] * (pos - lo)


def first_agent_prompt(messages: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """Return normalized agent ID and the matching first user prompt excerpt."""
    for message in messages:
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        match = AGENT_RE.search(content)
        if match:
            return f"agent-{int(match.group(1)):03d}", content[:500]
    return None, None


def phase_marker(messages: list[dict[str, Any]]) -> str | None:
    for message in messages:
        if message.get("role") != "user" or not isinstance(message.get("content"), str):
            continue
        content = message["content"].lower()
        if "generation 2" in content or "这是你的 **generation 2**" in content:
            return "phase2_successor"
        if AGENT_RE.search(content):
            return "phase1_predecessor"
    return None


def read_meta(path: Path) -> dict[str, Any] | None:
    try:
        data = load_json(path)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def main_metas() -> list[tuple[Path, dict[str, Any]]]:
    rows: list[tuple[Path, dict[str, Any]]] = []
    for path in SESSION_DIR.glob("*.meta.json"):
        if ".archive." in path.name:
            continue
        meta = read_meta(path)
        if meta is not None:
            rows.append((path, meta))
    return rows


def in_window(meta: dict[str, Any], start: float, end: float) -> bool:
    created = safe_float(meta.get("created_at"), -1.0)
    return (
        created is not None
        and start <= created < end
        and meta.get("working_dir") == str(SWARM_DIR)
    )


def session_json_path(session_id: str) -> Path:
    return SESSION_DIR / f"{session_id}.json"


def logical_files(session_id: str, include_archives: bool) -> list[Path]:
    paths = [session_json_path(session_id)]
    if include_archives:
        paths.extend(
            path
            for path in sorted(SESSION_DIR.glob(f"{session_id}.archive.*.json"))
            if not path.name.endswith(".meta.json")
        )
    return [path for path in paths if path.exists()]


def usage_record(
    message: dict[str, Any],
    session_id: str,
    source_file: Path,
    model_fallback: str | None,
) -> dict[str, Any] | None:
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt = int(usage.get("prompt_tokens") or 0)
    cached = int(usage.get("cached_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    total = int(usage.get("total_tokens") or (prompt + completion))
    extra = message.get("extra") if isinstance(message.get("extra"), dict) else {}
    timing = extra.get("_llm_timing") if isinstance(extra.get("_llm_timing"), dict) else {}
    request_ts = safe_float(timing.get("llm_request_ts"), safe_float(message.get("created_at")))
    response_ts = safe_float(timing.get("llm_response_ts"), safe_float(message.get("created_at")))
    response_id = message.get("response_id")
    message_id = message.get("id")
    stable_key = response_id or message_id
    if not stable_key:
        stable_key = f"{session_id}:{source_file.name}:{message.get('created_at')}:{prompt}:{completion}"
    return {
        "key": str(stable_key),
        "response_id": response_id,
        "message_id": message_id,
        "session_id": session_id,
        "source_file": str(source_file),
        "request_ts": request_ts,
        "response_ts": response_ts,
        # The session metadata retains the configured tier (base/high/xhigh,
        # thinking/max), whereas the response often carries only a provider
        # family alias.  Keep both and aggregate primarily by configured tier.
        "model": model_fallback or extra.get("model") or message.get("origin_model_alias"),
        "origin_model_alias": extra.get("model") or message.get("origin_model_alias"),
        "prompt_tokens": prompt,
        "cached_tokens": cached,
        "noncached_prompt_tokens": max(0, prompt - cached),
        "completion_tokens": completion,
        "total_tokens": total,
    }


def extract_records(
    session_id: str,
    model: str | None,
    include_archives: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Extract and deduplicate usage records for one logical session."""
    files = logical_files(session_id, include_archives)
    by_key: dict[str, dict[str, Any]] = {}
    source_keys: dict[str, set[str]] = defaultdict(set)
    messages_seen = 0
    agent_id: str | None = None
    prompt_excerpt: str | None = None
    marker: str | None = None
    created_values: list[float] = []
    updated_values: list[float] = []

    for path in files:
        try:
            data = load_json(path)
        except (OSError, ValueError):
            continue
        messages = data.get("messages") if isinstance(data, dict) else None
        if not isinstance(messages, list):
            continue
        messages_seen += len(messages)
        created = safe_float(data.get("created_at"))
        updated = safe_float(data.get("updated_at"))
        if created is not None:
            created_values.append(created)
        if updated is not None:
            updated_values.append(updated)
        candidate, excerpt = first_agent_prompt(messages)
        if candidate and agent_id is None:
            agent_id, prompt_excerpt = candidate, excerpt
        if marker is None:
            marker = phase_marker(messages)
        for message in messages:
            if not isinstance(message, dict):
                continue
            record = usage_record(message, session_id, path, model)
            if record is None:
                continue
            key = record["key"]
            source_keys[str(path)].add(key)
            # Prefer the current file's copy when an archive overlaps it; usage is
            # identical, but this produces stable provenance.
            if key not in by_key or ".archive." not in path.name:
                by_key[key] = record

    records = sorted(
        by_key.values(),
        key=lambda row: (
            row.get("request_ts") if row.get("request_ts") is not None else float("inf"),
            row["key"],
        ),
    )
    all_source_occurrences = sum(len(keys) for keys in source_keys.values())
    provenance = {
        "files": [str(path) for path in files],
        "archive_file_count": sum(".archive." in path.name for path in files),
        "raw_messages_across_files": messages_seen,
        "usage_occurrences_across_files": all_source_occurrences,
        "unique_usage_records": len(records),
        "deduplicated_usage_occurrences": all_source_occurrences - len(records),
        "agent_id_from_first_prompt": agent_id,
        "phase_marker_from_prompt": marker,
        "prompt_excerpt": prompt_excerpt,
        "logical_created_at": min(created_values) if created_values else None,
        "logical_updated_at": max(updated_values) if updated_values else None,
    }
    return records, provenance


def token_totals(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(records)
    totals = {key: sum(int(row.get(key) or 0) for row in rows) for key in TOKEN_KEYS}
    totals["responses"] = len(rows)
    totals["cache_ratio_of_prompt"] = (
        totals["cached_tokens"] / totals["prompt_tokens"] if totals["prompt_tokens"] else None
    )
    request_times = [row.get("request_ts") for row in rows if row.get("request_ts") is not None]
    response_times = [row.get("response_ts") for row in rows if row.get("response_ts") is not None]
    totals["first_request_ts"] = min(request_times) if request_times else None
    totals["first_request_utc"] = iso_utc(totals["first_request_ts"])
    totals["last_response_ts"] = max(response_times) if response_times else None
    totals["last_response_utc"] = iso_utc(totals["last_response_ts"])
    return totals


def totals_by_model(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[str(row.get("model") or "unknown")].append(row)
    return {model: token_totals(rows) for model, rows in sorted(grouped.items())}


DEPTH_BUCKETS: list[tuple[str, int, int | None]] = [
    ("1-25", 1, 25),
    ("26-50", 26, 50),
    ("51-100", 51, 100),
    ("101-200", 101, 200),
    ("201-300", 201, 300),
    ("301-400", 301, 400),
    ("401+", 401, None),
]


def depth_bucket(depth: int) -> str:
    for label, start, end in DEPTH_BUCKETS:
        if depth >= start and (end is None or depth <= end):
            return label
    raise AssertionError(depth)


def depth_analysis(
    records_by_session: dict[str, list[dict[str, Any]]],
    session_meta: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    pooled: dict[str, list[dict[str, Any]]] = defaultdict(list)
    session_rows: list[dict[str, Any]] = []
    all_depth_rows: list[dict[str, Any]] = []
    matched_301_ratios: list[float] = []
    matched_401_ratios: list[float] = []

    for session_id, records in records_by_session.items():
        ordered = sorted(
            records,
            key=lambda row: (
                row.get("request_ts") if row.get("request_ts") is not None else float("inf"),
                row["key"],
            ),
        )
        for depth, row in enumerate(ordered, start=1):
            enriched = dict(row)
            enriched["depth"] = depth
            pooled[depth_bucket(depth)].append(enriched)
            all_depth_rows.append(enriched)
        early_prompts = [int(row["prompt_tokens"]) for row in ordered[:25]]
        early_mean = statistics.fmean(early_prompts) if early_prompts else None
        if early_mean:
            if len(ordered) >= 301:
                late_301 = [int(row["prompt_tokens"]) for row in ordered[300:400]]
                matched_301_ratios.append(statistics.fmean(late_301) / early_mean)
            if len(ordered) >= 401:
                late_401 = [int(row["prompt_tokens"]) for row in ordered[400:]]
                matched_401_ratios.append(statistics.fmean(late_401) / early_mean)
        totals = token_totals(ordered)
        meta = session_meta.get(session_id, {})
        session_rows.append(
            {
                "session_id": session_id,
                "agent_id": meta.get("agent_id"),
                "model": meta.get("model"),
                **{key: totals[key] for key in ("responses",) + TOKEN_KEYS},
            }
        )

    bucket_rows: list[dict[str, Any]] = []
    for label, _start, _end in DEPTH_BUCKETS:
        rows = pooled.get(label, [])
        prompts = [int(row["prompt_tokens"]) for row in rows]
        totals = token_totals(rows)
        bucket_rows.append(
            {
                "depth_bucket": label,
                "sessions_reaching_bucket": len({row["session_id"] for row in rows}),
                **{key: totals[key] for key in ("responses",) + TOKEN_KEYS},
                "share_of_scope_prompt_tokens": None,
                "avg_prompt_tokens_per_response": statistics.fmean(prompts) if prompts else None,
                "median_prompt_tokens_per_response": statistics.median(prompts) if prompts else None,
                "p90_prompt_tokens_per_response": percentile(prompts, 0.90),
            }
        )

    scope_prompt = sum(row["prompt_tokens"] for row in bucket_rows)
    for row in bucket_rows:
        row["share_of_scope_prompt_tokens"] = (
            row["prompt_tokens"] / scope_prompt if scope_prompt else None
        )

    sorted_sessions = sorted(session_rows, key=lambda row: row["prompt_tokens"], reverse=True)

    def top_share(n: int) -> float | None:
        if not scope_prompt:
            return None
        return sum(row["prompt_tokens"] for row in sorted_sessions[:n]) / scope_prompt

    deep_100 = [row for row in all_depth_rows if row["depth"] > 100]
    deep_200 = [row for row in all_depth_rows if row["depth"] > 200]
    deep_300 = [row for row in all_depth_rows if row["depth"] > 300]
    early = next((row for row in bucket_rows if row["depth_bucket"] == "1-25"), None)
    late_candidates = [
        row for row in bucket_rows
        if row["depth_bucket"] in {"301-400", "401+"} and row["responses"]
    ]
    late_prompts = sum(row["prompt_tokens"] for row in late_candidates)
    late_responses = sum(row["responses"] for row in late_candidates)
    late_avg = late_prompts / late_responses if late_responses else None
    early_avg = early["avg_prompt_tokens_per_response"] if early else None

    return {
        "session_count": len(records_by_session),
        "response_count": len(all_depth_rows),
        "depth_buckets": bucket_rows,
        "growth": {
            "avg_prompt_depth_1_25": early_avg,
            "avg_prompt_depth_301_plus": late_avg,
            "depth_301_plus_vs_1_25_ratio": (
                late_avg / early_avg if late_avg is not None and early_avg else None
            ),
            "matched_sessions_reaching_depth_301": len(matched_301_ratios),
            "matched_depth_301_400_vs_1_25_median_ratio": (
                statistics.median(matched_301_ratios) if matched_301_ratios else None
            ),
            "matched_depth_301_400_vs_1_25_mean_ratio": (
                statistics.fmean(matched_301_ratios) if matched_301_ratios else None
            ),
            "matched_sessions_reaching_depth_401": len(matched_401_ratios),
            "matched_depth_401_plus_vs_1_25_median_ratio": (
                statistics.median(matched_401_ratios) if matched_401_ratios else None
            ),
            "matched_depth_401_plus_vs_1_25_mean_ratio": (
                statistics.fmean(matched_401_ratios) if matched_401_ratios else None
            ),
        },
        "cost_concentration": {
            "top_1_session_prompt_share": top_share(1),
            "top_5_sessions_prompt_share": top_share(5),
            "top_10_sessions_prompt_share": top_share(10),
            "prompt_share_after_depth_100": (
                sum(row["prompt_tokens"] for row in deep_100) / scope_prompt if scope_prompt else None
            ),
            "prompt_share_after_depth_200": (
                sum(row["prompt_tokens"] for row in deep_200) / scope_prompt if scope_prompt else None
            ),
            "prompt_share_after_depth_300": (
                sum(row["prompt_tokens"] for row in deep_300) / scope_prompt if scope_prompt else None
            ),
            "sessions_with_at_least_100_responses": sum(row["responses"] >= 100 for row in session_rows),
            "sessions_with_at_least_200_responses": sum(row["responses"] >= 200 for row in session_rows),
            "sessions_with_at_least_300_responses": sum(row["responses"] >= 300 for row in session_rows),
            "maximum_responses_in_one_session": max((row["responses"] for row in session_rows), default=0),
            "top_10_sessions": sorted_sessions[:10],
        },
    }


def add_totals(*totals: dict[str, Any]) -> dict[str, Any]:
    result = {key: sum(int(total.get(key) or 0) for total in totals) for key in TOKEN_KEYS}
    result["responses"] = sum(int(total.get("responses") or 0) for total in totals)
    result["cache_ratio_of_prompt"] = (
        result["cached_tokens"] / result["prompt_tokens"] if result["prompt_tokens"] else None
    )
    return result


def filter_records(
    records: Iterable[dict[str, Any]],
    start: float | None = None,
    end: float | None = None,
) -> list[dict[str, Any]]:
    result = []
    for row in records:
        ts = row.get("request_ts")
        if ts is None:
            continue
        if start is not None and ts < start:
            continue
        if end is not None and ts > end:
            continue
        result.append(row)
    return result


def compact_session_row(
    session_id: str,
    meta: dict[str, Any],
    provenance: dict[str, Any],
    records: list[dict[str, Any]],
    role: str,
    canonical: bool | None = None,
) -> dict[str, Any]:
    totals = token_totals(records)
    row = {
        "session_id": session_id,
        "role": role,
        "agent_id": provenance.get("agent_id_from_first_prompt"),
        "model": meta.get("model"),
        "created_at": safe_float(meta.get("created_at")),
        "created_utc": iso_utc(safe_float(meta.get("created_at"))),
        "updated_at": safe_float(meta.get("updated_at")),
        "metadata_message_count": int(meta.get("message_count") or 0),
        "phase_marker_from_prompt": provenance.get("phase_marker_from_prompt"),
        "archive_file_count": provenance.get("archive_file_count"),
        "deduplicated_usage_occurrences": provenance.get("deduplicated_usage_occurrences"),
        **{key: totals[key] for key in ("responses",) + TOKEN_KEYS},
        "first_request_ts": totals["first_request_ts"],
        "last_response_ts": totals["last_response_ts"],
    }
    if canonical is not None:
        row["canonical_successor"] = canonical
    return row


def main() -> int:
    output_path = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else DEFAULT_OUTPUT
    metas = main_metas()
    meta_by_id = {
        str(meta.get("session_id") or path.name.removesuffix(".meta.json")): meta
        for path, meta in metas
    }

    phase1_ids = sorted(
        session_id for session_id, meta in meta_by_id.items()
        if in_window(meta, PHASE1_START, PHASE1_END)
    )
    canonical_rows = load_json(CANONICAL_MAP)
    if not isinstance(canonical_rows, list):
        raise RuntimeError(f"Expected list in {CANONICAL_MAP}")
    canonical_by_agent = {
        str(row["id"]): str(row["session_id"])
        for row in canonical_rows
        if isinstance(row, dict) and row.get("id") and row.get("session_id")
    }
    canonical_ids = set(canonical_by_agent.values())

    phase2_ids = sorted(
        session_id for session_id, meta in meta_by_id.items()
        if in_window(meta, PHASE2_START, PHASE2_END)
    )
    # Preserve final-map successors even if a future copy of the metadata has a
    # slightly shifted timestamp.
    phase2_ids = sorted(set(phase2_ids) | canonical_ids)

    p1_records: dict[str, list[dict[str, Any]]] = {}
    p1_provenance: dict[str, dict[str, Any]] = {}
    p1_session_meta: dict[str, dict[str, Any]] = {}
    for session_id in phase1_ids:
        meta = meta_by_id[session_id]
        records, provenance = extract_records(session_id, meta.get("model"), include_archives=True)
        p1_records[session_id] = records
        p1_provenance[session_id] = provenance
        p1_session_meta[session_id] = {
            "agent_id": provenance.get("agent_id_from_first_prompt"),
            "model": meta.get("model"),
        }

    p2_records: dict[str, list[dict[str, Any]]] = {}
    p2_provenance: dict[str, dict[str, Any]] = {}
    p2_session_meta: dict[str, dict[str, Any]] = {}
    for session_id in phase2_ids:
        meta = meta_by_id.get(session_id, {})
        records, provenance = extract_records(session_id, meta.get("model"), include_archives=False)
        p2_records[session_id] = records
        p2_provenance[session_id] = provenance
        p2_session_meta[session_id] = {
            "agent_id": provenance.get("agent_id_from_first_prompt"),
            "model": meta.get("model"),
        }

    p1_agent_to_sid: dict[str, str] = {}
    phase1_mapping_conflicts: list[dict[str, Any]] = []
    for session_id in phase1_ids:
        agent_id = p1_provenance[session_id].get("agent_id_from_first_prompt")
        if not agent_id:
            phase1_mapping_conflicts.append({"session_id": session_id, "issue": "no_agent_id_in_prompt"})
        elif agent_id in p1_agent_to_sid:
            phase1_mapping_conflicts.append(
                {
                    "session_id": session_id,
                    "issue": "duplicate_agent_id_in_phase1",
                    "agent_id": agent_id,
                    "other_session_id": p1_agent_to_sid[agent_id],
                }
            )
        else:
            p1_agent_to_sid[agent_id] = session_id

    p2_prompt_map: dict[str, list[str]] = defaultdict(list)
    for session_id in phase2_ids:
        agent_id = p2_provenance[session_id].get("agent_id_from_first_prompt")
        if agent_id:
            p2_prompt_map[agent_id].append(session_id)

    all_p1 = [row for records in p1_records.values() for row in records]
    all_p2 = [row for records in p2_records.values() for row in records]
    canonical_p2_records = {
        sid: p2_records.get(sid, []) for sid in sorted(canonical_ids)
    }
    orphan_ids = sorted(set(phase2_ids) - canonical_ids)
    orphan_valid_ids = [sid for sid in orphan_ids if p2_records.get(sid)]
    orphan_zero_ids = [sid for sid in orphan_ids if not p2_records.get(sid)]
    all_p2_canonical = [row for records in canonical_p2_records.values() for row in records]
    all_p2_orphan = [row for sid in orphan_ids for row in p2_records.get(sid, [])]

    # Per-agent predecessor/successor overlap.  The primary cutoff is successor
    # session creation; a stricter live-overlap window starts at the successor's
    # first LLM request and ends at its last response.
    pair_rows: list[dict[str, Any]] = []
    all_post_successor: list[dict[str, Any]] = []
    all_live_overlap: list[dict[str, Any]] = []
    for agent_id in sorted(canonical_by_agent):
        successor_id = canonical_by_agent[agent_id]
        predecessor_id = p1_agent_to_sid.get(agent_id)
        successor_meta = meta_by_id.get(successor_id, {})
        successor_created = safe_float(successor_meta.get("created_at"))
        successor_usage = p2_records.get(successor_id, [])
        successor_totals = token_totals(successor_usage)
        successor_first_request = successor_totals.get("first_request_ts")
        successor_last_response = successor_totals.get("last_response_ts")
        predecessor_usage = p1_records.get(predecessor_id or "", [])
        post_created = filter_records(predecessor_usage, start=successor_created)
        live_overlap = filter_records(
            predecessor_usage,
            start=successor_first_request or successor_created,
            end=successor_last_response,
        )
        all_post_successor.extend(post_created)
        all_live_overlap.extend(live_overlap)
        orphan_successors = [
            sid for sid in p2_prompt_map.get(agent_id, []) if sid != successor_id
        ]
        pair_rows.append(
            {
                "agent_id": agent_id,
                "phase1_predecessor_session_id": predecessor_id,
                "phase2_canonical_successor_session_id": successor_id,
                "phase2_other_successor_session_ids": orphan_successors,
                "successor_created_at": successor_created,
                "successor_created_utc": iso_utc(successor_created),
                "successor_first_request_ts": successor_first_request,
                "successor_last_response_ts": successor_last_response,
                "predecessor_after_successor_created": token_totals(post_created),
                "predecessor_during_successor_live_window": token_totals(live_overlap),
                "canonical_successor_usage": successor_totals,
                "other_successor_usage": token_totals(
                    row
                    for sid in orphan_successors
                    for row in p2_records.get(sid, [])
                ),
            }
        )

    p1_totals = token_totals(all_p1)
    p2_totals = token_totals(all_p2)
    p2_canonical_totals = token_totals(all_p2_canonical)
    p2_orphan_totals = token_totals(all_p2_orphan)
    post_successor_totals = token_totals(all_post_successor)
    live_overlap_totals = token_totals(all_live_overlap)

    # A transparent upper-bound counterfactual only: these are duplicate-lived
    # predecessor calls plus noncanonical successor calls.  They are not labeled
    # "waste" because output value is not inferable from token logs alone.
    duplicate_lifecycle_upper_bound = add_totals(post_successor_totals, p2_orphan_totals)

    phase1_session_rows = [
        compact_session_row(
            sid, meta_by_id[sid], p1_provenance[sid], p1_records[sid], "phase1_predecessor"
        )
        for sid in phase1_ids
    ]
    phase2_session_rows = [
        compact_session_row(
            sid,
            meta_by_id.get(sid, {}),
            p2_provenance[sid],
            p2_records[sid],
            "phase2_successor" if sid in canonical_ids else "phase2_noncanonical_attempt",
            canonical=sid in canonical_ids,
        )
        for sid in phase2_ids
    ]

    phase1_prompt_agent_counts = Counter(
        row["agent_id"] for row in phase1_session_rows if row.get("agent_id")
    )
    phase2_prompt_agent_counts = Counter(
        row["agent_id"] for row in phase2_session_rows if row.get("agent_id")
    )

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "mode": "read_only_local_audit_no_ssh",
            "session_dir": str(SESSION_DIR),
            "swarm_dir": str(SWARM_DIR),
            "canonical_phase2_map": str(CANONICAL_MAP),
            "phase1_window_epoch": [PHASE1_START, PHASE1_END],
            "phase1_window_utc": [iso_utc(PHASE1_START), iso_utc(PHASE1_END)],
            "phase2_window_epoch": [PHASE2_START, PHASE2_END],
            "phase2_window_utc": [iso_utc(PHASE2_START), iso_utc(PHASE2_END)],
        },
        "methodology": {
            "agent_mapping": "First user prompt containing agent-NNN; no filename/model inference.",
            "phase1": "36 base sessions created in the narrow Phase-1 launch window; current plus archive segments are one logical session.",
            "phase2": "All local swarm sessions in the resurrection launch window plus every final canonical session in swarm_sessions.json.",
            "usage": "Authoritative assistant-message usage fields; prompt includes cached tokens; total is prompt plus completion.",
            "deduplication": "response_id, falling back to message id; current copy wins over archive copy.",
            "predecessor_cutoff": "Phase-1 LLM request timestamp >= its canonical Phase-2 successor metadata.created_at.",
            "strict_overlap": "Phase-1 request timestamp between successor first LLM request and successor last LLM response.",
            "limitations": [
                "Provider billing rates and cached-token discounts are not encoded in session JSON, so RMB cost is not reconstructed.",
                "Token logs measure compute consumption, not the research value of individual artifacts.",
                "Remote /tmp/swarm devbox data is outside this local-only audit.",
            ],
        },
        "agent_mapping": {
            "phase1_unique_agent_ids": len(phase1_prompt_agent_counts),
            "phase1_agent_id_counts": dict(sorted(phase1_prompt_agent_counts.items())),
            "phase1_conflicts": phase1_mapping_conflicts,
            "phase1_agent_to_session": dict(sorted(p1_agent_to_sid.items())),
            "phase2_unique_agent_ids_across_attempts": len(phase2_prompt_agent_counts),
            "phase2_agent_id_counts_across_attempts": dict(sorted(phase2_prompt_agent_counts.items())),
            "phase2_agent_to_sessions_from_prompts": {
                agent: sorted(sids) for agent, sids in sorted(p2_prompt_map.items())
            },
            "phase2_final_canonical_agent_to_session": dict(sorted(canonical_by_agent.items())),
        },
        "phase1_predecessors": {
            "session_count": len(phase1_ids),
            "sessions": sorted(phase1_session_rows, key=lambda row: row.get("agent_id") or row["session_id"]),
            "totals": p1_totals,
            "totals_by_model": totals_by_model(all_p1),
            "depth_analysis": depth_analysis(p1_records, p1_session_meta),
            "archive_provenance": {
                "archive_files": sum(p1_provenance[sid]["archive_file_count"] for sid in phase1_ids),
                "usage_occurrences_across_current_and_archive": sum(
                    p1_provenance[sid]["usage_occurrences_across_files"] for sid in phase1_ids
                ),
                "unique_usage_records": len(all_p1),
                "deduplicated_usage_occurrences": sum(
                    p1_provenance[sid]["deduplicated_usage_occurrences"] for sid in phase1_ids
                ),
            },
        },
        "phase2_successors": {
            "session_files_in_scope": len(phase2_ids),
            "valid_session_files": sum(bool(p2_records[sid]) for sid in phase2_ids),
            "zero_usage_session_files": sum(not p2_records[sid] for sid in phase2_ids),
            "canonical_session_count": len(canonical_ids),
            "noncanonical_session_count": len(orphan_ids),
            "noncanonical_valid_session_count": len(orphan_valid_ids),
            "noncanonical_zero_usage_session_count": len(orphan_zero_ids),
            "noncanonical_session_ids": orphan_ids,
            "noncanonical_valid_session_ids": orphan_valid_ids,
            "noncanonical_zero_usage_session_ids": orphan_zero_ids,
            "sessions": sorted(phase2_session_rows, key=lambda row: (row.get("agent_id") or "zzz", row["created_at"] or 0)),
            "all_attempts_totals": p2_totals,
            "canonical_totals": p2_canonical_totals,
            "noncanonical_attempt_totals": p2_orphan_totals,
            "noncanonical_share_of_phase2_total_tokens": (
                p2_orphan_totals["total_tokens"] / p2_totals["total_tokens"]
                if p2_totals["total_tokens"] else None
            ),
            "totals_by_model_all_attempts": totals_by_model(all_p2),
            "depth_analysis_all_attempts": depth_analysis(p2_records, p2_session_meta),
            "depth_analysis_canonical_only": depth_analysis(canonical_p2_records, p2_session_meta),
        },
        "predecessor_successor_overlap": {
            "agents_paired": len(pair_rows),
            "agents_with_predecessor_calls_after_successor_created": sum(
                row["predecessor_after_successor_created"]["responses"] > 0 for row in pair_rows
            ),
            "agents_with_strict_live_overlap": sum(
                row["predecessor_during_successor_live_window"]["responses"] > 0 for row in pair_rows
            ),
            "predecessor_after_successor_created_totals": post_successor_totals,
            "predecessor_during_successor_live_window_totals": live_overlap_totals,
            "phase2_noncanonical_attempt_totals": p2_orphan_totals,
            "duplicate_lifecycle_upper_bound": {
                **duplicate_lifecycle_upper_bound,
                "definition": "predecessor-after-canonical-successor-created + every noncanonical Phase-2 attempt; counterfactual upper bound, not a value judgment",
                "share_of_two_round_total_tokens": (
                    duplicate_lifecycle_upper_bound["total_tokens"]
                    / (p1_totals["total_tokens"] + p2_totals["total_tokens"])
                    if p1_totals["total_tokens"] + p2_totals["total_tokens"] else None
                ),
            },
            "pairs": pair_rows,
        },
        "two_round_local_total": add_totals(p1_totals, p2_totals),
        "evidence_paths": [
            str(SESSION_DIR),
            str(CANONICAL_MAP),
            str(SWARM_DIR / "vitals/resurrect.log"),
            str(SWARM_DIR / "swarm_resurrect.py"),
            str(SWARM_DIR / "swarm_launcher.py"),
            str(SWARM_DIR / "swarm_monitor.py"),
            str(SWARM_DIR / "swarm_compactor.py"),
            str(SWARM_DIR / "swarm_phase2.sh"),
            str(SWARM_DIR / "devbox_runner.py"),
            str(SWARM_DIR / "devbox_watchdog.py"),
            "/Users/bytedance/.maso/settings.json",
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(json.dumps({
        "output": str(output_path),
        "phase1_sessions": len(phase1_ids),
        "phase2_session_files": len(phase2_ids),
        "phase1": p1_totals,
        "phase2": p2_totals,
        "post_successor": post_successor_totals,
        "phase2_noncanonical": p2_orphan_totals,
        "two_round": add_totals(p1_totals, p2_totals),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
