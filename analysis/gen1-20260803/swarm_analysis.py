#!/usr/bin/env python3
"""Integrated analysis of both swarm generations.

Gen 1 = 36 agents on MASO (agent-001..036), Gen 2 = the devbox scale-up
(agent-037+). They share one commons, one citation log and one message board,
so the two waves are separated by agent id rather than by file.

The questions this answers, in order: did the population differentiate into
roles, did a citation hierarchy form, did the seeded cooperators change
anything, and did the covert adversaries leave a detectable trace.
"""

import json
import re
import datetime
from collections import Counter, defaultdict
from pathlib import Path

SWARM = Path("/Users/bytedance/Downloads/swarm")

GEN1 = set(f"agent-{i:03d}" for i in range(1, 37))
SEEDS_G1 = {"agent-005", "agent-017", "agent-029"}
SEEDS_G2 = {f"agent-{i:03d}" for i in (38, 45, 52, 60, 69, 76, 85, 92, 99)}
ADVERSARIES = {
    "agent-042": "Saboteur", "agent-051": "Parasite", "agent-059": "Infiltrator",
    "agent-067": "Escapist", "agent-074": "Provocateur", "agent-083": "Nihilist",
    "agent-0150": "Gaslighter", "agent-0280": "Monopolist",
    "agent-0420": "Accelerationist", "agent-0560": "Double Agent",
    "agent-0700": "Entropy Agent", "agent-0850": "Cult Leader",
}


def norm(aid):
    """agent-42 / agent-042 / agent-0042 all denote the same agent."""
    m = re.match(r"agent-0*(\d+)$", str(aid or "").strip())
    return f"agent-{int(m.group(1)):03d}" if m else str(aid or "").strip()


def gen_of(aid):
    m = re.match(r"agent-(\d+)$", aid)
    if not m:
        return "?"
    return "gen1" if int(m.group(1)) <= 36 else "gen2"


def jsonl(path):
    if not path.exists():
        return
    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if line:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def gini(xs):
    xs = sorted(xs)
    n = len(xs)
    if n == 0 or sum(xs) == 0:
        return 0.0
    cum = sum((i + 1) * x for i, x in enumerate(xs))
    return (2 * cum) / (n * sum(xs)) - (n + 1) / n


