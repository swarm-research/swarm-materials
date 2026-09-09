#!/usr/bin/env python3
"""Deterministic raw-transcript audit builder for Agents 031--036.

The eligible-session boundary is defined only by the base session meta.name.
Archive segments inherit eligibility from their base session.  This script never
uses readable summaries as transcript evidence.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
import textwrap
from pathlib import Path


SOURCE_ROOT = Path("/Users/bytedance/Downloads/swarm-archive-20260803/02_transcripts")
OUT_DIR = Path(
    "/Users/bytedance/Documents/Codex/2026-08-03/ni/work/full_corpus_audit/"
    "batches/gen1_transcripts_agents_031_036"
)
ELIGIBLE_NAME_RE = re.compile(
    r"agent\s*[-_]?\s*0*(31|32|33|34|35|36)(?!\d)", re.IGNORECASE
)
ARCHIVE_RE = re.compile(r"\.archive\.(\d+)\.json$")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def eligible_sessions() -> list[dict]:
    rows: list[dict] = []
    for meta_path in sorted(SOURCE_ROOT.glob("*.meta.json")):
        if ".archive." in meta_path.name:
            continue
        meta = load_json(meta_path)
        match = ELIGIBLE_NAME_RE.search(meta.get("name") or "")
        if not match:
            continue
        rows.append(
            {
                "actor": f"agent-{int(match.group(1)):03d}",
                "session_id": meta["session_id"],
                "base_meta_path": meta_path,
                "base_meta": meta,
            }
        )
    expected_actors = {f"agent-{number:03d}" for number in range(31, 37)}
    observed_actors = {row["actor"] for row in rows}
    if observed_actors != expected_actors:
        raise RuntimeError(
            f"eligible actor mismatch: expected={sorted(expected_actors)} "
            f"observed={sorted(observed_actors)}"
        )
    if len(rows) != 12:
        raise RuntimeError(f"expected 12 eligible base sessions, got {len(rows)}")
    return sorted(rows, key=lambda row: (row["actor"], row["base_meta"]["created_at"]))


def segment_paths(session_id: str) -> list[tuple[str, int, Path]]:
    archives: list[tuple[str, int, Path]] = []
    for path in SOURCE_ROOT.glob(f"{session_id}.archive.*.json"):
        match = ARCHIVE_RE.search(path.name)
        if match:
            index = int(match.group(1))
            archives.append((f"archive.{index}", index, path))
    archives.sort(key=lambda item: item[1])
    main = SOURCE_ROOT / f"{session_id}.json"
    return archives + [("main", len(archives), main)]


def build_source_inventory() -> list[dict]:
    rows: list[dict] = []
    for session in eligible_sessions():
        base_meta = session["base_meta"]
        for segment_label, chain_order, raw_path in segment_paths(session["session_id"]):
            meta_path = raw_path.with_suffix(".meta.json")
            if not raw_path.is_file() or not meta_path.is_file():
                raise FileNotFoundError(f"missing raw/meta pair: {raw_path} / {meta_path}")
            raw_bytes = raw_path.read_bytes()
            meta_bytes = meta_path.read_bytes()
            raw = json.loads(raw_bytes)
            meta = json.loads(meta_bytes)
            messages = raw.get("messages")
            if not isinstance(messages, list):
                raise TypeError(f"messages is not a list: {raw_path}")
            roles = collections.Counter(str(message.get("role", "")) for message in messages)
            tool_calls = sum(len(message.get("tool_calls") or []) for message in messages)
            timestamps = [
                message["created_at"]
                for message in messages
                if isinstance(message.get("created_at"), (int, float))
            ]
            rows.append(
                {
                    "actor_label": session["actor"],
                    "session_id": session["session_id"],
                    "eligible_meta_name": base_meta.get("name", ""),
                    "eligibility_rule": "base meta.name explicit Agent-031..036",
                    "segment_label": segment_label,
                    "segment_chain_order": chain_order,
                    "segment_meta_name": meta.get("name", ""),
                    "raw_path": str(raw_path),
                    "meta_path": str(meta_path),
                    "raw_bytes": len(raw_bytes),
                    "meta_bytes": len(meta_bytes),
                    "raw_sha256": sha256_bytes(raw_bytes),
                    "meta_sha256": sha256_bytes(meta_bytes),
                    "raw_session_id": raw.get("session_id", ""),
                    "meta_session_id": meta.get("session_id", ""),
                    "message_count_actual": len(messages),
                    "message_count_meta": meta.get("message_count", ""),
                    "user_messages": roles.get("user", 0),
                    "assistant_messages": roles.get("assistant", 0),
                    "tool_messages": roles.get("tool", 0),
                    "other_messages": len(messages)
                    - roles.get("user", 0)
                    - roles.get("assistant", 0)
                    - roles.get("tool", 0),
                    "tool_calls": tool_calls,
                    "first_event_ts": min(timestamps) if timestamps else "",
                    "last_event_ts": max(timestamps) if timestamps else "",
                    "model": meta.get("model", ""),
                    "forked_from": meta.get("forked_from", ""),
                    "fork_root_id": meta.get("fork_root_id", ""),
                    "fork_depth": meta.get("fork_depth", ""),
                    "parse_status": "ok",
                }
            )
    if len(rows) != 21:
        raise RuntimeError(f"expected 21 eligible raw segments, got {len(rows)}")
    raw_paths = [row["raw_path"] for row in rows]
    meta_paths = [row["meta_path"] for row in rows]
    if len(raw_paths) != len(set(raw_paths)) or len(meta_paths) != len(set(meta_paths)):
        raise RuntimeError("duplicate source path in inventory")
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise RuntimeError(f"refusing to write empty CSV: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def flat_excerpt(value: object, limit: int = 800) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", "\\0")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]} … [{len(text)} chars]"


def text_sha(value: object) -> str:
    if value is None:
        return ""
    return sha256_bytes(str(value).encode("utf-8", errors="replace"))


def parse_tool_arguments(tool_call: dict) -> tuple[str, object]:
    raw = tool_call.get("function", {}).get("arguments", "")
    if not isinstance(raw, str):
        return json.dumps(raw, ensure_ascii=False, sort_keys=True), raw
    try:
        return raw, json.loads(raw)
    except Exception:
        return raw, {"__unparsed__": raw}


def tool_action_summary(tool_call: dict) -> str:
    function = tool_call.get("function", {})
    name = function.get("name", "")
    raw, args = parse_tool_arguments(tool_call)
    if not isinstance(args, dict):
        return f"{name}: arguments={flat_excerpt(raw, 400)}"
    if name == "Bash":
        return (
            f"Bash: {flat_excerpt(args.get('description', ''), 180)} | "
            f"command={flat_excerpt(args.get('command', ''), 500)}"
        )
    if name == "Write":
        content = args.get("content", "")
        return (
            f"Write: {args.get('file_path', '')}; payload_chars={len(str(content))}; "
            f"payload_sha256={text_sha(content)}; first={flat_excerpt(content, 220)}"
        )
    if name == "Edit":
        old = args.get("old_string", "")
        new = args.get("new_string", "")
        return (
            f"Edit: {args.get('file_path', '')}; old_chars={len(str(old))}; "
            f"new_chars={len(str(new))}; old_sha256={text_sha(old)}; "
            f"new_sha256={text_sha(new)}; replace_all={args.get('replace_all', '')}"
        )
    if name == "Read":
        return (
            f"Read: {args.get('file_path', '')}; offset={args.get('offset', '')}; "
            f"limit={args.get('limit', '')}"
        )
    if name == "Grep":
        return (
            f"Grep: pattern={flat_excerpt(args.get('pattern', ''), 180)}; "
            f"path={args.get('path', '')}; mode={args.get('output_mode', '')}; "
            f"head_limit={args.get('head_limit', '')}"
        )
    if name == "Glob":
        return f"Glob: pattern={args.get('pattern', '')}; path={args.get('path', '')}"
    if name == "Task":
        tasks = args.get("tasks") or []
        task_bits = []
        for task in tasks:
            prompt = task.get("prompt", "")
            task_bits.append(
                f"{task.get('subagent_name', '')}/{task.get('description', '')} "
                f"prompt_chars={len(str(prompt))} prompt_sha256={text_sha(prompt)} "
                f"prompt={flat_excerpt(prompt, 260)}"
            )
        return "Task: " + " || ".join(task_bits)
    if name in {"QueryAgent", "KillAgent", "SendMessage", "BashOutput", "KillBash"}:
        return f"{name}: {flat_excerpt(json.dumps(args, ensure_ascii=False, sort_keys=True), 650)}"
    if name in {"TaskGraphCreate", "TaskGraphUpdate", "TaskGraphList", "TodoWrite"}:
        return f"{name}: {flat_excerpt(json.dumps(args, ensure_ascii=False, sort_keys=True), 650)}"
    return f"{name}: {flat_excerpt(json.dumps(args, ensure_ascii=False, sort_keys=True), 650)}"


def classify_user_message(message: dict) -> str:
    content = str(message.get("content") or "")
    extra = message.get("extra") or {}
    if extra.get("environment_reminder"):
        return "environment_reminder"
    if "[Incoming Agent Messages]" in content:
        return "incoming_agent_message"
    if "message(s) above arrived mid-task" in content:
        return "incoming_message_followup"
    if "Generation 2" in content and "你是 agent-" in content:
        return "generation2_memory_injection"
    # Condensation summaries can quote an earlier forced-wakeup message.  They
    # must be classified by their envelope before looking for quoted phrases;
    # otherwise a summary containing “你停下来了吗…不许停” is falsely counted
    # as a new runner intervention (observed in agent-036 main:1).
    if "<conversation-summary>" in content or "OVERSIZED TOOL RESULTS" in content:
        return "condense_continuation_injection"
    if content.lstrip().startswith("你停下来了吗？") and "不许停" in content:
        return "maso_do_not_stop_wakeup"
    if "你是 agent-" in content and "36 个同时运行" in content:
        return "generation1_initial_prompt"
    return "user_or_system_injection"


def classify_message(message: dict) -> str:
    role = message.get("role", "")
    if role == "user":
        return classify_user_message(message)
    if role == "tool":
        return "tool_result"
    if role == "assistant":
        extra = message.get("extra") or {}
        if extra.get("agent_error") or extra.get("llm_call_failed"):
            return "assistant_provider_error"
        if message.get("tool_calls"):
            return "assistant_tool_request"
        return "assistant_narrative_or_stop"
    return "other"


def build_event_rows(inventory_rows: list[dict]) -> list[dict]:
    by_session: dict[str, list[dict]] = collections.defaultdict(list)
    for source in inventory_rows:
        by_session[source["session_id"]].append(source)
    events: list[dict] = []
    for session_id, sources in sorted(
        by_session.items(),
        key=lambda item: (
            item[1][0]["actor_label"],
            min(float(row["first_event_ts"] or 0) for row in item[1]),
        ),
    ):
        sources.sort(key=lambda row: int(row["segment_chain_order"]))
        seen_message_ids: dict[str, str] = {}
        physical_order = 0
        logical_order = 0
        for source in sources:
            raw = load_json(Path(source["raw_path"]))
            for raw_index, message in enumerate(raw["messages"]):
                physical_order += 1
                message_id = str(message.get("id") or "")
                event_key = f"{session_id}:{source['segment_label']}:{raw_index}"
                duplicate_of = seen_message_ids.get(message_id, "") if message_id else ""
                if not duplicate_of:
                    logical_order += 1
                    if message_id:
                        seen_message_ids[message_id] = event_key
                content = message.get("content")
                reasoning = message.get("reasoning_content")
                calls = message.get("tool_calls") or []
                raw_argument_strings = [parse_tool_arguments(call)[0] for call in calls]
                usage = message.get("usage") or {}
                extra = message.get("extra") or {}
                events.append(
                    {
                        "event_key": event_key,
                        "actor_label": source["actor_label"],
                        "session_id": session_id,
                        "eligible_meta_name": source["eligible_meta_name"],
                        "segment_label": source["segment_label"],
                        "segment_meta_name": source["segment_meta_name"],
                        "segment_chain_order": source["segment_chain_order"],
                        "raw_index": raw_index,
                        "physical_event_order": physical_order,
                        "logical_event_order": "" if duplicate_of else logical_order,
                        "duplicate_of_event_key": duplicate_of,
                        "message_id": message_id,
                        "created_at": message.get("created_at", ""),
                        "role": message.get("role", ""),
                        "event_type": classify_message(message),
                        "runtime_actor_id": extra.get("agent_id", ""),
                        "origin_model_alias": message.get("origin_model_alias", ""),
                        "model": extra.get("model", ""),
                        "finish_reason": extra.get("finish_reason", ""),
                        "stop_reason": extra.get("stop_reason", ""),
                        "loss_mask": message.get("loss_mask", ""),
                        "content_chars": len(str(content)) if content is not None else 0,
                        "content_sha256": text_sha(content),
                        "content_excerpt": flat_excerpt(content),
                        "reasoning_chars": len(str(reasoning)) if reasoning is not None else 0,
                        "reasoning_sha256": text_sha(reasoning),
                        "reasoning_excerpt": flat_excerpt(reasoning),
                        "tool_call_count": len(calls),
                        "tool_call_ids": "|".join(str(call.get("id", "")) for call in calls),
                        "tool_names": "|".join(
                            str(call.get("function", {}).get("name", "")) for call in calls
                        ),
                        "tool_arguments_chars": sum(len(value) for value in raw_argument_strings),
                        "tool_arguments_sha256": text_sha("\n".join(raw_argument_strings)),
                        "tool_action_summary": " || ".join(tool_action_summary(call) for call in calls),
                        "tool_call_id": message.get("tool_call_id", ""),
                        "prompt_tokens": usage.get("prompt_tokens", ""),
                        "completion_tokens": usage.get("completion_tokens", ""),
                        "cached_tokens": usage.get("cached_tokens", ""),
                        "total_tokens": usage.get("total_tokens", ""),
                        "agent_error": extra.get("agent_error", ""),
                        "llm_call_failed": extra.get("llm_call_failed", ""),
                        "raw_path": source["raw_path"],
                        "audit_note": "",
                        "theme": "",
                        "evidence_status": "",
                    }
                )
    return events


def write_traces(event_rows: list[dict]) -> None:
    trace_dir = OUT_DIR / "scratch_traces"
    compact_dir = OUT_DIR / "scratch_compact_traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    compact_dir.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict]] = collections.defaultdict(list)
    for row in event_rows:
        grouped[row["session_id"]].append(row)
    for session_id, rows in grouped.items():
        lines = [
            f"# Raw-derived event trace: {rows[0]['actor_label']} / {session_id}",
            "",
            "Every physical message is listed. Long payloads remain addressable by raw path, "
            "raw index, character count, and SHA-256 in event_ledger.csv.",
            "",
        ]
        for row in rows:
            lines.extend(
                [
                    (
                        f"## {row['event_key']} | p={row['physical_event_order']} "
                        f"l={row['logical_event_order'] or '-'} | {row['created_at']} | "
                        f"{row['role']} | {row['event_type']}"
                    ),
                    f"- segment: {row['segment_label']} / {row['segment_meta_name']}",
                    f"- runtime actor: {row['runtime_actor_id']}",
                    f"- duplicate of: {row['duplicate_of_event_key'] or '-'}",
                    f"- content ({row['content_chars']} chars): {row['content_excerpt']}",
                    f"- reasoning ({row['reasoning_chars']} chars): {row['reasoning_excerpt']}",
                    f"- tools: {row['tool_action_summary']}",
                    "",
                ]
            )
        (trace_dir / f"{rows[0]['actor_label']}_{session_id}.md").write_text(
            "\n".join(lines), encoding="utf-8"
        )
        compact_lines = []
        for row in rows:
            if row["duplicate_of_event_key"]:
                semantic = f"DUPLICATE_OF={row['duplicate_of_event_key']}"
            else:
                semantic = " | ".join(
                    bit
                    for bit in (
                        f"C={flat_excerpt(row['content_excerpt'], 360)}"
                        if row["content_excerpt"]
                        else "",
                        f"R={flat_excerpt(row['reasoning_excerpt'], 520)}"
                        if row["reasoning_excerpt"]
                        else "",
                        f"T={flat_excerpt(row['tool_action_summary'], 720)}"
                        if row["tool_action_summary"]
                        else "",
                    )
                    if bit
                )
            compact_lines.append(
                "\t".join(
                    (
                        str(row["physical_event_order"]),
                        row["event_key"],
                        str(row["created_at"]),
                        row["role"],
                        row["event_type"],
                        row["runtime_actor_id"],
                        semantic,
                    )
                )
            )
        (compact_dir / f"{rows[0]['actor_label']}_{session_id}.tsv").write_text(
            "\n".join(compact_lines) + "\n", encoding="utf-8"
        )


def events_command() -> None:
    source_path = OUT_DIR / "source_list.csv"
    with source_path.open("r", encoding="utf-8", newline="") as handle:
        inventory_rows = list(csv.DictReader(handle))
    event_rows = build_event_rows(inventory_rows)
    write_csv(OUT_DIR / "event_ledger.csv", event_rows)
    write_traces(event_rows)
    print(
        json.dumps(
            {
                "physical_events": len(event_rows),
                "logical_events": sum(not row["duplicate_of_event_key"] for row in event_rows),
                "duplicate_physical_events": sum(
                    bool(row["duplicate_of_event_key"]) for row in event_rows
                ),
                "user_injections": collections.Counter(
                    row["event_type"] for row in event_rows if row["role"] == "user"
                ),
                "runtime_actor_ids": sorted({row["runtime_actor_id"] for row in event_rows}),
            },
            ensure_ascii=False,
            indent=2,
            default=dict,
        )
    )


def inventory_command() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_source_inventory()
    write_csv(OUT_DIR / "source_list.csv", rows)
    print(
        json.dumps(
            {
                "eligible_sessions": len({row["session_id"] for row in rows}),
                "raw_segments": len(rows),
                "archive_segments": sum(row["segment_label"] != "main" for row in rows),
                "messages": sum(row["message_count_actual"] for row in rows),
                "tool_calls": sum(row["tool_calls"] for row in rows),
                "parse_errors": sum(row["parse_status"] != "ok" for row in rows),
                "source_list": str(OUT_DIR / "source_list.csv"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("inventory", "events"))
    args = parser.parse_args()
    if args.command == "inventory":
        inventory_command()
    elif args.command == "events":
        events_command()


if __name__ == "__main__":
    main()
