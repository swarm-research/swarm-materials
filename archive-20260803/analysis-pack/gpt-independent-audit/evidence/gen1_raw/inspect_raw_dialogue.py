#!/usr/bin/env python3
"""Small read-only CLI for qualitative inspection of raw swarm transcripts."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


TRANSCRIPTS = Path("/Users/bytedance/Downloads/swarm-archive-20260803/02_transcripts")


def text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(text(x.get("text") or x.get("content") or x) if isinstance(x, dict) else text(x) for x in value)
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def utc(value: Any) -> str:
    if not value:
        return ""
    return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat().replace("+00:00", "Z")


def experiment_sids() -> Iterator[str]:
    for path in sorted(TRANSCRIPTS.glob("*.meta.json")):
        meta = json.loads(path.read_text())
        if meta.get("working_dir") == "/Users/bytedance/Downloads/swarm":
            yield meta["session_id"]


def show_session(sid: str, start: int, end: int, width: int, roles: set[str]) -> None:
    doc = json.loads((TRANSCRIPTS / f"{sid}.json").read_text())
    meta = doc.get("metadata", {})
    print(f"SESSION {sid} | {meta.get('name')} | {meta.get('model')} | {len(doc.get('messages', []))} messages")
    messages = doc.get("messages", [])
    if end < 0:
        end = len(messages)
    for idx in range(max(start, 0), min(end, len(messages))):
        message = messages[idx]
        role = str(message.get("role") or "")
        if roles and role not in roles:
            continue
        body = text(message.get("content")).replace("\r", "")
        if width and len(body) > width:
            body = body[:width] + " …"
        print(f"\n[{idx}] {role} {utc(message.get('created_at'))} id={message.get('id','')}\n{body}")


def search(pattern: str, width: int, roles: set[str], limit: int, only_session: str = "") -> None:
    rx = re.compile(pattern, flags=re.I | re.S)
    hits = 0
    session_ids = [only_session] if only_session else experiment_sids()
    for sid in session_ids:
        doc = json.loads((TRANSCRIPTS / f"{sid}.json").read_text())
        meta = doc.get("metadata", {})
        for idx, message in enumerate(doc.get("messages", [])):
            role = str(message.get("role") or "")
            if roles and role not in roles:
                continue
            body = text(message.get("content")).replace("\r", "")
            match = rx.search(body)
            if not match:
                continue
            lo = max(0, match.start() - width // 3)
            hi = min(len(body), match.end() + 2 * width // 3)
            excerpt = body[lo:hi].replace("\n", " ")
            print(f"{sid}\t{meta.get('name','')}\t{idx}\t{role}\t{utc(message.get('created_at'))}\t{excerpt}")
            hits += 1
            if hits >= limit:
                return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p_show = sub.add_parser("show")
    p_show.add_argument("session_id")
    p_show.add_argument("--start", type=int, default=0)
    p_show.add_argument("--end", type=int, default=-1)
    p_show.add_argument("--width", type=int, default=1200)
    p_show.add_argument("--roles", default="assistant,user")
    p_search = sub.add_parser("search")
    p_search.add_argument("pattern")
    p_search.add_argument("--width", type=int, default=700)
    p_search.add_argument("--roles", default="assistant")
    p_search.add_argument("--limit", type=int, default=100)
    p_search.add_argument("--session", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    roles = {x.strip() for x in args.roles.split(",") if x.strip()}
    if args.command == "show":
        show_session(args.session_id, args.start, args.end, args.width, roles)
    else:
        search(args.pattern, args.width, roles, args.limit, args.session)


if __name__ == "__main__":
    main()