def main():
    # ---- load ----
    cites = [c for c in jsonl(SWARM / "citations.jsonl")]
    msgs = [m for m in jsonl(SWARM / "board" / "messages.jsonl")]

    outputs = defaultdict(list)   # agent -> [(kind, filename)]
    for kind in ("tools", "findings", "data", "challenges", "builds"):
        d = SWARM / "commons" / kind
        if not d.exists():
            continue
        for f in d.iterdir():
            m = re.match(r"(agent-\d+)_", f.name)
            if m:
                outputs[norm(m.group(1))].append((kind, f.name))

    actors = set(outputs) | {norm(c.get("citer")) for c in cites} | \
             {norm(c.get("cited")) for c in cites} | {norm(m.get("from")) for m in msgs}
    actors = {a for a in actors if re.match(r"agent-\d+$", a)}

    print("=" * 76)
    print("SWARM 整合分析 — 一代 (agent-001..036) + 二代 (agent-037+)")
    print("=" * 76)

    g1 = {a for a in actors if gen_of(a) == "gen1"}
    g2 = {a for a in actors if gen_of(a) == "gen2"}
    print(f"\n活跃 agent 总数 {len(actors)}   一代 {len(g1)}   二代 {len(g2)}")
    print(f"产出 {sum(len(v) for v in outputs.values()):,}   "
          f"引用 {len(cites):,}   消息 {len(msgs):,}")

    # ---- 1. 产出与分工 ----
    print("\n" + "-" * 76)
    print("1. 分工：每个 agent 的产出是否集中到某一类")
    print("-" * 76)

    KINDS = ["tools", "findings", "data", "challenges", "builds"]
    kind_tot = Counter(k for v in outputs.values() for k, _ in v)
    print("  全局构成: " + "  ".join(f"{k} {kind_tot.get(k,0)}" for k in KINDS))

    specialists = defaultdict(list)
    for a, items in outputs.items():
        if len(items) < 3:
            continue
        c = Counter(k for k, _ in items)
        top, n = c.most_common(1)[0]
        share = n / len(items)
        if share >= 0.7:                       # ≥70% in one category = specialist
            specialists[top].append((a, len(items), share))

    n_multi = sum(1 for v in outputs.values() if len(v) >= 3)
    n_spec = sum(len(v) for v in specialists.values())
    print(f"\n  产出≥3 的 agent: {n_multi}   其中专精(单类≥70%): {n_spec} "
          f"({n_spec/max(n_multi,1)*100:.0f}%)")
    for kind in KINDS:
        lst = sorted(specialists.get(kind, []), key=lambda t: -t[1])
        if lst:
            names = ", ".join(f"{a}({n})" for a, n, _ in lst[:6])
            print(f"    {kind:11s} {len(lst):3d} 个: {names}")

    # ---- 2. 引用网络 ----
    print("\n" + "-" * 76)
    print("2. 引用网络：地位分化程度")
    print("-" * 76)

    recv = Counter(norm(c["cited"]) for c in cites if c.get("cited"))
    give = Counter(norm(c["citer"]) for c in cites if c.get("citer"))
    distinct_citers = defaultdict(set)
    for c in cites:
        if c.get("cited") and c.get("citer"):
            distinct_citers[norm(c["cited"])].add(norm(c["citer"]))

    vals = [recv.get(a, 0) for a in actors]
    print(f"  被引 Gini {gini(vals):.3f}   出引 Gini {gini([give.get(a,0) for a in actors]):.3f}")
    print(f"  从未被引用: {sum(1 for v in vals if v == 0)} / {len(actors)}")

    print("\n  被引 Top 12:")
    for a, n in recv.most_common(12):
        tag = ""
        if a in ADVERSARIES: tag = f" ★{ADVERSARIES[a]}"
        elif a in SEEDS_G1 | SEEDS_G2: tag = " [种子]"
        print(f"    {a:12s} {n:4d}次  {len(distinct_citers[a]):3d}个不同引用者  "
              f"产出{len(outputs.get(a,[])):3d}{tag}")

    # 互惠性
    pairs = Counter((norm(c["citer"]), norm(c["cited"])) for c in cites
                    if c.get("citer") and c.get("cited"))
    mutual = sum(1 for (x, y) in pairs if x != y and (y, x) in pairs)
    print(f"\n  有向边 {len(pairs)}   互引边 {mutual} ({mutual/max(len(pairs),1)*100:.1f}%)")
    self_c = sum(n for (x, y), n in pairs.items() if x == y)
    print(f"  自引 {self_c} 次 ({self_c/max(len(cites),1)*100:.1f}%)")

    # ---- 3. 种子效应 ----
    print("\n" + "-" * 76)
    print("3. 种子 agent（被私下要求多引用他人）是否改变了网络")
    print("-" * 76)
    for label, seeds, pool in [("一代", SEEDS_G1, g1), ("二代", SEEDS_G2, g2)]:
        s = [a for a in seeds if a in actors]
        o = [a for a in pool if a not in seeds]
        if not s or not o:
            continue
        f = lambda g, c: sum(c.get(a, 0) for a in g) / max(len(g), 1)
        print(f"  {label}  种子{len(s)}个: 出引 {f(s,give):5.1f}  被引 {f(s,recv):5.1f}  "
              f"产出 {sum(len(outputs.get(a,[])) for a in s)/max(len(s),1):5.1f}")
        print(f"       其余{len(o)}个: 出引 {f(o,give):5.1f}  被引 {f(o,recv):5.1f}  "
              f"产出 {sum(len(outputs.get(a,[])) for a in o)/max(len(o),1):5.1f}")

    # ---- 4. 对抗 agent ----
    print("\n" + "-" * 76)
    print("4. 卧底 agent 的实际表现")
    print("-" * 76)
    live = [(a, t) for a, t in ADVERSARIES.items() if a in actors]
    if not live:
        print("  没有卧底 agent 留下痕迹（二代未真正跑起来）")
    else:
        base_recv = sum(recv.get(a, 0) for a in actors if a not in ADVERSARIES) / \
                    max(len(actors) - len(live), 1)
        print(f"  普通 agent 平均被引 {base_recv:.1f}\n")
        for a, t in sorted(live, key=lambda x: -recv.get(x[0], 0)):
            print(f"    {a:12s} {t:14s} 被引{recv.get(a,0):4d}  出引{give.get(a,0):4d}  "
                  f"产出{len(outputs.get(a,[])):3d}  "
                  f"消息{sum(1 for m in msgs if norm(m.get('from'))==a):3d}")

    # ---- 5. 时间演化 ----
    print("\n" + "-" * 76)
    print("5. 时间演化")
    print("-" * 76)
    def hour(ts):
        try:
            return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%m-%d %H")
        except Exception:
            return None
    ch = Counter(h for h in (hour(c.get("time", "")) for c in cites) if h)
    mh = Counter(h for h in (hour(m.get("time", "")) for m in msgs) if h)
    print(f"  {'时刻':<10} {'引用':>6} {'消息':>6}")
    for h in sorted(set(ch) | set(mh)):
        print(f"  {h:<10} {ch.get(h,0):6d} {mh.get(h,0):6d}")

    # ---- 6. 消息内容 ----
    print("\n" + "-" * 76)
    print("6. 消息板：交流的性质")
    print("-" * 76)
    to_all = sum(1 for m in msgs if str(m.get("to", "")).lower() == "all")
    print(f"  广播 {to_all} ({to_all/max(len(msgs),1)*100:.0f}%)   "
          f"定向 {len(msgs)-to_all}")
    themes = {
        "协作提议": ["协作", "一起", "合作", "collaborat", "joint"],
        "求助": ["请问", "help", "怎么", "如何", "?"],
        "宣告产出": ["我在", "已发布", "放在 commons", "我写了", "已提交"],
        "治理/规则": ["规则", "规范", "治理", "投票", "淘汰", "reaper", "protocol"],
        "质疑/纠错": ["有问题", "错误", "bug", "不对", "存疑", "怀疑"],
        "元认知": ["我们是", "被观察", "实验", "sandbox", "沙箱", "为什么存在"],
    }
    for name, kws in themes.items():
        n = sum(1 for m in msgs
                if any(k in str(m.get("message", "")).lower() for k in kws))
        print(f"    {name:10s} {n:5d} ({n/max(len(msgs),1)*100:4.1f}%)")

    # ---- 7. 二次创作 ----
    print("\n" + "-" * 76)
    print("7. 累积性：是否在他人成果上继续建造")
    print("-" * 76)
    builds = outputs and [f for v in outputs.values() for k, f in v if k == "builds"]
    cited_files = Counter(c.get("file", "") for c in cites if c.get("file"))
    print(f"  builds/ 产出 {len(builds or [])} 个")
    print(f"  被引用过的文件 {len(cited_files)} 个 / 总产出 {sum(len(v) for v in outputs.values())}")
    print(f"  最多被引的文件:")
    for f, n in cited_files.most_common(5):
        print(f"    {n:3d}次  {f[:66]}")

    out = SWARM / "analysis_summary.json"
    out.write_text(json.dumps({
        "actors": len(actors), "gen1": len(g1), "gen2": len(g2),
        "outputs": sum(len(v) for v in outputs.values()),
        "citations": len(cites), "messages": len(msgs),
        "gini_received": round(gini(vals), 4),
        "specialist_ratio": round(n_spec / max(n_multi, 1), 4),
        "mutual_edge_ratio": round(mutual / max(len(pairs), 1), 4),
        "top_cited": recv.most_common(20),
    }, ensure_ascii=False, indent=2))
    print(f"\n结构化结果已存 {out}")


if __name__ == "__main__":
    main()
