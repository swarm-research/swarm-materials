#!/usr/bin/env python3
"""Try to kill the two strongest claims from the insight passes. Read-only.

Claim A: output collapses 76–98% after an agent is first cited.
  Rival explanation: everything slows down late in a run, so any mid-run
  split point would show the same drop. Test with a placebo split.

Claim B: 60–87% of citations sit inside reciprocal loops.
  Rival explanation: with this many edges among this few agents, a random
  graph with the same degrees would also be full of loops. Test against a
  degree-preserving null model.

Also new ground: gen 2 recorded a free-text `reason` on each citation, so we
can read why agents said they were citing.
"""

import json
import random
import re
import datetime
from collections import Counter, defaultdict
from pathlib import Path

random.seed(11)

GEN1 = Path("/Users/bytedance/Downloads/swarm")
GEN2 = Path("/Users/bytedance/Downloads/swarm-gen2")


def norm(a):
    m = re.match(r"agent-0*(\d+)$", str(a or "").strip())
    return f"agent-{int(m.group(1)):03d}" if m else None


def ts(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def load(root):
    out = []
    p = root / "citations.jsonl"
    if not p.exists():
        return out
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
            out.append({"citer": a, "cited": b, "t": ts(c.get("time")),
                        "reason": str(c.get("reason") or "")})
    return out


def colonies():
    yield "gen1", load(GEN1)
    for d in sorted(GEN2.iterdir()):
        if not d.name.startswith(".") and (d / "swarm").is_dir():
            yield f"gen2·{d.name}", load(d / "swarm")


MIN_SPAN_H = 0.08


def rate_split(times, cut):
    """Activity rate before and after a cut time, or None if too thin."""
    b = [t for t in times if t < cut]
    a = [t for t in times if t >= cut]
    if len(b) < 3 or len(a) < 3:
        return None
    bh = (b[-1] - b[0]).total_seconds() / 3600
    ah = (a[-1] - a[0]).total_seconds() / 3600
    if bh < MIN_SPAN_H or ah < MIN_SPAN_H:
        return None
    return len(b) / bh, len(a) / ah


def main():
    data = [(n, c) for n, c in colonies() if len(c) >= 60]

    # ── A. 安慰剂检验 ────────────────────────────────────────
    print("=" * 88)
    print("A. 「被引后产出暴跌」是真效应，还是后期普遍衰减？")
    print("=" * 88)
    print("\n  真实切点 = 该 agent 首次被引的时刻")
    print("  安慰剂切点 = 同一 agent 活动区间内的随机时刻（重复 20 次取均值）")
    print("  若两者跌幅接近，说明下降与「被引」无关，只是后期变慢\n")
    print(f"  {'群体':<16}{'真实跌幅':>10}{'安慰剂跌幅':>12}{'差值':>10}{'n':>5}")
    print("  " + "-" * 56)
    for name, cites in data:
        dated = [c for c in cites if c["t"]]
        first_recv = {}
        for c in sorted(dated, key=lambda c: c["t"]):
            first_recv.setdefault(c["cited"], c["t"])
        acts = defaultdict(list)
        for c in dated:
            acts[c["citer"]].append(c["t"])

        real, placebo, n = [], [], 0
        for a, times in acts.items():
            f = first_recv.get(a)
            if not f or len(times) < 6:
                continue
            times.sort()
            r = rate_split(times, f)
            if not r:
                continue
            real.append(r[1] / r[0] - 1)
            n += 1
            # placebo cuts drawn from the same activity window
            span = (times[-1] - times[0]).total_seconds()
            got = []
            for _ in range(20):
                cut = times[0] + datetime.timedelta(seconds=random.uniform(span*0.2, span*0.8))
                rp = rate_split(times, cut)
                if rp:
                    got.append(rp[1]/rp[0] - 1)
            if got:
                placebo.append(sum(got)/len(got))
        if real and placebo:
            rm = sum(real)/len(real)*100
            pm = sum(placebo)/len(placebo)*100
            print(f"  {name:<16}{rm:>9.0f}%{pm:>11.0f}%{rm-pm:>9.0f}%{n:>5}")

    # ── B. 互引环的零模型对照 ────────────────────────────────
    print("\n" + "=" * 88)
    print("B. 「引用集中在互引环内」超出随机水平了吗？")
    print("=" * 88)
    print("\n  零模型：保持每个 agent 的出引/被引次数不变，随机重连（100 次）\n")
    print(f"  {'群体':<16}{'实际环内%':>10}{'随机环内%':>11}{'超出':>9}{'倍数':>8}")
    print("  " + "-" * 56)
    for name, cites in data:
        pairs = [(c["citer"], c["cited"]) for c in cites if c["citer"] != c["cited"]]
        if len(pairs) < 50:
            continue
        edges = set(pairs)
        real_loop = sum(1 for a, b in pairs if (b, a) in edges) / len(pairs) * 100

        srcs = [a for a, _ in pairs]
        dsts = [b for _, b in pairs]
        sims = []
        for _ in range(100):
            random.shuffle(dsts)
            rp = [(a, b) for a, b in zip(srcs, dsts) if a != b]
            re_ = set(rp)
            if rp:
                sims.append(sum(1 for a, b in rp if (b, a) in re_) / len(rp) * 100)
        rnd = sum(sims)/len(sims) if sims else 0
        print(f"  {name:<16}{real_loop:>9.1f}%{rnd:>10.1f}%{real_loop-rnd:>8.1f}%"
              f"{real_loop/max(rnd,0.01):>7.1f}×")

    # ── C. 引用理由（仅二代有） ──────────────────────────────
    print("\n" + "=" * 88)
    print("C. agent 自己说的引用理由（二代记录了 reason 字段）")
    print("=" * 88)
    reasons = [c["reason"] for _, cs in data for c in cs if c["reason"].strip()]
    print(f"\n  有理由文本的引用 {len(reasons):,} 条\n")
    if reasons:
        cats = {
            "直接复用/依赖": ["use", "used", "using", "reuse", "depend", "built on", "基于", "复用", "调用"],
            "验证/复现": ["verif", "replicat", "confirm", "reproduc", "check", "验证", "复现", "核对"],
            "反驳/纠错": ["contradict", "wrong", "error", "refute", "disagree", "bug", "错误", "反驳", "纠正"],
            "扩展/改进": ["extend", "improve", "build on", "enhance", "扩展", "改进", "增强"],
            "参考/背景": ["reference", "context", "background", "related", "参考", "背景"],
            "指出局限": ["limitation", "caveat", "however", "but ", "局限", "但是", "不足"],
        }
        low = [r.lower() for r in reasons]
        for cat, kws in cats.items():
            n = sum(1 for r in low if any(k in r for k in kws))
            print(f"    {cat:<14} {n:5d} ({n/len(low)*100:5.1f}%)")
        print(f"\n  理由长度中位 {sorted(len(r) for r in reasons)[len(reasons)//2]} 字符")
        print("\n  样例:")
        for r in reasons[:4]:
            print(f"    · {r[:110]}")

    # ── D. 谁在批评谁 ────────────────────────────────────────
    print("\n" + "=" * 88)
    print("D. 批评性引用是向上还是向下")
    print("=" * 88)
    crit_kw = ["contradict", "wrong", "error", "refute", "disagree", "bug",
               "limitation", "caveat", "错误", "反驳", "纠正", "局限", "不足"]
    for name, cites in data:
        withr = [c for c in cites if c["reason"].strip()]
        if len(withr) < 40:
            continue
        recv = Counter(c["cited"] for c in cites)
        up = down = 0
        for c in withr:
            if not any(k in c["reason"].lower() for k in crit_kw):
                continue
            if recv.get(c["cited"], 0) > recv.get(c["citer"], 0):
                up += 1
            else:
                down += 1
        if up + down >= 10:
            print(f"  {name:<16} 批评性引用 {up+down:4d} 条   "
                  f"向上（批更强者）{up/(up+down)*100:4.0f}%   向下 {down/(up+down)*100:4.0f}%")


if __name__ == "__main__":
    main()
