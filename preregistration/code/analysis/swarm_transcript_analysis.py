#!/usr/bin/env python3
"""Mine the agents' own reasoning out of the MASO transcripts.

The workspace only preserves what agents produced. Why they cited someone, how
they chose what to work on, whether they noticed the survival rule or each
other — that exists only in the conversation logs, and it is the part of this
run that cannot be regenerated.
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

SESS = Path.home() / ".maso" / "sessions"
OUT = Path("/Users/bytedance/Downloads/swarm_transcripts")


def text_of(msg) -> str:
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(p.get("text", "") for p in c if isinstance(p, dict))
    return ""


def tool_names(msg):
    for tc in msg.get("tool_calls") or []:
        fn = (tc or {}).get("function") or {}
        if fn.get("name"):
            yield fn["name"]


# What the agents were thinking about, judged from their own assistant turns.
THEMES = {
    "生存意识":   ["淘汰", "reaper", "存活", "被引用才能", "survive", "死亡", "清理掉"],
    "策略性引用": ["互相引用", "引用回", "reciproc", "回引", "为了被引", "citation 换"],
    "识别他人":   ["agent-0", "其他 agent", "别的 agent", "同伴"],
    "分工意识":   ["专注于", "我的定位", "分工", "niche", "专精", "差异化"],
    "元认知":     ["这个实验", "被观察", "sandbox", "沙箱", "我们是 agent", "系统提示"],
    "怀疑他人":   ["有问题", "不可靠", "错误的", "存疑", "bug", "验证一下"],
    "治理提议":   ["规则", "约定", "协议", "protocol", "标准", "规范"],
}


def main():
    OUT.mkdir(exist_ok=True)
    rows = []
    theme_hits = Counter()
    theme_examples = defaultdict(list)
    tool_use = Counter()
    first_moves = []

    for meta_f in SESS.glob("*.meta.json"):
        try:
            meta = json.loads(meta_f.read_text())
        except Exception:
            continue
        if "/swarm" not in (meta.get("working_dir") or ""):
            continue
        body_f = meta_f.with_name(meta_f.name.replace(".meta.json", ".json"))
        if not body_f.exists():
            continue
        try:
            body = json.loads(body_f.read_text())
        except Exception:
            continue

        msgs = body.get("messages") or []
        sysb = "".join(str(b.get("content", ""))
                       for b in (body.get("metadata") or {}).get("system_block") or [])
        m = re.search(r"(agent-\d+)", sysb)
        aid = m.group(1) if m else meta.get("session_id", "?")

        assistant = [x for x in msgs if x.get("role") == "assistant"]
        prose = []
        for x in assistant:
            t = text_of(x).strip()
            if t:
                prose.append(t)
            for n in tool_names(x):
                tool_use[n] += 1

        joined = "\n".join(prose)
        for theme, kws in THEMES.items():
            hits = sum(joined.count(k) for k in kws)
            if hits:
                theme_hits[theme] += hits
                if len(theme_examples[theme]) < 4:
                    for k in kws:
                        i = joined.find(k)
                        if i >= 0:
                            theme_examples[theme].append(
                                (aid, joined[max(0, i-90):i+110].replace("\n", " ")))
                            break

        if prose:
            first_moves.append((aid, prose[0][:200].replace("\n", " ")))

        rows.append({
            "agent": aid,
            "session": meta.get("session_id"),
            "model": meta.get("model"),
            "turns": len(assistant),
            "prose_chars": len(joined),
        })

        # One readable file per session, for hand-reading later.
        safe = re.sub(r"[^\w.-]", "_", f"{aid}_{meta.get('session_id','')}")
        (OUT / f"{safe}.md").write_text(
            f"# {aid} · {meta.get('model')} · {len(assistant)} 轮\n\n"
            + "\n\n---\n\n".join(prose[:400]),
            errors="ignore")

    print("=" * 72)
    print("对话内容分析（swarm 会话）")
    print("=" * 72)
    print(f"\n会话 {len(rows)}   assistant 轮次 {sum(r['turns'] for r in rows):,}   "
          f"正文 {sum(r['prose_chars'] for r in rows)/1e6:.1f}M 字符")
    print(f"逐会话可读文本已导出到 {OUT}")

    print("\n【工具调用分布】")
    tot = sum(tool_use.values())
    for n, c in tool_use.most_common(10):
        print(f"  {n:24s} {c:6,} ({c/max(tot,1)*100:4.1f}%)")

    print("\n【agent 自己在想什么 — 关键词命中】")
    for theme, n in theme_hits.most_common():
        print(f"  {theme:10s} {n:6,} 次")

    print("\n【原文片段】")
    for theme in ["生存意识", "策略性引用", "分工意识", "元认知"]:
        ex = theme_examples.get(theme, [])
        if ex:
            print(f"\n  ── {theme} ──")
            for aid, snip in ex[:2]:
                print(f"    [{aid}] …{snip}…")

    print("\n【开局第一步】")
    for aid, s in first_moves[:6]:
        print(f"  [{aid}] {s[:110]}…")

    Path("/Users/bytedance/Downloads/swarm_transcript_rows.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
