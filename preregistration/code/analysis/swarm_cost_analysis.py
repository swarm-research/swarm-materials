#!/usr/bin/env python3
"""Attribute MASO spend across both swarm generations.

No token counts are stored per message, so volume is estimated from content
characters (~2.5 chars/token for mixed zh/en, ~3.5 for code-heavy text). The
absolute numbers are estimates; the *relative* split between models, roles and
generations is what the billing question actually turns on.

The expensive part of an agent run is not the messages it writes — it is that
every turn resends the whole conversation as input. A session with N turns
costs O(N^2) in input tokens unless the prefix is cached, so this script
reports cumulative resent input, not just content size.
"""

import json
import sys
import datetime
from collections import defaultdict
from pathlib import Path

SESS = Path.home() / ".maso" / "sessions"
CHARS_PER_TOKEN = 2.8


def content_chars(msg) -> int:
    c = msg.get("content")
    if isinstance(c, str):
        n = len(c)
    elif isinstance(c, list):
        n = sum(len(p.get("text", "")) for p in c if isinstance(p, dict))
    else:
        n = 0
    for tc in msg.get("tool_calls") or []:
        fn = (tc or {}).get("function") or {}
        n += len(str(fn.get("arguments", "")))
    extra = msg.get("extra")
    if isinstance(extra, dict):
        n += len(str(extra.get("content", "")))
    return n


def main():
    rows = []
    for meta_f in SESS.glob("*.meta.json"):
        try:
            meta = json.loads(meta_f.read_text())
        except Exception:
            continue
        body_f = meta_f.with_name(meta_f.name.replace(".meta.json", ".json"))
        if not body_f.exists():
            continue

        try:
            body = json.loads(body_f.read_text())
        except Exception:
            continue

        msgs = body.get("messages") or []
        sys_chars = sum(len(str(b.get("content", "")))
                        for b in (body.get("metadata") or {}).get("system_block") or [])

        # Walk the conversation, tracking what each turn resends as input.
        running = sys_chars
        resent = 0
        digests = set()
        out_chars = 0
        for m in msgs:
            c = content_chars(m)
            if m.get("role") == "assistant":
                resent += running          # this turn resent everything before it
                out_chars += c
                if m.get("prefix_digest"):
                    digests.add(m["prefix_digest"])
            running += c

        rows.append({
            "id": meta.get("session_id", body_f.stem),
            "model": meta.get("model", "?"),
            "dir": meta.get("working_dir", ""),
            "name": meta.get("name", ""),
            "created": meta.get("created_at", 0),
            "updated": meta.get("updated_at", 0),
            "msgs": len(msgs),
            "in_tok": resent / CHARS_PER_TOKEN,
            "out_tok": out_chars / CHARS_PER_TOKEN,
            "distinct_prefixes": len(digests),
            "assistant_turns": sum(1 for m in msgs if m.get("role") == "assistant"),
        })

    if not rows:
        print("no sessions found")
        return

    # Gen 2 = the scale-up push; it begins with the devbox wave on Aug 2.
    GEN2_CUTOFF = datetime.datetime(2026, 8, 2, 0, 0).timestamp()

    def gen_of(r):
        d = r["dir"] or ""
        if "/swarm" in d:
            # Two swarm waves: the 36-agent run, then the scale-up.
            return "swarm-gen1" if r["created"] < GEN2_CUTOFF else "swarm-gen2"
        return "other (papers etc.)"

    created = sorted(r["created"] for r in rows if r["created"])

    for r in rows:
        r["gen"] = gen_of(r)

    tot_in = sum(r["in_tok"] for r in rows)
    tot_out = sum(r["out_tok"] for r in rows)

    print("=" * 78)
    print(f"会话文件 {len(rows)}   估算输入 {tot_in/1e6:,.1f}M tok   输出 {tot_out/1e6:,.1f}M tok")
    print(f"输入/输出比 {tot_in/max(tot_out,1):,.1f} : 1")
    print("=" * 78)

    print("\n【按代次】")
    agg = defaultdict(lambda: {"n": 0, "in": 0.0, "out": 0.0, "msgs": 0})
    for r in rows:
        a = agg[r["gen"]]
        a["n"] += 1; a["in"] += r["in_tok"]; a["out"] += r["out_tok"]; a["msgs"] += r["msgs"]
    for g, a in sorted(agg.items(), key=lambda kv: -kv[1]["in"]):
        print(f"  {g:22s} {a['n']:5d}会话 {a['msgs']:7,}消息 "
              f"输入{a['in']/1e6:8,.1f}M ({a['in']/tot_in*100:5.1f}%) 输出{a['out']/1e6:6,.1f}M")

    print("\n【按模型 — 输入 token 占比即成本占比】")
    bym = defaultdict(lambda: {"n": 0, "in": 0.0, "out": 0.0})
    for r in rows:
        a = bym[r["model"]]
        a["n"] += 1; a["in"] += r["in_tok"]; a["out"] += r["out_tok"]
    for m, a in sorted(bym.items(), key=lambda kv: -kv[1]["in"])[:12]:
        print(f"  {m:34s} {a['n']:5d}会话 输入{a['in']/1e6:8,.1f}M ({a['in']/tot_in*100:5.1f}%) "
              f"输出{a['out']/1e6:6,.1f}M")

    print("\n【最贵的 15 个会话（按重发输入量）】")
    for r in sorted(rows, key=lambda r: -r["in_tok"])[:15]:
        print(f"  {r['in_tok']/1e6:6,.1f}M  {r['assistant_turns']:4d}轮  "
              f"{r['model'][:30]:30s} {r['gen'][:11]:11s} {r['name'][:24]}")

    print("\n【缓存复用】")
    multi = [r for r in rows if r["assistant_turns"] >= 5]
    if multi:
        reuse = sum(1 - r["distinct_prefixes"] / max(r["assistant_turns"], 1) for r in multi) / len(multi)
        print(f"  多轮会话 {len(multi)} 个，平均 prefix 复用率 {reuse*100:.1f}%")
        print(f"  （每轮都换 prefix = 0%，完全复用 = 100%）")

    print("\n【长会话的二次方代价】")
    buckets = [(0, 20), (20, 50), (50, 100), (100, 300), (300, 10000)]
    for lo, hi in buckets:
        sel = [r for r in rows if lo <= r["assistant_turns"] < hi]
        if not sel:
            continue
        s_in = sum(r["in_tok"] for r in sel)
        print(f"  {lo:4d}-{hi if hi<10000 else '∞':>5} 轮: {len(sel):5d}会话 "
              f"输入{s_in/1e6:8,.1f}M ({s_in/tot_in*100:5.1f}%)  "
              f"人均{s_in/len(sel)/1e6:5.2f}M")

    if created:
        t0 = datetime.datetime.fromtimestamp(min(created))
        t1 = datetime.datetime.fromtimestamp(max(r["updated"] for r in rows if r["updated"]))
        print(f"\n【时间】{t0:%m-%d %H:%M} → {t1:%m-%d %H:%M}  "
              f"({(t1-t0).total_seconds()/3600:.0f} 小时)")

    out = Path("/Users/bytedance/Downloads/swarm_cost_rows.json")
    out.write_text(json.dumps(rows, ensure_ascii=False))
    print(f"\n明细已存 {out}")


if __name__ == "__main__":
    main()
