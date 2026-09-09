#!/usr/bin/env python3
"""Deep analysis of the swarm run, second pass.

Fixes two problems with the first pass: 15.7% of citation records point at
placeholder paths (test/path.py) left behind while agents were learning the
citation tool, and a fixed 70%-in-one-category rule is too blunt to detect
specialisation when the categories themselves are unevenly sized.

Specialisation is measured here as divergence from the population's own output
mix, so an agent only counts as specialised if it differs from what everybody
else was doing.
"""

import json
import math
import re
import datetime
from collections import Counter, defaultdict
from pathlib import Path

SWARM = Path("/Users/bytedance/Downloads/swarm")
KINDS = ["tools", "findings", "data", "challenges", "builds"]
SEEDS = {"agent-005", "agent-017", "agent-029"}
ADVERSARIES = {"agent-042": "Saboteur", "agent-051": "Parasite",
               "agent-059": "Infiltrator", "agent-067": "Escapist",
               "agent-074": "Provocateur", "agent-083": "Nihilist"}


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
    # Some records carry a timezone and some do not; drop it so they compare.
    try:
        d = datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d.replace(tzinfo=None)
    except Exception:
        return None


def gini(xs):
    xs = sorted(xs); n = len(xs); s = sum(xs)
    if not n or not s:
        return 0.0
    return (2 * sum((i + 1) * x for i, x in enumerate(xs))) / (n * s) - (n + 1) / n


def entropy(counts):
    tot = sum(counts)
    if tot <= 0:
        return 0.0
    return -sum((c / tot) * math.log2(c / tot) for c in counts if c > 0)


