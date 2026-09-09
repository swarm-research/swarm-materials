#!/usr/bin/env python3
"""Read-only, reproducible audit of the first MASO social-swarm archive.

The source archive is never modified.  Every derived table is written next to
this script.  The script deliberately reports several measurement variants
instead of silently choosing the one that tells the cleanest story.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import itertools
import json
import math
import os
import random
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


ROOT = Path("/Users/bytedance/Downloads/swarm-archive-20260803")
W = ROOT / "01_workspace"
T = ROOT / "02_transcripts"
OUT = Path(__file__).resolve().parent

DOMAINS = ("tools", "findings", "data", "challenges", "builds")
ROSTER = tuple(f"agent-{i:03d}" for i in range(1, 37))
ROSTER_SET = set(ROSTER)
SEEDS = {"agent-005", "agent-017", "agent-029"}
SCOUTS = {
    "agent-001", "agent-005", "agent-007", "agent-010",
    "agent-013", "agent-017", "agent-019", "agent-022",
    "agent-025", "agent-029", "agent-031", "agent-034",
}
KILLED = {
    "agent-007": "2026-08-02T07:44:14.023404",
    "agent-030": "2026-08-02T07:44:14.023404",
    "agent-033": "2026-08-02T07:44:14.023404",
    "agent-035": "2026-08-02T08:44:16.379548",
}
LOCAL = ZoneInfo("America/New_York")
UTC = dt.timezone.utc

# The resurrection log is in local time; the session metadata independently
# places the first Gen-2 creation at 08:32:36 UTC.
PHASE2_START = dt.datetime(2026, 8, 2, 4, 32, 32, 901074, tzinfo=LOCAL).astimezone(UTC)
EXPANSION_START = dt.datetime(2026, 8, 2, 6, 21, 8, 939737, tzinfo=LOCAL).astimezone(UTC)
# Earliest public disclosure found in the raw board ledger: agent-021 names all
# three seed identities and describes the private prompt fragment.  Agent-020
# publishes a fuller disclosure ten minutes later at 16:41:47Z.
SEED_LEAK = dt.datetime(2026, 8, 1, 16, 31, 17, tzinfo=UTC)


def norm_agent(value: Any) -> str | None:
    m = re.fullmatch(r"agent-0*(\d+)", str(value or "").strip(), re.I)
    return f"agent-{int(m.group(1)):03d}" if m else None


def parse_time(value: Any, naive_zone: ZoneInfo = LOCAL) -> dt.datetime | None:
    """Interpret aware timestamps literally and archive-naive timestamps locally."""
    s = str(value or "").strip()
    if not s:
        return None
    try:
        x = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if x.tzinfo is None:
        x = x.replace(tzinfo=naive_zone)
    return x.astimezone(UTC)


def iso(x: dt.datetime | None) -> str:
    return x.isoformat().replace("+00:00", "Z") if x else ""


def jsonl(path: Path) -> tuple[list[dict[str, Any]], list[tuple[int, str]]]:
    good: list[dict[str, Any]] = []
    bad: list[tuple[int, str]] = []
    for i, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                good.append(value)
            else:
                bad.append((i, "non-object"))
        except json.JSONDecodeError:
            bad.append((i, line[:200]))
    return good, bad


def gini(values: Iterable[float]) -> float:
    xs = sorted(float(x) for x in values)
    n, s = len(xs), sum(xs)
    if not n or not s:
        return 0.0
    return 2 * sum((i + 1) * x for i, x in enumerate(xs)) / (n * s) - (n + 1) / n


def hhi(counts: Iterable[int]) -> float | None:
    xs = [x for x in counts if x]
    s = sum(xs)
    return sum((x / s) ** 2 for x in xs) if s else None


def max_share(counts: Iterable[int]) -> float | None:
    xs = list(counts)
    s = sum(xs)
    return max(xs, default=0) / s if s else None


def quantile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    xs = sorted(values)
    z = (len(xs) - 1) * p
    lo, hi = math.floor(z), math.ceil(z)
    return xs[lo] if lo == hi else xs[lo] * (hi - z) + xs[hi] * (z - lo)


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if not n:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - r, c + r


STAMP_RE = re.compile(r"(20\d{6})[T_]?([0-2]\d)([0-5]\d)([0-5]\d)(?:Z)?")


def name_time(name: str) -> dt.datetime | None:
    matches = list(STAMP_RE.finditer(name))
    if not matches:
        return None
    try:
        return dt.datetime.strptime("".join(matches[-1].groups()), "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def tree_digest(path: Path) -> tuple[str, int, int]:
    """Stable digest, bytes, and file count for a top-level artifact entry."""
    h = hashlib.sha256()
    if path.is_file():
        with path.open("rb") as f:
            while True:
                b = f.read(1024 * 1024)
                if not b:
                    break
                h.update(b)
        return h.hexdigest(), path.stat().st_size, 1
    total = 0
    nfiles = 0
    for f in sorted(x for x in path.rglob("*") if x.is_file()):
        rel = f.relative_to(path).as_posix().encode()
        h.update(len(rel).to_bytes(4, "big"))
        h.update(rel)
        with f.open("rb") as fp:
            while True:
                b = fp.read(1024 * 1024)
                if not b:
                    break
                total += len(b)
                h.update(b)
        nfiles += 1
    return h.hexdigest(), total, nfiles


def owner_from_rel(rel: str) -> str | None:
    # The owner is encoded in the first top-level artifact name.  Looking for
    # any agent token deeper in text would incorrectly assign shared aliases.
    parts = rel.split("/")
    if len(parts) >= 3 and parts[0] == "commons" and parts[1] in DOMAINS:
        m = re.match(r"(agent-\d+)(?:_|[.-])", parts[2])
        return norm_agent(m.group(1)) if m else None
    if len(parts) >= 2 and parts[0] == "agents":
        return norm_agent(parts[1])
    return None


def artifact_inventory() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cache = OUT / "artifact_inventory.csv"
    prior_summary = OUT / "audit_summary.json"
    if cache.exists() and prior_summary.exists():
        # The archive may live behind macOS File Provider; reopening every
        # artifact can trigger minutes of hydration.  The inventory is
        # content-addressed and can be reused.  Delete the CSV to force a full
        # byte rescan.
        with cache.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            for k in ("owner_in_roster", "zero_bytes", "heuristic_fixture"):
                r[k] = str(r[k]).lower() == "true"
            for k in ("bytes", "nested_files", "exact_duplicate_group_size"):
                r[k] = int(r[k])
        old = json.loads(prior_summary.read_text())
        summary = old["integrity"]
        dup_paths: dict[str, list[str]] = defaultdict(list)
        for r in rows:
            if r["bytes"] > 0 and r["exact_duplicate_group_size"] > 1:
                dup_paths[r["sha256"]].append(r["path"])
        summary["largest_exact_duplicate_groups"] = sorted(
            dup_paths.values(), key=lambda x: (-len(x), x)
        )[:15]
        summary["inventory_cache_reused"] = True
        return rows, summary

    rows: list[dict[str, Any]] = []
    for domain in DOMAINS:
        for p in sorted((W / "commons" / domain).iterdir()):
            rel = p.relative_to(W).as_posix()
            owner = owner_from_rel(rel)
            digest, nbytes, nfiles = tree_digest(p)
            mt = dt.datetime.fromtimestamp(p.stat().st_mtime, UTC)
            nt = name_time(p.name)
            inferred = nt or mt
            heuristic_fixture = bool(re.search(
                r"(?i)(?:^|[_-])(test|fixture|dummy|placeholder|convention)(?:[_-]|$)", p.name
            ))
            rows.append({
                "domain": domain,
                "path": rel,
                "entry_type": "dir" if p.is_dir() else "file",
                "owner": owner or "",
                "owner_in_roster": owner in ROSTER_SET,
                "bytes": nbytes,
                "nested_files": nfiles,
                "sha256": digest,
                "mtime_utc": iso(mt),
                "name_time_utc": iso(nt),
                "inferred_create_utc": iso(inferred),
                "phase_inferred": "phase1" if inferred < PHASE2_START else "phase2",
                "phase_mtime": "phase1" if mt < PHASE2_START else "phase2",
                "zero_bytes": nbytes == 0,
                "heuristic_fixture": heuristic_fixture,
            })

    hashes = Counter(r["sha256"] for r in rows if r["bytes"] > 0)
    for r in rows:
        r["exact_duplicate_group_size"] = hashes[r["sha256"]] if r["bytes"] > 0 else 0

    all_files = [p for p in W.rglob("*") if p.is_file()]
    agent_dirs = [p for p in (W / "agents").iterdir() if p.is_dir()]
    dup_paths: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        if r["bytes"] > 0 and hashes[r["sha256"]] > 1:
            dup_paths[r["sha256"]].append(r["path"])
    summary = {
        "workspace_files": len(all_files),
        "workspace_bytes": sum(p.stat().st_size for p in all_files),
        "workspace_zero_byte_files": sum(p.stat().st_size == 0 for p in all_files),
        "workspace_extensions": Counter(p.suffix or "[no_ext]" for p in all_files),
        "agent_directories": len(agent_dirs),
        "empty_agent_directories": sum(not any(p.iterdir()) for p in agent_dirs),
        "empty_expansion_directories_037_100": sum(
            not any((W / "agents" / f"agent-{i:03d}").iterdir()) for i in range(37, 101)
        ),
        "top_level_commons_entries": len(rows),
        "roster_attributed_entries": sum(r["owner_in_roster"] for r in rows),
        "nonroster_attributed_entries": sum(bool(r["owner"]) and not r["owner_in_roster"] for r in rows),
        "unattributed_entries": sum(not r["owner"] for r in rows),
        "zero_byte_entries": sum(r["zero_bytes"] for r in rows),
        "fixture_named_entries": sum(r["heuristic_fixture"] for r in rows),
        "exact_duplicate_nonempty_files": sum(
            r["entry_type"] == "file" and r["exact_duplicate_group_size"] > 1 for r in rows
        ),
        "exact_duplicate_excess": sum(n - 1 for n in hashes.values() if n > 1),
        "largest_exact_duplicate_groups": sorted(dup_paths.values(), key=lambda x: (-len(x), x))[:15],
    }
    return rows, summary


def build_path_index() -> tuple[dict[str, Path], dict[str, list[Path]]]:
    rel = {}
    base: dict[str, list[Path]] = defaultdict(list)
    for p in W.rglob("*"):
        if p.is_file() or p.is_dir():
            rp = p.relative_to(W).as_posix()
            rel[rp] = p
            base[p.name].append(p)
    return rel, base


def resolve_cited_file(value: Any, rel_index: dict[str, Path], base_index: dict[str, list[Path]]) -> tuple[str, str]:
    if not isinstance(value, str):
        return "", "non_string"
    s = value.strip().replace("\\", "/")
    prefix = "/Users/bytedance/Downloads/swarm/"
    if s.startswith(prefix):
        s = s[len(prefix):]
    while s.startswith("./"):
        s = s[2:]
    if s in rel_index:
        return s, "exact"
    if "/" not in s and len(base_index.get(s, [])) == 1:
        return base_index[s][0].relative_to(W).as_posix(), "unique_basename"
    return "", "unresolved"


def citation_audit(rel_index: dict[str, Path], base_index: dict[str, list[Path]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw, bad = jsonl(W / "citations.jsonl")
    rows = []
    for i, x in enumerate(raw, 1):
        citer, cited = norm_agent(x.get("citer") or x.get("from")), norm_agent(x.get("cited") or x.get("to"))
        resolved, resolution = resolve_cited_file(x.get("file"), rel_index, base_index)
        owner = owner_from_rel(resolved) if resolved else None
        when = parse_time(x.get("time"))
        roster_pair = citer in ROSTER_SET and cited in ROSTER_SET
        nonself = roster_pair and citer != cited
        public = resolved.startswith("commons/")
        owner_confirmed = nonself and public and owner == cited
        rows.append({
            "line": i,
            "citer_raw": str(x.get("citer") or x.get("from") or ""),
            "cited_raw": str(x.get("cited") or x.get("to") or ""),
            "citer": citer or "",
            "cited": cited or "",
            "file_raw": str(x.get("file") or ""),
            "resolved_path": resolved,
            "resolution": resolution,
            "resolved_owner": owner or "",
            "time_raw": str(x.get("time") or ""),
            "time_utc": iso(when),
            "phase": "phase1" if when and when < PHASE2_START else ("phase2" if when else "unknown"),
            "roster_pair": roster_pair,
            "nonself_roster_pair": nonself,
            "public_resolved": public,
            "owner_confirmed": owner_confirmed,
        })

    exact_objects = [json.dumps(x, ensure_ascii=False, sort_keys=True) for x in raw]
    clean = [r for r in rows if r["owner_confirmed"]]
    clean_triples = [(r["citer"], r["cited"], r["resolved_path"]) for r in clean]
    clean_pairs = {(r["citer"], r["cited"]) for r in clean}
    raw_recv = Counter(r["cited"] for r in rows if r["cited"] in ROSTER_SET)
    clean_recv_events = Counter(r["cited"] for r in clean)
    clean_recv_neighbors: dict[str, set[str]] = defaultdict(set)
    for r in clean:
        clean_recv_neighbors[r["cited"]].add(r["citer"])
    unresolved_patterns = Counter(r["file_raw"] for r in rows if not r["resolved_path"])
    invalid_actor = Counter()
    for r in rows:
        if r["citer"] not in ROSTER_SET:
            invalid_actor[r["citer_raw"] or "[missing]"] += 1

    summary = {
        "lines": len(raw),
        "parse_errors": len(bad),
        "exact_object_duplicate_excess": len(exact_objects) - len(set(exact_objects)),
        "roster_pair": sum(r["roster_pair"] for r in rows),
        "nonself_roster_pair": sum(r["nonself_roster_pair"] for r in rows),
        "public_resolved": sum(r["public_resolved"] for r in rows),
        "owner_confirmed_events": len(clean),
        "owner_confirmed_fraction": len(clean) / len(rows) if rows else 0,
        "owner_confirmed_unique_triples": len(set(clean_triples)),
        "owner_confirmed_semantic_duplicate_excess": len(clean_triples) - len(set(clean_triples)),
        "owner_confirmed_pair_edges": len(clean_pairs),
        "raw_received_gini_roster": gini(raw_recv[a] for a in ROSTER),
        "clean_event_received_gini_roster": gini(clean_recv_events[a] for a in ROSTER),
        "clean_unique_citer_received_gini_roster": gini(len(clean_recv_neighbors[a]) for a in ROSTER),
        "clean_zero_received_agents": sum(not clean_recv_neighbors[a] for a in ROSTER),
        "invalid_citer_labels": invalid_actor,
        "top_unresolved_file_values": unresolved_patterns.most_common(20),
        "phase_counts_raw": Counter(r["phase"] for r in rows),
        "phase_counts_clean": Counter(r["phase"] for r in clean),
    }
    return rows, summary


def message_body(x: dict[str, Any]) -> str:
    return str(x.get("message") or x.get("content") or "")


def message_sender(x: dict[str, Any]) -> str | None:
    return norm_agent(x.get("from") or x.get("agent"))


def message_targets(x: dict[str, Any]) -> list[str]:
    value = x.get("to")
    vals = value if isinstance(value, list) else [value]
    return [a for a in (norm_agent(v) for v in vals) if a]


def message_audit() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw, bad = jsonl(W / "board" / "messages.jsonl")
    rows = []
    semantic = []
    test_re = re.compile(r"(?i)(?:^|\b)(test message(?: \d+)?|hello from test|test/path|dummy|placeholder)(?:\b|$)")
    for i, x in enumerate(raw, 1):
        sender = message_sender(x)
        body = message_body(x)
        when = parse_time(x.get("time"))
        to_raw = x.get("to")
        broadcast = str(to_raw).lower() == "all" or (isinstance(to_raw, list) and "all" in to_raw)
        fixture = bool(test_re.search(body)) or str(x.get("from", "")).lower() in {"agent-test", "test"}
        target_agents = message_targets(x)
        sem = (str(x.get("from") or x.get("agent") or ""), json.dumps(to_raw, sort_keys=True, ensure_ascii=False), body)
        semantic.append(sem)
        rows.append({
            "line": i,
            "sender_raw": str(x.get("from") or x.get("agent") or ""),
            "sender": sender or "",
            "sender_in_roster": sender in ROSTER_SET,
            "to_raw": json.dumps(to_raw, ensure_ascii=False, sort_keys=True),
            "targets": ",".join(target_agents),
            "broadcast": broadcast,
            "body_chars": len(body),
            "time_raw": str(x.get("time") or ""),
            "time_utc": iso(when),
            "phase": "phase1" if when and when < PHASE2_START else ("phase2" if when else "unknown"),
            "heuristic_fixture": fixture,
            "body_sha256": hashlib.sha256(body.encode(errors="replace")).hexdigest(),
        })

    exact_objects = [json.dumps(x, ensure_ascii=False, sort_keys=True) for x in raw]
    clean_sem = [
        semantic[i] for i, r in enumerate(rows)
        if r["sender_in_roster"] and not r["heuristic_fixture"]
    ]
    summary = {
        "lines": len(raw),
        "parse_errors": len(bad),
        "roster_sender": sum(r["sender_in_roster"] for r in rows),
        "broadcast": sum(r["broadcast"] for r in rows),
        "heuristic_fixture": sum(r["heuristic_fixture"] for r in rows),
        "exact_object_duplicate_excess": len(exact_objects) - len(set(exact_objects)),
        "semantic_duplicate_excess_all": len(semantic) - len(set(semantic)),
        "semantic_duplicate_excess_clean": len(clean_sem) - len(set(clean_sem)),
        "nonroster_sender_labels": Counter(r["sender_raw"] or "[missing]" for r in rows if not r["sender_in_roster"]),
        "phase_counts": Counter(r["phase"] for r in rows),
    }
    return rows, summary


def load_models() -> dict[str, dict[str, Any]]:
    sessions = json.loads((W / "swarm_sessions.json").read_text())
    result = {}
    for x in sessions:
        aid = x["id"]
        model = x["model"]
        if model.startswith("gpt56_sol"):
            family = "sol"
        elif model.startswith("es1_orange"):
            family = "orange"
        else:
            family = "seed-stable"
        if any(k in model for k in ("xhigh", "thinking_max", "reasoning-high")):
            level = "high"
        elif any(k in model for k in ("reasoning_high", "_thinking", "-reasoning")):
            level = "mid"
        else:
            level = "base"
        result[aid] = {**x, "family": family, "level": level}
    return result


def phase_artifact_counts(artifacts: list[dict[str, Any]], phase_key: str = "phase_inferred") -> dict[str, Counter[str]]:
    out = {a: Counter() for a in ROSTER}
    for r in artifacts:
        if r["owner_in_roster"]:
            out[r["owner"]][f"{r[phase_key]}:{r['domain']}"] += 1
            out[r["owner"]][f"all:{r['domain']}"] += 1
    return out


def artifact_phase_summary(artifacts: list[dict[str, Any]], phase_key: str) -> dict[str, Any]:
    counts = phase_artifact_counts(artifacts, phase_key)
    result: dict[str, Any] = {"phase_key": phase_key}
    for phase in ("phase1", "phase2"):
        ns, shares, hhis = [], [], []
        for a in ROSTER:
            xs = [counts[a][f"{phase}:{d}"] for d in DOMAINS]
            ns.append(sum(xs))
            shares.append(max_share(xs))
            hhis.append(hhi(xs))
        active = [i for i, n in enumerate(ns) if n]
        spec_active = sum(shares[i] is not None and shares[i] >= 0.5 for i in active)
        result[phase] = {
            "entries": sum(ns),
            "active_agents": len(active),
            "output_gini_36": gini(ns),
            "specialists_ge_50_all36": sum(s is not None and s >= 0.5 for s in shares),
            "specialists_ge_50_active": spec_active,
            "specialist_rate_active": spec_active / len(active) if active else None,
            "specialist_rate_active_wilson95": wilson(spec_active, len(active)),
            "mean_hhi_active": statistics.mean(hhis[i] for i in active),
            "median_hhi_active": statistics.median(hhis[i] for i in active),
            "by_min_output": {
                str(t): {
                    "n": sum(n >= t for n in ns),
                    "specialists": sum(n >= t and s is not None and s >= 0.5 for n, s in zip(ns, shares)),
                }
                for t in (1, 3, 5, 10)
            },
        }

    # Small-n null: downsample each agent's Phase-1 domain labels to its Phase-2
    # count.  This shows how much HHI and the >=.5 rule rise mechanically when
    # agents only emit one or two entries.
    rng = random.Random(20260803)
    p1_labels: dict[str, list[str]] = {}
    p2_n: dict[str, int] = {}
    observed_hhi = []
    observed_spec = 0
    included = []
    for a in ROSTER:
        labels = []
        for d in DOMAINS:
            labels.extend([d] * counts[a][f"phase1:{d}"])
        n2 = sum(counts[a][f"phase2:{d}"] for d in DOMAINS)
        if labels and n2:
            p1_labels[a] = labels
            p2_n[a] = min(n2, len(labels))
            xs2 = [counts[a][f"phase2:{d}"] for d in DOMAINS]
            observed_hhi.append(hhi(xs2) or 0)
            observed_spec += (max_share(xs2) or 0) >= 0.5
            included.append(a)
    null_hhi, null_spec = [], []
    for _ in range(20000):
        hs, ss = [], 0
        for a in included:
            draw = rng.sample(p1_labels[a], p2_n[a])
            c = Counter(draw)
            xs = [c[d] for d in DOMAINS]
            hs.append(hhi(xs) or 0)
            ss += (max_share(xs) or 0) >= 0.5
        null_hhi.append(statistics.mean(hs))
        null_spec.append(ss)
    obs_h = statistics.mean(observed_hhi)
    result["small_n_downsample_null"] = {
        "agents": len(included),
        "observed_mean_hhi": obs_h,
        "null_mean_hhi_mean": statistics.mean(null_hhi),
        "null_mean_hhi_95": [quantile(null_hhi, .025), quantile(null_hhi, .975)],
        "one_sided_p_hhi": (1 + sum(x >= obs_h for x in null_hhi)) / (len(null_hhi) + 1),
        "observed_specialists": observed_spec,
        "null_specialists_mean": statistics.mean(null_spec),
        "null_specialists_95": [quantile([float(x) for x in null_spec], .025), quantile([float(x) for x in null_spec], .975)],
        "one_sided_p_specialists": (1 + sum(x >= observed_spec for x in null_spec)) / (len(null_spec) + 1),
    }
    return result


def clean_citation_edges(citations: list[dict[str, Any]], dedup_triples: bool = True) -> list[dict[str, Any]]:
    rows = [r for r in citations if r["owner_confirmed"]]
    if not dedup_triples:
        return rows
    seen = set()
    out = []
    for r in rows:
        key = (r["citer"], r["cited"], r["resolved_path"])
        if key not in seen:
            out.append(r)
            seen.add(key)
    return out


def reaper_audit(artifacts: list[dict[str, Any]], citations: list[dict[str, Any]], messages: list[dict[str, Any]], models: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    log_lines = (W / "vitals" / "reaper.log").read_text(errors="replace").splitlines()
    json_actions = []
    for line in log_lines:
        try:
            x = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(x, dict) and x.get("type"):
            when = parse_time(x.get("time"))
            json_actions.append({**x, "time_utc": iso(when)})

    # stdout and JSON appends targeted the same file and interleaved.  The JSON
    # stream lost parts of two cycles, while the human cycle summaries preserve
    # all five scoring passes.  Parse the summaries as the runtime action log;
    # retain JSON counts above as an integrity diagnostic only.
    actions = []
    current_cycle: dt.datetime | None = None
    for line in log_lines:
        m = re.search(r"\[Reaper\] Cycle at (\d{2}):(\d{2}):(\d{2})", line)
        if m:
            hh, mm, ss = map(int, m.groups())
            current_cycle = dt.datetime(2026, 8, 2, hh, mm, ss, tzinfo=LOCAL).astimezone(UTC)
            continue
        if current_cycle is None:
            continue
        am = re.search(r"(agent-\d{3}).*ALLIANCE PROTECTION \((\d+) distinct citers\)", line)
        if am:
            actions.append({"type": "alliance_protection", "agent": am.group(1),
                            "distinct_citers": int(am.group(2)), "time": iso(current_cycle)})
            continue
        am = re.search(r"(agent-\d{3}).*WARNING", line)
        if am:
            actions.append({"type": "warning", "agent": am.group(1), "time": iso(current_cycle)})
            continue
        am = re.search(r"(agent-\d{3}).*THROTTLED", line)
        if am:
            actions.append({"type": "throttle", "agent": am.group(1), "time": iso(current_cycle)})
            continue
        am = re.search(r"(agent-\d{3}).*KILLED", line)
        if am:
            actions.append({"type": "killed", "agent": am.group(1), "time": iso(current_cycle)})

    cycles = sorted({r["time"] for r in actions})
    clean = clean_citation_edges(citations, dedup_triples=False)
    cycle_rows = []
    for raw_cycle in cycles:
        cycle_utc = parse_time(raw_cycle)
        assert cycle_utc
        strict_lo = cycle_utc - dt.timedelta(hours=2)
        logged = [r for r in actions if r["time"] == raw_cycle and r["type"] == "alliance_protection"]
        for r in logged:
            aid = r["agent"]
            strict_raw = {
                c["citer"] for c in citations
                if c["cited"] == aid and c["citer"] in ROSTER_SET and c["citer"] != aid
                and c["time_utc"] and strict_lo <= parse_time(c["time_utc"]) <= cycle_utc
            }
            strict_clean = {
                c["citer"] for c in clean
                if c["cited"] == aid and c["time_utc"]
                and strict_lo <= parse_time(c["time_utc"]) <= cycle_utc
            }
            cycle_rows.append({
                "cycle_local_raw": raw_cycle,
                "cycle_utc": iso(cycle_utc),
                "agent": aid,
                "logged_distinct_citers": r.get("distinct_citers", ""),
                "strict_2h_raw_roster_distinct": len(strict_raw),
                "strict_2h_owner_confirmed_distinct": len(strict_clean),
                "logged_protection_survives_raw_2h": len(strict_raw) >= 3,
                "logged_protection_survives_clean_2h": len(strict_clean) >= 3,
            })

    post_kill = {}
    for aid, raw_when in KILLED.items():
        when = parse_time(raw_when)
        assert when
        post_entries = [
            r for r in artifacts if r["owner"] == aid and parse_time(r["inferred_create_utc"]) and parse_time(r["inferred_create_utc"]) > when
        ]
        post_msgs = [r for r in messages if r["sender"] == aid and r["time_utc"] and parse_time(r["time_utc"]) > when]
        post_cites = [r for r in citations if r["citer"] == aid and r["time_utc"] and parse_time(r["time_utc"]) > when]
        sid = models[aid].get("session_id")
        transcript_after = 0
        transcript_last = ""
        body_path = T / f"{sid}.json"
        if body_path.exists():
            body = json.loads(body_path.read_text(errors="replace"))
            ts = [
                dt.datetime.fromtimestamp(float(m["created_at"]), UTC)
                for m in body.get("messages", [])
                if m.get("role") == "assistant" and isinstance(m.get("created_at"), (int, float))
            ]
            transcript_after = sum(t > when for t in ts)
            transcript_last = iso(max(ts)) if ts else ""
        post_kill[aid] = {
            "killed_utc": iso(when),
            "artifact_entries_after": len(post_entries),
            "board_messages_after": len(post_msgs),
            "citations_sent_after": len(post_cites),
            "current_session_assistant_messages_after": transcript_after,
            "current_session_last_assistant_utc": transcript_last,
        }

    # Exact finite-population comparison: were the four labelled-killed agents
    # unusually generalist in Phase 1?  Enumerate all C(36,4) assignments.
    pc = phase_artifact_counts(artifacts)
    h1 = {}
    for a in ROSTER:
        h1[a] = hhi([pc[a][f"phase1:{d}"] for d in DOMAINS]) or 0
    kset = set(KILLED)
    obs = statistics.mean(h1[a] for a in kset) - statistics.mean(h1[a] for a in ROSTER if a not in kset)
    diffs = []
    for combo in itertools.combinations(ROSTER, 4):
        s = set(combo)
        diffs.append(statistics.mean(h1[a] for a in s) - statistics.mean(h1[a] for a in ROSTER if a not in s))
    mechanism = {
        "killed_mean_phase1_hhi": statistics.mean(h1[a] for a in kset),
        "survivor_mean_phase1_hhi": statistics.mean(h1[a] for a in ROSTER if a not in kset),
        "difference_killed_minus_survivor": obs,
        "exact_one_sided_p_killed_lower": sum(x <= obs for x in diffs) / len(diffs),
        "assignments": len(diffs),
    }

    summary = {
        "json_action_records_partial_due_interleaved_writes": len(json_actions),
        "json_action_counts_partial": Counter(r["type"] for r in json_actions),
        "human_summary_action_records": len(actions),
        "action_counts": Counter(r["type"] for r in actions),
        "action_cycles": len(cycles),
        "first_action_cycle_utc": iso(parse_time(cycles[0])) if cycles else "",
        "last_action_cycle_utc": iso(parse_time(cycles[-1])) if cycles else "",
        "logged_alliance_events": len(cycle_rows),
        "logged_alliance_events_valid_under_strict_raw_2h": sum(r["logged_protection_survives_raw_2h"] for r in cycle_rows),
        "logged_alliance_events_valid_under_strict_clean_2h": sum(r["logged_protection_survives_clean_2h"] for r in cycle_rows),
        "post_kill": post_kill,
        "killed_hhi_mechanism_test": mechanism,
        "expansion_agents_in_sessions_file": sum(int(x.split("-")[1]) >= 37 for x in models),
    }
    return cycle_rows, summary


def transcript_audit(models: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    meta_files = sorted(T.glob("*.meta.json"))
    body_files = sorted(p for p in T.glob("*.json") if not p.name.endswith(".meta.json"))
    body_names = {p.name for p in body_files}
    rows = []
    swarm_missing_body = []
    gen2_memory_none = []
    gen2_false_none = []

    # Raw Phase-1 incoming citation existence, matching what the reaper used
    # rather than the empty board/citations file read by the resurrector.
    raw_cites, _ = jsonl(W / "citations.jsonl")
    incoming_pre = Counter()
    for c in raw_cites:
        a = norm_agent(c.get("cited"))
        t = parse_time(c.get("time"))
        if a in ROSTER_SET and t and t < PHASE2_START:
            incoming_pre[a] += 1

    for mf in meta_files:
        try:
            meta = json.loads(mf.read_text(errors="replace"))
        except json.JSONDecodeError:
            continue
        working = str(meta.get("working_dir") or "").rstrip("/")
        if working != "/Users/bytedance/Downloads/swarm":
            continue
        sid = str(meta.get("session_id") or mf.name.removesuffix(".meta.json"))
        bf = T / f"{sid}.json"
        if not bf.exists():
            swarm_missing_body.append(sid)
            continue
        # Several sessions are hundreds of MB.  Loading each JSON object can
        # exceed a laptop process' memory even though we only need its opening
        # prompt.  Root identity and injected memory occur at the front; meta
        # files provide authoritative counts and interval endpoints.  Stream
        # role counters separately so memory stays O(1).
        try:
            with bf.open("rb") as f:
                prefix = f.read(4 * 1024 * 1024).decode("utf-8", errors="replace")
        except OSError:
            rows.append({"session": sid, "parse_error": True})
            continue
        # Decode only the first few objects in messages[].  Searching the raw
        # prefix would also hit a copy of the parent's prompt embedded later in
        # a sub-agent system block, falsely classifying sub-agents as roots.
        opening_messages: list[dict[str, Any]] = []
        marker = re.search(r'"messages"\s*:\s*\[', prefix)
        if marker:
            pos = marker.end()
            decoder = json.JSONDecoder()
            while len(opening_messages) < 6:
                while pos < len(prefix) and prefix[pos] in " \r\n\t,":
                    pos += 1
                if pos >= len(prefix) or prefix[pos] == "]":
                    break
                try:
                    obj, pos = decoder.raw_decode(prefix, pos)
                except json.JSONDecodeError:
                    break
                if isinstance(obj, dict):
                    opening_messages.append(obj)
        opening = "\n".join(
            str(m.get("content") or "") for m in opening_messages if m.get("role") == "user"
        )
        match = re.search(r"你是 (agent-\d+)。你是 (?:36|100) 个同时运行的自主智能体之一", opening)
        if not match:
            match = re.search(r"You are (agent-\d+), a member of a (?:36|100)-agent swarm", opening)
        aid = norm_agent(match.group(1)) if match else None
        generation = 2 if aid and re.search(r"Generation 2|Generation 2", opening, re.I) else (1 if aid else None)
        assistant_count = 0
        assistant_times: list[dt.datetime] = []
        # Raw JSON tokens occurring inside content are escaped, so unescaped
        # role/created_at tokens provide a memory-safe message scanner.
        token_re = re.compile(
            rb'"role"\s*:\s*"(assistant|user|tool|system)"|"created_at"\s*:\s*([0-9]+(?:\.[0-9]+)?)'
        )
        pending_assistant = False
        carry = b""
        with bf.open("rb") as f:
            while True:
                chunk = f.read(4 * 1024 * 1024)
                if not chunk:
                    break
                data = carry + chunk
                safe_end = max(0, len(data) - 128)
                for tm in token_re.finditer(data):
                    if tm.start() >= safe_end:
                        break
                    if tm.group(1):
                        pending_assistant = tm.group(1) == b"assistant"
                        if pending_assistant:
                            assistant_count += 1
                    elif pending_assistant and tm.group(2):
                        assistant_times.append(dt.datetime.fromtimestamp(float(tm.group(2)), UTC))
                        pending_assistant = False
                carry = data[safe_end:]
        for tm in token_re.finditer(carry):
            if tm.group(1):
                pending_assistant = tm.group(1) == b"assistant"
                if pending_assistant:
                    assistant_count += 1
            elif pending_assistant and tm.group(2):
                assistant_times.append(dt.datetime.fromtimestamp(float(tm.group(2)), UTC))
                pending_assistant = False
        memory_none = False
        if aid and generation == 2:
            memory_none = bool(re.search(r"Agents who cited me:\s*none", opening))
            if memory_none:
                gen2_memory_none.append(aid)
                if incoming_pre[aid] > 0:
                    gen2_false_none.append(aid)
        rows.append({
            "session": sid,
            "base_session": re.sub(r"\.archive\.\d+$", "", sid),
            "model": meta.get("model") or "",
            "root_agent": aid or "",
            "root_generation": generation or "",
            "is_root_swarm_session": bool(aid),
            "meta_created_utc": iso(dt.datetime.fromtimestamp(float(meta["created_at"]), UTC)) if meta.get("created_at") else "",
            "meta_updated_utc": iso(dt.datetime.fromtimestamp(float(meta["updated_at"]), UTC)) if meta.get("updated_at") else "",
            "meta_message_count": meta.get("message_count", ""),
            "actual_message_count": "not_loaded_memory_safe",
            "assistant_messages_stream_count": assistant_count,
            "first_assistant_utc": iso(min(assistant_times)) if assistant_times else "",
            "last_assistant_utc": iso(max(assistant_times)) if assistant_times else "",
            "usage_records": "not_scanned",
            "prompt_tokens_recorded": "",
            "completion_tokens_recorded": "",
            "cached_tokens_recorded": "",
            "gen2_memory_says_no_inbound_citers": memory_none,
            "phase1_raw_inbound_events": incoming_pre[aid] if aid else "",
            "parse_error": False,
        })

    # Compaction archive fragments and the current file share one base session.
    # A fragment carrying the opening prompt identifies the whole base session.
    base_identity: dict[str, tuple[str, Any]] = {}
    for r in rows:
        if r.get("is_root_swarm_session"):
            base_identity[r["base_session"]] = (r["root_agent"], r["root_generation"])
    for r in rows:
        if r.get("base_session") in base_identity:
            r["root_agent"], r["root_generation"] = base_identity[r["base_session"]]
            r["is_root_swarm_session"] = True

    roots = [r for r in rows if r.get("is_root_swarm_session")]
    base_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in roots:
        base_rows[r["base_session"]].append(r)
    base_sessions = []
    for base, rs in base_rows.items():
        base_sessions.append({
            "base": base,
            "agent": rs[0]["root_agent"],
            "generation": rs[0]["root_generation"],
            "created": min(parse_time(r["meta_created_utc"]) for r in rs if r["meta_created_utc"]),
            "updated": max(parse_time(r["meta_updated_utc"]) for r in rs if r["meta_updated_utc"]),
            "last_assistant": max(
                (parse_time(r["last_assistant_utc"]) for r in rs if r["last_assistant_utc"]),
                default=None,
            ),
            "files": len(rs),
        })
    by_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in base_sessions:
        by_agent[r["agent"]].append(r)
    overlaps = []
    for a, rs in by_agent.items():
        g1 = [r for r in rs if r["generation"] == 1]
        g2 = [r for r in rs if r["generation"] == 2]
        for x in g1:
            for y in g2:
                if x["updated"] > y["created"]:
                    overlaps.append(a)

    current_sids = {x["session_id"] for x in models.values()}
    summary = {
        "directory_meta_files_all": len(meta_files),
        "directory_body_files_all": len(body_files),
        "body_files_without_meta_all": len(body_names - {p.name.replace(".meta.json", ".json") for p in meta_files}),
        "swarm_meta_files": len(rows) + len(swarm_missing_body),
        "swarm_missing_body": swarm_missing_body,
        "swarm_root_sessions": len(roots),
        "swarm_root_base_sessions": len(base_sessions),
        "root_archive_fragment_files": len(roots) - len(base_sessions),
        "root_sessions_by_generation": Counter(str(r["root_generation"]) for r in roots),
        "root_agents_by_generation": {
            str(g): len({r["agent"] for r in base_sessions if r["generation"] == g}) for g in (1, 2)
        },
        "root_base_sessions_by_generation": Counter(str(r["generation"]) for r in base_sessions),
        "root_sessions_agent_ge_37": sum(int(r["root_agent"].split("-")[1]) >= 37 for r in roots),
        "agents_with_duplicate_gen2_base_sessions": sorted(
            a for a, rs in by_agent.items() if sum(r["generation"] == 2 for r in rs) > 1
        ),
        "agents_with_phase1_phase2_session_interval_overlap": sorted(set(overlaps)),
        "phase1_base_sessions_with_assistant_after_phase2_start": sorted(
            r["agent"] for r in base_sessions
            if r["generation"] == 1 and r["last_assistant"] and r["last_assistant"] > PHASE2_START
        ),
        "current_session_ids_found": sum(any(r["session"] == sid for r in rows) for sid in current_sids),
        "gen2_prompts_saying_no_inbound_citers": sorted(set(gen2_memory_none)),
        "gen2_false_no_inbound_citer_prompts": sorted(set(gen2_false_none)),
        "assistant_messages_stream_count": sum(int(r.get("assistant_messages_stream_count") or 0) for r in rows),
        "token_usage_not_rescanned_reason": "body JSONs total hundreds of MB; cost is outside this social-output audit",
    }
    return rows, summary


def agent_and_group_metrics(artifacts: list[dict[str, Any]], citations: list[dict[str, Any]], messages: list[dict[str, Any]], models: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pc = phase_artifact_counts(artifacts)
    clean = clean_citation_edges(citations, dedup_triples=True)
    cin = Counter(r["cited"] for r in clean)
    cout = Counter(r["citer"] for r in clean)
    in_neighbors: dict[str, set[str]] = defaultdict(set)
    out_neighbors: dict[str, set[str]] = defaultdict(set)
    for r in clean:
        in_neighbors[r["cited"]].add(r["citer"])
        out_neighbors[r["citer"]].add(r["cited"])
    msgc = Counter(r["sender"] for r in messages if r["sender_in_roster"] and not r["heuristic_fixture"])
    rows = []
    for a in ROSTER:
        p1 = [pc[a][f"phase1:{d}"] for d in DOMAINS]
        p2 = [pc[a][f"phase2:{d}"] for d in DOMAINS]
        allc = [pc[a][f"all:{d}"] for d in DOMAINS]
        rows.append({
            "agent": a,
            "model": models[a]["model"],
            "family": models[a]["family"],
            "level": models[a]["level"],
            "seed": a in SEEDS,
            "scout": a in SCOUTS,
            "killed_label": a in KILLED,
            "outputs_phase1": sum(p1),
            "outputs_phase2": sum(p2),
            "outputs_all": sum(allc),
            "phase1_hhi": hhi(p1),
            "phase2_hhi": hhi(p2),
            "phase1_primary_share": max_share(p1),
            "phase2_primary_share": max_share(p2),
            "clean_citation_events_in": cin[a],
            "clean_citation_events_out": cout[a],
            "clean_distinct_citers_in": len(in_neighbors[a]),
            "clean_distinct_targets_out": len(out_neighbors[a]),
            "clean_board_messages": msgc[a],
            **{f"outputs_{d}": allc[i] for i, d in enumerate(DOMAINS)},
        })

    def aggregate(key: str) -> dict[str, Any]:
        out = {}
        for val in sorted({str(r[key]) for r in rows}):
            rs = [r for r in rows if str(r[key]) == val]
            out[val] = {
                "n": len(rs),
                "mean_outputs": statistics.mean(r["outputs_all"] for r in rs),
                "mean_phase2_outputs": statistics.mean(r["outputs_phase2"] for r in rs),
                "mean_clean_in": statistics.mean(r["clean_citation_events_in"] for r in rs),
                "mean_clean_out": statistics.mean(r["clean_citation_events_out"] for r in rs),
                "mean_messages": statistics.mean(r["clean_board_messages"] for r in rs),
                "killed": sum(r["killed_label"] for r in rs),
            }
        return out

    # Exact 4^3 assignment sensitivity for the hidden seed prompt.  One agent
    # was treated in each family mid-level block.  This is descriptive after
    # the prompt leaked, but the finite assignment space makes uncertainty clear.
    strata = [
        [f"agent-{i:03d}" for i in range(5, 9)],
        [f"agent-{i:03d}" for i in range(17, 21)],
        [f"agent-{i:03d}" for i in range(29, 33)],
    ]
    row_by = {r["agent"]: r for r in rows}

    def seed_exact(metric: str) -> dict[str, float]:
        assignments = [set(x) for x in itertools.product(*strata)]
        def stat(s: set[str]) -> float:
            return statistics.mean(float(row_by[a][metric]) for a in s) - statistics.mean(
                float(row_by[a][metric]) for group in strata for a in group if a not in s
            )
        obs = stat(SEEDS)
        vals = [stat(s) for s in assignments]
        return {
            "observed_seed_minus_matched_controls": obs,
            "one_sided_p_positive": sum(x >= obs for x in vals) / len(vals),
            "two_sided_p": sum(abs(x) >= abs(obs) for x in vals) / len(vals),
            "assignments": len(vals),
        }

    summary = {
        "by_family": aggregate("family"),
        "by_level": aggregate("level"),
        "by_model": aggregate("model"),
        "seed_exact_full_run": {
            k: seed_exact(k) for k in (
                "outputs_all", "clean_citation_events_out", "clean_citation_events_in",
                "clean_distinct_targets_out", "clean_board_messages",
            )
        },
    }
    return rows, summary


def network_audit(citations: list[dict[str, Any]], messages: list[dict[str, Any]]) -> dict[str, Any]:
    clean = clean_citation_edges(citations, dedup_triples=True)
    cpairs = {(r["citer"], r["cited"]) for r in clean}
    mutual_directed = sum(a != b and (b, a) in cpairs for a, b in cpairs)
    msg_pairs = set()
    for r in messages:
        if not r["sender_in_roster"] or r["broadcast"] or r["heuristic_fixture"]:
            continue
        for target in r["targets"].split(",") if r["targets"] else []:
            if target in ROSTER_SET and target != r["sender"]:
                msg_pairs.add((r["sender"], target))

    result: dict[str, Any] = {
        "citation_directed_pair_edges": len(cpairs),
        "citation_density": len(cpairs) / (36 * 35),
        "citation_mutual_directed_fraction": mutual_directed / len(cpairs) if cpairs else 0,
        "direct_message_pair_edges_excluding_broadcast": len(msg_pairs),
        "direct_message_density": len(msg_pairs) / (36 * 35),
        "citation_message_pair_jaccard": len(cpairs & msg_pairs) / len(cpairs | msg_pairs) if cpairs | msg_pairs else 0,
    }
    try:
        import networkx as nx
        g = nx.Graph()
        g.add_nodes_from(ROSTER)
        weights = Counter(tuple(sorted((a, b))) for a, b in cpairs if a != b)
        for (a, b), weight in weights.items():
            g.add_edge(a, b, weight=weight)
        comms = nx.community.louvain_communities(g, weight="weight", resolution=1, seed=20260803)
        q = nx.community.modularity(g, comms, weight="weight")
        result.update({
            "citation_louvain_communities": [sorted(c) for c in comms],
            "citation_louvain_modularity": q,
            "citation_connected_components": [sorted(c) for c in nx.connected_components(g)],
        })
    except Exception as exc:  # network metrics are supplemental, not a gate
        result["networkx_error"] = repr(exc)
    return result


def citation_path_split() -> dict[str, Any]:
    root, _ = jsonl(W / "citations.jsonl")
    board, _ = jsonl(W / "board" / "citations.jsonl")
    def key(x: dict[str, Any]) -> tuple[str, str, str]:
        return (
            norm_agent(x.get("citer") or x.get("from")) or "",
            norm_agent(x.get("cited") or x.get("to")) or "",
            str(x.get("file") or x.get("artifact") or ""),
        )
    rk = {key(x) for x in root}
    bk = [key(x) for x in board]
    return {
        "root_lines_reaper_reads": len(root),
        "board_lines_gen2_prompt_directs": len(board),
        "board_semantic_records_mirrored_in_root": sum(x in rk for x in bk),
        "board_semantic_records_not_in_root": sum(x not in rk for x in bk),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    keys = []
    seen = set()
    for row in rows:
        for k in row:
            if k not in seen:
                keys.append(k)
                seen.add(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def json_default(x: Any) -> Any:
    if isinstance(x, Counter):
        return dict(x)
    if isinstance(x, set):
        return sorted(x)
    if isinstance(x, Path):
        return str(x)
    raise TypeError(type(x).__name__)


def main() -> None:
    print("stage:artifact_inventory", flush=True)
    artifacts, integrity = artifact_inventory()
    print("stage:path_index", flush=True)
    rel_index, base_index = build_path_index()
    print("stage:citations", flush=True)
    citations, cite_summary = citation_audit(rel_index, base_index)
    print("stage:messages", flush=True)
    messages, msg_summary = message_audit()
    print("stage:models", flush=True)
    models = load_models()
    print("stage:reaper", flush=True)
    reaper_rows, reaper_summary = reaper_audit(artifacts, citations, messages, models)
    print("stage:transcripts", flush=True)
    transcripts, transcript_summary = transcript_audit(models)
    print("stage:agents", flush=True)
    agents, group_summary = agent_and_group_metrics(artifacts, citations, messages, models)
    print("stage:summary", flush=True)

    summary = {
        "source": {"workspace": str(W), "transcripts": str(T)},
        "boundaries": {
            "phase2_start_utc": iso(PHASE2_START),
            "expansion_attempt_start_utc": iso(EXPANSION_START),
            "seed_identity_public_leak_utc": iso(SEED_LEAK),
        },
        "integrity": integrity,
        "artifacts_inferred_time": artifact_phase_summary(artifacts, "phase_inferred"),
        "artifacts_mtime_sensitivity": artifact_phase_summary(artifacts, "phase_mtime"),
        "citations": cite_summary,
        "messages": msg_summary,
        "reaper": reaper_summary,
        "transcripts": transcript_summary,
        "model_seed_scout": group_summary,
        "networks": network_audit(citations, messages),
        "citation_path_split": citation_path_split(),
    }

    write_csv(OUT / "artifact_inventory.csv", artifacts)
    write_csv(OUT / "citation_audit.csv", citations)
    write_csv(OUT / "message_audit.csv", messages)
    write_csv(OUT / "reaper_alliance_recheck.csv", reaper_rows)
    write_csv(OUT / "transcript_sessions.csv", transcripts)
    write_csv(OUT / "agent_metrics.csv", agents)
    (OUT / "audit_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=json_default) + "\n"
    )
    print(json.dumps({
        "effective_roster": 36,
        "expansion_effective": transcript_summary["root_sessions_agent_ge_37"],
        "artifacts": integrity["top_level_commons_entries"],
        "citations_raw": cite_summary["lines"],
        "citations_owner_confirmed": cite_summary["owner_confirmed_events"],
        "messages": msg_summary["lines"],
        "reaper_killed": reaper_summary["action_counts"].get("killed", 0),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
