#!/usr/bin/env python3
"""Recount gen-2 after separating out the gen-1 material that was seeded into it.

When gen 2 was deployed, gen 1's commons was rsynced onto each devbox so the new
agents could read what came before. That was deliberate, but the earlier
cross-generation numbers counted those inherited files as gen-2 output, which
inflated everything. Agent ids <= 36 are gen 1; anything above is gen 2.

Citations need the same treatment on 122174, which also received gen 1's
citations.jsonl — those records are dated 08-01, before gen 2 existed.
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

GEN1 = Path("/Users/bytedance/Downloads/swarm")
GEN2 = Path("/Users/bytedance/Downloads/swarm-gen2")
KINDS = ["tools", "findings", "data", "challenges", "builds"]
GEN2_CUTOFF = 36


def agent_num(name):
    m = re.match(r"agent-0*(\d+)", str(name or ""))
    return int(m.group(1)) if m else None


def jsonl(p):
    if not p.exists():
        return
    for ln in p.read_text(errors="ignore").splitlines():
        ln = ln.strip()
        if ln:
            try:
                yield json.loads(ln)
            except json.JSONDecodeError:
                pass


def colony(root, native_only):
    """native_only=True keeps just the agents that belong to this generation."""
    out = Counter()
    for kind in KINDS:
        d = root / "commons" / kind
        if not d.is_dir():
            continue
        for f in d.iterdir():
            n = agent_num(f.name)
            if n is None:
                continue
            if native_only and n <= GEN2_CUTOFF:
                continue
            out[kind] += 1

    cites, junk, inherited = [], 0, 0
    for c in jsonl(root / "citations.jsonl"):
        path = str(c.get("file") or c.get("artifact") or "")
        if not path.startswith(("commons/", "agents/")):
            junk += 1
            continue
        a, b = agent_num(c.get("citer")), agent_num(c.get("cited"))
        if a is None or b is None:
            continue
        if native_only and a <= GEN2_CUTOFF:
            inherited += 1          # citer predates gen 2 → carried over
            continue
        cites.append((a, b))

    msgs = 0
    for m in jsonl(root / "board" / "messages.jsonl"):
        n = agent_num(m.get("from"))
        if n is None:
            continue
        if native_only and n <= GEN2_CUTOFF:
            continue
        msgs += 1
    return out, cites, junk, inherited, msgs


def gini(xs):
    xs = sorted(xs); n = len(xs); s = sum(xs)
    if not n or not s:
        return 0.0
    return (2 * sum((i + 1) * x for i, x in enumerate(xs))) / (n * s) - (n + 1) / n


def main():
    rows = []
    o, c, j, inh, m = colony(GEN1, native_only=False)
    rows.append(("gen1", o, c, j, inh, m))

    for d in sorted(GEN2.iterdir()):
        if d.name.startswith(".") or not (d / "swarm").is_dir():
            continue
        o, c, j, inh, m = colony(d / "swarm", native_only=True)
        rows.append((f"gen2·{d.name}", o, c, j, inh, m))

    print("=" * 88)
    print("剔除继承数据后的重算")
    print("=" * 88)
    print(f"\n{'群体':<16}{'本代产出':>9}{'本代引用':>9}{'本代消息':>9}"
          f"{'占位引用':>9}{'继承引用':>9}{'Gini':>8}{'互引%':>8}")
    print("-" * 88)

    g2o = g2c = g2m = 0
    for name, o, c, j, inh, m in rows:
        tot = sum(o.values())
        recv = Counter(b for _, b in c)
        pairs = set(c)
        mutual = sum(1 for (x, y) in pairs if x != y and (y, x) in pairs)
        mp = mutual / max(len(pairs), 1) * 100
        print(f"{name:<16}{tot:>9}{len(c):>9}{m:>9}{j:>9}{inh:>9}"
              f"{gini(list(recv.values())):>8.3f}{mp:>7.1f}%")
        if name.startswith("gen2"):
            g2o += tot; g2c += len(c); g2m += m

    g1o = sum(rows[0][1].values()); g1c = len(rows[0][2]); g1m = rows[0][5]
    print("-" * 88)
    print(f"{'二代合计':<16}{g2o:>9}{g2c:>9}{g2m:>9}")
    print(f"{'一代':<16}{g1o:>9}{g1c:>9}{g1m:>9}")
    print(f"{'规模比':<16}{g2o/max(g1o,1):>8.1f}×{g2c/max(g1c,1):>8.1f}×{g2m/max(g1m,1):>8.1f}×")

    print("\n" + "─" * 88)
    print("与此前发布数字的差异")
    print("─" * 88)
    print(f"  {'指标':<14}{'此前':>10}{'修正后':>10}{'虚高':>10}")
    for label, before, after in [("二代产出", 8262, g2o),
                                 ("二代引用", 4305, g2c),
                                 ("二代消息", 7701, g2m)]:
        print(f"  {label:<14}{before:>10}{after:>10}{(before/max(after,1)-1)*100:>9.0f}%")

    print("\n有效群体数：", sum(1 for r in rows[1:] if len(r[2]) >= 60),
          "（122447 因 Python 版本导致 import 失败，零产出零引用）")


if __name__ == "__main__":
    main()