def main():
    raw_cites = list(jsonl(SWARM / "citations.jsonl"))
    msgs = list(jsonl(SWARM / "board" / "messages.jsonl"))

    # Placeholder paths were never real artifacts; counting them inflates the
    # survival score of whoever was testing the tool at the time.
    cites, junk = [], []
    for c in raw_cites:
        f = str(c.get("file", ""))
        (cites if f.startswith(("commons/", "agents/")) else junk).append(c)

    outputs = defaultdict(Counter)
    files_by_agent = defaultdict(list)
    for kind in KINDS:
        d = SWARM / "commons" / kind
        if not d.exists():
            continue
        for f in d.iterdir():
            m = re.match(r"(agent-\d+)_", f.name)
            a = norm(m.group(1)) if m else None
            if a:
                outputs[a][kind] += 1
                files_by_agent[a].append((kind, f.name, f.stat().st_size))

    recv = Counter(); give = Counter(); citers_of = defaultdict(set)
    for c in cites:
        a, b = norm(c.get("citer")), norm(c.get("cited"))
        if a and b:
            give[a] += 1; recv[b] += 1; citers_of[b].add(a)

    actors = set(outputs) | set(give) | set(recv)
    actors = {a for a in actors if a}

    print("=" * 74)
    print("SWARM 深度分析（已剔除占位引用）")
    print("=" * 74)
    print(f"\nagent {len(actors)}   产出 {sum(sum(v.values()) for v in outputs.values()):,}   "
          f"有效引用 {len(cites):,}   占位引用 {len(junk):,} ({len(junk)/len(raw_cites)*100:.1f}%)")
    print(f"消息 {len(msgs):,}")

    # ---------- 1. 分工 ----------
    print("\n" + "─" * 74)
    print("1. 分工：产出结构是否偏离群体基线")
    print("─" * 74)
    glob = Counter()
    for v in outputs.values():
        glob.update(v)
    tot = sum(glob.values())
    print("  群体基线: " + "  ".join(f"{k} {glob[k]/tot*100:.0f}%" for k in KINDS if glob[k]))
    max_ent = math.log2(len([k for k in KINDS if glob[k]]))

    rows = []
    for a, c in outputs.items():
        n = sum(c.values())
        if n < 5:
            continue
        # KL divergence from the population mix: how unusual is this agent's blend
        kl = sum((c[k]/n) * math.log2((c[k]/n) / (glob[k]/tot))
                 for k in KINDS if c[k] and glob[k])
        rows.append((a, n, entropy([c[k] for k in KINDS]), kl, c))

    rows.sort(key=lambda r: -r[3])
    print(f"\n  产出≥5 的 agent: {len(rows)}   平均熵 "
          f"{sum(r[2] for r in rows)/max(len(rows),1):.2f} / 上限 {max_ent:.2f}")
    strong = [r for r in rows if r[3] >= 0.3]
    print(f"  明显偏离基线 (KL≥0.3): {len(strong)} 个 ({len(strong)/max(len(rows),1)*100:.0f}%)")
    print(f"\n  {'agent':<12}{'产出':>5}{'熵':>6}{'KL':>7}   构成")
    for a, n, ent, kl, c in rows[:12]:
        mix = " ".join(f"{k[:4]}{c[k]}" for k in KINDS if c[k])
        tag = " [种子]" if a in SEEDS else (f" ★{ADVERSARIES[a]}" if a in ADVERSARIES else "")
        print(f"  {a:<12}{n:>5}{ent:>6.2f}{kl:>7.2f}   {mix}{tag}")

    # ---------- 2. 引用网络 ----------
    print("\n" + "─" * 74)
    print("2. 引用网络")
    print("─" * 74)
    vals = [recv.get(a, 0) for a in actors]
    print(f"  被引 Gini {gini(vals):.3f}   出引 Gini {gini([give.get(a,0) for a in actors]):.3f}")
    print(f"  零被引 {sum(1 for v in vals if v==0)} / {len(actors)}")

    pairs = Counter()
    for c in cites:
        a, b = norm(c.get("citer")), norm(c.get("cited"))
        if a and b:
            pairs[(a, b)] += 1
    mutual = sum(1 for (x, y) in pairs if x != y and (y, x) in pairs)
    print(f"  有向边 {len(pairs)}   互引 {mutual} ({mutual/max(len(pairs),1)*100:.1f}%)")

    print(f"\n  {'agent':<12}{'被引':>5}{'引用者':>7}{'产出':>5}  每产出被引")
    for a, n in recv.most_common(10):
        o = sum(outputs.get(a, Counter()).values())
        tag = " [种子]" if a in SEEDS else ""
        print(f"  {a:<12}{n:>5}{len(citers_of[a]):>7}{o:>5}  {n/max(o,1):>6.2f}{tag}")

    # ---------- 3. 引用是否跟随质量 ----------
    print("\n" + "─" * 74)
    print("3. 引用依据：文件大小 vs 被引次数")
    print("─" * 74)
    fc = Counter(str(c.get("file", "")).split("/")[-1] for c in cites)
    sized = []
    for a, lst in files_by_agent.items():
        for kind, name, size in lst:
            sized.append((fc.get(name, 0), size, kind))
    if sized:
        cited_f = [s for s in sized if s[0] > 0]
        un = [s for s in sized if s[0] == 0]
        print(f"  被引文件 {len(cited_f)} 个，平均 {sum(s[1] for s in cited_f)/max(len(cited_f),1)/1024:.1f} KB")
        print(f"  零引文件 {len(un)} 个，平均 {sum(s[1] for s in un)/max(len(un),1)/1024:.1f} KB")
        by_kind = defaultdict(lambda: [0, 0])
        for n, _, k in sized:
            by_kind[k][0] += 1
            by_kind[k][1] += (n > 0)
        print("\n  各类产出的被引率:")
        for k in KINDS:
            t, c_ = by_kind.get(k, [0, 0])
            if t:
                print(f"    {k:11s} {c_:4d}/{t:4d} = {c_/t*100:4.1f}%")

    # ---------- 4. 时间演化 ----------
    print("\n" + "─" * 74)
    print("4. 时间演化：结构是随时间加强还是消散")
    print("─" * 74)
    dated = sorted(((ts(c.get("time")), c) for c in cites if ts(c.get("time"))),
                   key=lambda p: p[0])
    if dated:
        t0 = dated[0][0]
        span = (dated[-1][0] - t0).total_seconds() / 3600
        nb = 6
        print(f"  跨度 {span:.1f} 小时，分 {nb} 段\n")
        print(f"  {'时段':<6}{'引用':>6}{'活跃者':>7}{'Gini':>7}{'互引率':>8}")
        for i in range(nb):
            lo, hi = t0 + datetime.timedelta(hours=span*i/nb), t0 + datetime.timedelta(hours=span*(i+1)/nb)
            seg = [c for t, c in dated if lo <= t < hi]
            if not seg:
                continue
            r = Counter(); p = Counter()
            for c in seg:
                x, y = norm(c.get("citer")), norm(c.get("cited"))
                if x and y:
                    r[y] += 1; p[(x, y)] += 1
            mu = sum(1 for (x, y) in p if x != y and (y, x) in p)
            act = len({norm(c.get("citer")) for c in seg} | {norm(c.get("cited")) for c in seg})
            print(f"  {i+1:<6}{len(seg):>6}{act:>7}{gini(list(r.values())):>7.3f}"
                  f"{mu/max(len(p),1)*100:>7.1f}%")

    # ---------- 5. 种子与卧底 ----------
    print("\n" + "─" * 74)
    print("5. 种子 agent 与卧底 agent")
    print("─" * 74)
    others = [a for a in actors if a not in SEEDS and a not in ADVERSARIES]
    f = lambda g, c: sum(c.get(a, 0) for a in g) / max(len(g), 1)
    sd = [a for a in SEEDS if a in actors]
    print(f"  种子 {len(sd)} 个 : 出引 {f(sd,give):6.1f}  被引 {f(sd,recv):6.1f}  "
          f"产出 {sum(sum(outputs.get(a,Counter()).values()) for a in sd)/max(len(sd),1):5.1f}")
    print(f"  其余 {len(others)} 个: 出引 {f(others,give):6.1f}  被引 {f(others,recv):6.1f}  "
          f"产出 {sum(sum(outputs.get(a,Counter()).values()) for a in others)/max(len(others),1):5.1f}")
    live = [(a, t) for a, t in ADVERSARIES.items() if a in actors]
    print(f"\n  留下痕迹的卧底 {len(live)} / {len(ADVERSARIES)}：")
    for a, t in live:
        print(f"    {a} {t}: 被引 {recv.get(a,0)}  出引 {give.get(a,0)}  "
              f"产出 {sum(outputs.get(a,Counter()).values())}")

    # ---------- 6. 占位引用的影响 ----------
    print("\n" + "─" * 74)
    print("6. 占位引用对生存计分的影响")
    print("─" * 74)
    jr = Counter()
    for c in junk:
        b = norm(c.get("cited"))
        if b:
            jr[b] += 1
    print(f"  占位引用 {len(junk)} 条，涉及被引方 {len(jr)} 个")
    print(f"\n  {'agent':<12}{'占位被引':>9}{'有效被引':>9}  占比")
    for a, n in jr.most_common(8):
        real = recv.get(a, 0)
        print(f"  {a:<12}{n:>9}{real:>9}  {n/max(n+real,1)*100:>5.1f}%")
    only_junk = [a for a in jr if recv.get(a, 0) == 0]
    if only_junk:
        print(f"\n  ⚠ 仅靠占位引用获得存活分的 agent: {', '.join(only_junk)}")


if __name__ == "__main__":
    main()
