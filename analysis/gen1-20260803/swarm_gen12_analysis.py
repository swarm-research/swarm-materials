#!/usr/bin/env python3
"""Compare the two swarm generations on the same measures.

Gen 1: 36 agents on one Mac via MASO, one shared filesystem.
Gen 2: agents spread over five devboxes, each with its own /tmp/swarm. The
sync that was supposed to merge them never ran, so gen 2 is really five
isolated colonies that started from the same seed state — which makes it an
accidental replication experiment: same rules, five independent runs.

That is the most useful thing about gen 2 and it is why the boxes are kept
separate here instead of being pooled.
"""

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

GEN1 = Path("/Users/bytedance/Downloads/swarm")
GEN2 = Path("/Users/bytedance/Downloads/swarm-gen2")
KINDS = ["tools", "findings", "data", "challenges", "builds"]
SEEDS1 = {"agent-005", "agent-017", "agent-029"}


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


def gini(xs):
    xs = sorted(xs); n = len(xs); s = sum(xs)
    if not n or not s:
        return 0.0
    return (2 * sum((i + 1) * x for i, x in enumerate(xs))) / (n * s) - (n + 1) / n


def entropy(cs):
    t = sum(cs)
    return -sum((c / t) * math.log2(c / t) for c in cs if c > 0) if t else 0.0


def load(root):
    """Read one colony: outputs by agent, citations, messages."""
    outputs = defaultdict(Counter)
    for kind in KINDS:
        d = root / "commons" / kind
        if not d.is_dir():
            continue
        for f in d.iterdir():
            m = re.match(r"(agent-\d+)_", f.name)
            a = norm(m.group(1)) if m else None
            if a:
                outputs[a][kind] += 1

    cites, junk = [], 0
    for c in jsonl(root / "citations.jsonl"):
        # Gen 1 wrote the path as "file"; the devbox runner used "artifact".
        f = str(c.get("file") or c.get("artifact") or "")
        if f.startswith(("commons/", "agents/")):
            cites.append(c)
        else:
            junk += 1

    msgs = list(jsonl(root / "board" / "messages.jsonl"))
    return outputs, cites, junk, msgs


def stats(name, outputs, cites, junk, msgs):
    recv, give, pairs = Counter(), Counter(), Counter()
    citers_of = defaultdict(set)
    for c in cites:
        a, b = norm(c.get("citer")), norm(c.get("cited"))
        if a and b:
            give[a] += 1; recv[b] += 1; pairs[(a, b)] += 1; citers_of[b].add(a)

    actors = {a for a in (set(outputs) | set(give) | set(recv)) if a}
    n_out = sum(sum(v.values()) for v in outputs.values())
    mutual = sum(1 for (x, y) in pairs if x != y and (y, x) in pairs)

    glob = Counter()
    for v in outputs.values():
        glob.update(v)
    tot = sum(glob.values()) or 1
    spec = 0; considered = 0
    for a, c in outputs.items():
        n = sum(c.values())
        if n < 5:
            continue
        considered += 1
        kl = sum((c[k]/n) * math.log2((c[k]/n) / (glob[k]/tot))
                 for k in KINDS if c[k] and glob[k])
        if kl >= 0.3:
            spec += 1

    return {
        "name": name,
        "agents": len(actors),
        "outputs": n_out,
        "citations": len(cites),
        "junk_pct": junk / max(len(cites) + junk, 1) * 100,
        "messages": len(msgs),
        "gini": gini([recv.get(a, 0) for a in actors]),
        "zero_cited": sum(1 for a in actors if recv.get(a, 0) == 0),
        "mutual_pct": mutual / max(len(pairs), 1) * 100,
        "edges": len(pairs),
        "spec_pct": spec / max(considered, 1) * 100,
        "considered": considered,
        "cite_per_output": len(cites) / max(n_out, 1),
        "top": recv.most_common(3),
        "mix": {k: glob[k] / tot * 100 for k in KINDS if glob[k]},
    }


def main():
    rows = [stats("gen1 (Mac, 36 agent)", *load(GEN1))]

    colonies = []
    for d in sorted(GEN2.iterdir()):
        if d.is_dir() and (d / "swarm").is_dir():
            colonies.append((d.name, *load(d / "swarm")))
    for name, *rest in colonies:
        rows.append(stats(f"gen2 · {name}", *rest))

    print("=" * 96)
    print("一代 vs 二代整合分析")
    print("=" * 96)
    print("\n二代的五台机器各自独立（同步从未生效），所以它们是同一套规则下的五次独立重复实验。\n")

    hdr = f"{'群体':<24}{'agent':>6}{'产出':>7}{'引用':>7}{'消息':>7}{'Gini':>7}{'互引%':>7}{'专精%':>7}{'引用/产出':>9}"
    print(hdr); print("-" * len(hdr))
    for r in rows:
        print(f"{r['name']:<24}{r['agents']:>6}{r['outputs']:>7}{r['citations']:>7}"
              f"{r['messages']:>7}{r['gini']:>7.3f}{r['mutual_pct']:>6.1f}%"
              f"{r['spec_pct']:>6.0f}%{r['cite_per_output']:>9.2f}")

    g2 = [r for r in rows if r["name"].startswith("gen2")]
    if g2:
        tot_out = sum(r["outputs"] for r in g2)
        tot_cite = sum(r["citations"] for r in g2)
        print(f"\n二代合计: 产出 {tot_out:,}  引用 {tot_cite:,}  "
              f"消息 {sum(r['messages'] for r in g2):,}")
        print(f"一代合计: 产出 {rows[0]['outputs']:,}  引用 {rows[0]['citations']:,}  "
              f"消息 {rows[0]['messages']:,}")
        print(f"规模比:   产出 {tot_out/max(rows[0]['outputs'],1):.1f}×  "
              f"引用 {tot_cite/max(rows[0]['citations'],1):.1f}×")

    print("\n" + "─" * 96)
    print("跨群体一致性 — 同一套规则重复五次，哪些指标稳定")
    print("─" * 96)
    live = [r for r in g2 if r["edges"] > 20]
    for key, label, fmt in [("gini", "被引 Gini", "{:.3f}"),
                            ("mutual_pct", "互引率 %", "{:.1f}"),
                            ("spec_pct", "专精比例 %", "{:.0f}"),
                            ("cite_per_output", "引用/产出", "{:.2f}")]:
        vals = [r[key] for r in live]
        if len(vals) < 2:
            continue
        mean = sum(vals) / len(vals)
        sd = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
        g1v = rows[0][key]
        print(f"  {label:<14} 二代五次: " + "  ".join(fmt.format(v) for v in vals)
              + f"   均值 {fmt.format(mean)} ± {fmt.format(sd)}"
              + f"   | 一代 {fmt.format(g1v)}")

    print("\n" + "─" * 96)
    print("产出构成对比 (%)")
    print("─" * 96)
    print(f"  {'群体':<24}" + "".join(f"{k:>12}" for k in KINDS))
    for r in rows:
        print(f"  {r['name']:<24}" + "".join(f"{r['mix'].get(k,0):>11.1f}" for k in KINDS))

    print("\n" + "─" * 96)
    print("数据质量：占位引用比例")
    print("─" * 96)
    for r in rows:
        print(f"  {r['name']:<24} {r['junk_pct']:>5.1f}%")

    out = Path("/Users/bytedance/Downloads/swarm_gen12_summary.json")
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(f"\n结果已存 {out}")


if __name__ == "__main__":
    main()
