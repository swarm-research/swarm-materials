#!/usr/bin/env python3
"""Dig for mechanisms in the swarm data. Read-only.

Five questions the earlier passes left open:
  1. Does citing others actually pay off, or do agents just believe it does?
  2. What is in the artifacts that get cited many times vs never?
  3. Do messages precede citations — is the board doing coordination work?
  4. Does an agent's model tier predict its standing?
  5. Where does a citation chain stop, and why does it stop there?
"""

import json
import re
import datetime
from collections import Counter, defaultdict
from pathlib import Path

GEN1 = Path("/Users/bytedance/Downloads/swarm")
GEN2 = Path("/Users/bytedance/Downloads/swarm-gen2")
KINDS = ["tools", "findings", "data", "challenges", "builds"]


def norm(a):
    m = re.match(r"agent-0*(\d+)$", str(a or "").strip())
    return f"agent-{int(m.group(1)):03d}" if m else None


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


def ts(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def colonies():
    out = [("gen1", GEN1)]
    for d in sorted(GEN2.iterdir()):
        if not d.name.startswith(".") and (d / "swarm").is_dir():
            out.append((f"gen2·{d.name}", d / "swarm"))
    return out


def load(root):
    cites = []
    for c in jsonl(root / "citations.jsonl"):
        f = str(c.get("file") or c.get("artifact") or "")
        if not f.startswith(("commons/", "agents/")):
            continue
        a, b = norm(c.get("citer")), norm(c.get("cited"))
        if a and b:
            cites.append({"citer": a, "cited": b, "file": f,
                          "t": ts(c.get("time")), "reason": c.get("reason", "")})
    msgs = []
    for m in jsonl(root / "board" / "messages.jsonl"):
        a = norm(m.get("from"))
        if a:
            msgs.append({"from": a, "to": m.get("to", ""),
                         "text": str(m.get("message", "")), "t": ts(m.get("time"))})
    outputs = defaultdict(Counter)
    sizes = {}
    for kind in KINDS:
        d = root / "commons" / kind
        if not d.is_dir():
            continue
        for f in d.iterdir():
            mm = re.match(r"(agent-\d+)_", f.name)
            a = norm(mm.group(1)) if mm else None
            if a:
                outputs[a][kind] += 1
                try:
                    sizes[f.name] = f.stat().st_size
                except OSError:
                    pass
    return cites, msgs, outputs, sizes


def corr(xs, ys):
    n = len(xs)
    if n < 4:
        return float("nan")
    mx, my = sum(xs)/n, sum(ys)/n
    cov = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    vx = sum((x-mx)**2 for x in xs) ** 0.5
    vy = sum((y-my)**2 for y in ys) ** 0.5
    return cov/(vx*vy) if vx and vy else float("nan")


def main():
    data = {n: load(r) for n, r in colonies()}

    # ── 1. 引用他人是否真的换来被引 ─────────────────────────────
    print("=" * 88)
    print("1. 互惠是不是真的：引用别人，别人会回引你吗")
    print("=" * 88)
    print(f"\n  {'群体':<16}{'出引~被引':>10}{'直接回引率':>11}{'延迟中位':>10}")
    print("  " + "-" * 48)
    for name, (cites, msgs, outputs, _) in data.items():
        if len(cites) < 60:
            continue
        give = Counter(c["citer"] for c in cites)
        recv = Counter(c["cited"] for c in cites)
        agents = set(give) | set(recv)
        r = corr([give.get(a, 0) for a in agents], [recv.get(a, 0) for a in agents])

        # Of all A→B edges, how many are answered by a later B→A?
        first = {}
        for c in sorted([c for c in cites if c["t"]], key=lambda c: c["t"]):
            first.setdefault((c["citer"], c["cited"]), c["t"])
        answered, lags = 0, []
        for (a, b), t0 in first.items():
            t1 = first.get((b, a))
            if t1 and t1 > t0:
                answered += 1
                lags.append((t1 - t0).total_seconds() / 60)
        rate = answered / max(len(first), 1) * 100
        med = sorted(lags)[len(lags)//2] if lags else float("nan")
        print(f"  {name:<16}{r:>10.2f}{rate:>10.1f}%{med:>9.0f}分")

    # ── 2. 被引 vs 零引的产出有什么不同 ─────────────────────────
    print("\n" + "=" * 88)
    print("2. 什么样的产出会被引用")
    print("=" * 88)
    tot_cited, tot_un = [], []
    kind_stat = defaultdict(lambda: [0, 0])
    for name, (cites, msgs, outputs, sizes) in data.items():
        fc = Counter(c["file"].split("/")[-1] for c in cites)
        for fn, sz in sizes.items():
            (tot_cited if fc.get(fn) else tot_un).append(sz)
            for k in KINDS:
                pass
    print(f"\n  被引产出 {len(tot_cited)} 个，中位 {sorted(tot_cited)[len(tot_cited)//2]/1024:.1f} KB"
          if tot_cited else "  无")
    print(f"  零引产出 {len(tot_un)} 个，中位 {sorted(tot_un)[len(tot_un)//2]/1024:.1f} KB"
          if tot_un else "")

    # 名字里的词与被引的关系
    print("\n  文件名关键词 vs 被引率（全体合并，出现≥25次的词）:")
    word_tot, word_cited = Counter(), Counter()
    for name, (cites, msgs, outputs, sizes) in data.items():
        fc = Counter(c["file"].split("/")[-1] for c in cites)
        for fn in sizes:
            body = re.sub(r"^agent-\d+_", "", fn)
            body = re.sub(r"_?\d{8}T?\d*Z?", "", body)
            for w in set(re.findall(r"[a-z]{4,}", body.lower())):
                word_tot[w] += 1
                if fc.get(fn):
                    word_cited[w] += 1
    rows = [(w, word_cited[w]/word_tot[w]*100, word_tot[w])
            for w in word_tot if word_tot[w] >= 25]
    rows.sort(key=lambda r: -r[1])
    for w, pct, n in rows[:8]:
        print(f"    {w:<18} {pct:5.1f}%  (n={n})")
    print("    …")
    for w, pct, n in rows[-5:]:
        print(f"    {w:<18} {pct:5.1f}%  (n={n})")

    # ── 3. 公告板是否在做协调 ──────────────────────────────────
    print("\n" + "=" * 88)
    print("3. 公告板有没有在做协调：发消息之后会更容易被引吗")
    print("=" * 88)
    print(f"\n  {'群体':<16}{'消息~被引':>10}{'公告后被引':>11}{'无公告被引':>11}")
    print("  " + "-" * 50)
    for name, (cites, msgs, outputs, _) in data.items():
        if len(cites) < 60 or not msgs:
            continue
        mcount = Counter(m["from"] for m in msgs)
        recv = Counter(c["cited"] for c in cites)
        agents = set(mcount) | set(recv)
        r = corr([mcount.get(a, 0) for a in agents], [recv.get(a, 0) for a in agents])
        announced = {m["from"] for m in msgs}
        with_ann = [recv.get(a, 0) for a in agents if a in announced]
        without = [recv.get(a, 0) for a in agents if a not in announced]
        wa = sum(with_ann)/len(with_ann) if with_ann else 0
        wo = sum(without)/len(without) if without else 0
        print(f"  {name:<16}{r:>10.2f}{wa:>11.1f}{wo:>11.1f}")

    # ── 4. 引用链能传多远 ─────────────────────────────────────
    print("\n" + "=" * 88)
    print("4. 累积深度：成果能被接力多少层")
    print("=" * 88)
    for name, (cites, msgs, outputs, _) in data.items():
        if len(cites) < 60:
            continue
        # builds/ artifacts are second-order work; are they themselves cited?
        built = {c["file"] for c in cites if "/builds/" in c["file"]}
        cited_files = Counter(c["file"] for c in cites)
        n_build_files = sum(1 for f in cited_files if "/builds/" in f)
        deep = sum(1 for f in built if cited_files[f] >= 2)
        print(f"  {name:<16} builds 被引 {n_build_files:4d} 个   其中被引≥2次 {deep:3d} 个")

    # ── 5. 谁在引用谁：同伴还是权威 ────────────────────────────
    print("\n" + "=" * 88)
    print("5. 引用方向：向上（引更强者）还是向下")
    print("=" * 88)
    print(f"\n  {'群体':<16}{'向上引%':>9}{'同层引%':>9}{'向下引%':>9}")
    print("  " + "-" * 44)
    for name, (cites, msgs, outputs, _) in data.items():
        if len(cites) < 60:
            continue
        recv = Counter(c["cited"] for c in cites)
        up = mid = down = 0
        for c in cites:
            a, b = recv.get(c["citer"], 0), recv.get(c["cited"], 0)
            if b > a * 1.5:
                up += 1
            elif a > b * 1.5:
                down += 1
            else:
                mid += 1
        t = up + mid + down
        print(f"  {name:<16}{up/t*100:>8.1f}%{mid/t*100:>8.1f}%{down/t*100:>8.1f}%")


if __name__ == "__main__":
    main()
