#!/usr/bin/env python3
"""Why did five identical colonies end up with very different hierarchies?

Gen 2 ran the same rules five times over (the sync between devboxes never
worked, so each box is an independent replicate). Final inequality varies a
lot — Gini 0.40 to 0.75 — which is the signature of path dependence rather
than of the rules themselves.

This asks whether the eventual winner is already visible in the first handful
of citations, i.e. whether early luck locks in. Read-only.
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

GEN1 = Path("/Users/bytedance/Downloads/swarm")
GEN2 = Path("/Users/bytedance/Downloads/swarm-gen2")


def norm(a):
    m = re.match(r"agent-0*(\d+)$", str(a or "").strip())
    return f"agent-{int(m.group(1)):03d}" if m else None


def load_cites(root):
    p = root / "citations.jsonl"
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(errors="ignore").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            c = json.loads(ln)
        except json.JSONDecodeError:
            continue
        f = str(c.get("file") or c.get("artifact") or "")
        if not f.startswith(("commons/", "agents/")):
            continue
        a, b = norm(c.get("citer")), norm(c.get("cited"))
        if a and b:
            out.append((a, b, c.get("time") or ""))
    return out


def gini(xs):
    xs = sorted(xs); n = len(xs); s = sum(xs)
    if not n or not s:
        return 0.0
    return (2 * sum((i + 1) * x for i, x in enumerate(xs))) / (n * s) - (n + 1) / n


def analyse(name, cites, cohort_only=False):
    if len(cites) < 60:
        return None
    cites = sorted(cites, key=lambda t: t[2] or "")
    total = len(cites)
    early_n = max(10, total // 10)

    if cohort_only:
        # Agents join over time, so a newcomer cannot appear in the early
        # ranking no matter how good it is. Restrict to the agents already
        # present in the first window, otherwise "the leader changed" just
        # measures population growth.
        present = {b for _, b, _ in cites[:early_n]} | {a for a, _, _ in cites[:early_n]}
        cites = [(a, b, t) for a, b, t in cites if b in present]
        total = len(cites)
        if total < 40:
            return None
        early_n = max(10, total // 10)

    recv_final = Counter(b for _, b, _ in cites)
    top_final = [a for a, _ in recv_final.most_common(5)]

    recv_early = Counter(b for _, b, _ in cites[:early_n])
    top_early = [a for a, _ in recv_early.most_common(5)]

    overlap = len(set(top_early) & set(top_final))
    leader_held = (top_early[:1] == top_final[:1]) if top_early and top_final else False

    # Preferential attachment: at the midpoint, does prior standing predict
    # who receives the second half's citations?
    mid = total // 2
    before = Counter(b for _, b, _ in cites[:mid])
    after = Counter(b for _, b, _ in cites[mid:])
    agents = set(before) | set(after)
    if len(agents) >= 4:
        xs = [before.get(a, 0) for a in agents]
        ys = [after.get(a, 0) for a in agents]
        mx, my = sum(xs)/len(xs), sum(ys)/len(ys)
        cov = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
        vx = sum((x-mx)**2 for x in xs) ** 0.5
        vy = sum((y-my)**2 for y in ys) ** 0.5
        corr = cov / (vx*vy) if vx and vy else 0.0
    else:
        corr = float("nan")

    # How concentrated was the very beginning?
    return {
        "name": name,
        "n": total,
        "agents": len(recv_final),
        "gini_final": gini(list(recv_final.values())),
        "gini_early": gini(list(recv_early.values())),
        "top5_overlap": overlap,
        "leader_held": leader_held,
        "corr_half": corr,
        "leader_share": recv_final.most_common(1)[0][1] / total if recv_final else 0,
        "top_early": top_early[:3],
        "top_final": top_final[:3],
    }


def main():
    sources = [("gen1", load_cites(GEN1))]
    for d in sorted(GEN2.iterdir()):
        # Skip dotted staging/backup copies — they duplicate a real colony.
        if d.name.startswith(".") or not (d / "swarm").is_dir():
            continue
        sources.append((f"gen2·{d.name}", load_cites(d / "swarm")))

    rows = [r for n, c in sources if (r := analyse(n, c))]
    cohort = [r for n, c in sources if (r := analyse(n, c, cohort_only=True))]

    print("=" * 90)
    print("路径依赖分析：早期领先是否锁定了最终格局")
    print("=" * 90)
    print("\n二代五台各自独立运行，是同一套规则的重复实验。\n")

    hdr = (f"{'群体':<16}{'引用':>6}{'agent':>6}{'早期Gini':>9}{'最终Gini':>9}"
           f"{'Top5重合':>9}{'冠军保持':>9}{'前后半相关':>11}{'冠军占比':>9}")
    print(hdr); print("-" * len(hdr))
    for r in rows:
        print(f"{r['name']:<16}{r['n']:>6}{r['agents']:>6}{r['gini_early']:>9.3f}"
              f"{r['gini_final']:>9.3f}{r['top5_overlap']:>7}/5"
              f"{('是' if r['leader_held'] else '否'):>9}"
              f"{r['corr_half']:>11.2f}{r['leader_share']*100:>8.1f}%")

    print("\n" + "─" * 90)
    print("解读")
    print("─" * 90)
    ov = [r["top5_overlap"] for r in rows]
    cr = [r["corr_half"] for r in rows if r["corr_half"] == r["corr_half"]]
    held = sum(1 for r in rows if r["leader_held"])
    print(f"  早期 Top5 中平均 {sum(ov)/len(ov):.1f} 个留在最终 Top5")
    print(f"  {held}/{len(rows)} 个群体的早期第一名保持到了最后")
    if cr:
        print(f"  前半程被引与后半程被引的相关系数: 均值 {sum(cr)/len(cr):.2f}")
        print(f"    （接近 1 = 强优先连接/马太效应；接近 0 = 地位可流动）")

    print("\n  早期 vs 最终 Top3:")
    for r in rows:
        print(f"    {r['name']:<16} 早期 {','.join(r['top_early']):<38} → 最终 {','.join(r['top_final'])}")

    print("\n" + "─" * 90)
    print("对照检验：只看开局就在场的 agent（排除「新成员稀释了排名」这一解释）")
    print("─" * 90)
    if cohort:
        print(f"  {'群体':<16}{'引用':>6}{'Top5重合':>9}{'冠军保持':>9}{'前后半相关':>11}")
        for r in cohort:
            print(f"  {r['name']:<16}{r['n']:>6}{r['top5_overlap']:>7}/5"
                  f"{('是' if r['leader_held'] else '否'):>9}{r['corr_half']:>11.2f}")
        ov2 = [r["top5_overlap"] for r in cohort]
        cr2 = [r["corr_half"] for r in cohort if r["corr_half"] == r["corr_half"]]
        held2 = sum(1 for r in cohort if r["leader_held"])
        print(f"\n  同期队列内: 早期 Top5 平均留存 {sum(ov2)/len(ov2):.1f} 个，"
              f"冠军保持 {held2}/{len(cohort)}，前后半相关均值 "
              f"{sum(cr2)/len(cr2):.2f}" if cr2 else "")
        print("  若这里的相关仍然很低，则地位流动不是人口增长造成的假象。")

    out = Path("/Users/bytedance/Downloads/swarm_path_dependence.json")
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(f"\n结果已存 {out}")


if __name__ == "__main__":
    main()
