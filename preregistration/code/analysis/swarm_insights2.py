#!/usr/bin/env python3
"""Second insight pass — adversarial, linguistic and temporal angles. Read-only.

  6. Is anyone farming reciprocal citations (rings, tight loops)?
  7. Does how you announce change whether you get cited?
  8. Does a colony converge on shared vocabulary, or fragment?
  9. What happens right after an agent is cited — does it change behaviour?
 10. Do agents duplicate each other's work, and does anyone notice?
 11. Does the model tier an agent runs on predict its standing?
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
            cites.append({"citer": a, "cited": b, "file": f, "t": ts(c.get("time"))})
    msgs = [{"from": norm(m.get("from")), "to": str(m.get("to", "")),
             "text": str(m.get("message", "")), "t": ts(m.get("time"))}
            for m in jsonl(root / "board" / "messages.jsonl") if norm(m.get("from"))]
    names = defaultdict(list)
    for kind in KINDS:
        d = root / "commons" / kind
        if d.is_dir():
            for f in d.iterdir():
                mm = re.match(r"(agent-\d+)_", f.name)
                if mm:
                    names[norm(mm.group(1))].append((kind, f.name))
    return cites, msgs, names


def main():
    data = {n: load(r) for n, r in colonies()}
    live = {n: d for n, d in data.items() if len(d[0]) >= 60}

    # ── 6. 互引环 ──────────────────────────────────────────────
    print("=" * 86)
    print("6. 有没有人在刷互引：紧密回路检测")
    print("=" * 86)
    print(f"\n  {'群体':<16}{'2环':>6}{'3环':>6}{'环内引用占比':>13}{'最密集对':>26}")
    print("  " + "-" * 68)
    for name, (cites, msgs, names) in live.items():
        pair = Counter((c["citer"], c["cited"]) for c in cites)
        edges = set(pair)
        two = {(a, b) for (a, b) in edges if a != b and (b, a) in edges}
        # triangles a→b→c→a
        adj = defaultdict(set)
        for a, b in edges:
            if a != b:
                adj[a].add(b)
        three = 0
        nodes = list(adj)
        for a in nodes:
            for b in list(adj[a]):
                for c in list(adj.get(b, ())):
                    if a < b < c and a in adj.get(c, ()):
                        three += 1
        in_loop = sum(n for (a, b), n in pair.items() if (b, a) in edges and a != b)
        hottest = max(((pair[(a, b)] + pair.get((b, a), 0), a, b)
                       for (a, b) in two), default=(0, "", ""))
        print(f"  {name:<16}{len(two)//2:>6}{three:>6}{in_loop/max(len(cites),1)*100:>12.1f}%"
              f"   {hottest[1]}↔{hottest[2]} ({hottest[0]}次)")

    # ── 7. 公告措辞与被引 ───────────────────────────────────────
    print("\n" + "=" * 86)
    print("7. 公告怎么写才有人理：措辞特征 vs 该 agent 的被引量")
    print("=" * 86)
    feats = {
        "带文件路径": lambda t: "commons/" in t,
        "提问/求助": lambda t: any(k in t for k in ["?", "？", "请问", "有人", "谁能"]),
        "点名他人": lambda t: bool(re.search(r"agent-\d+", t)),
        "宣告完成": lambda t: any(k in t for k in ["已发布", "已完成", "我写了", "published", "done"]),
        "提议协作": lambda t: any(k in t for k in ["一起", "协作", "合作", "joint", "collab"]),
        "带数据/数字": lambda t: bool(re.search(r"\d+%|\d+\s*(个|条|次)", t)),
    }
    agg = {k: [[], []] for k in feats}      # [用了该特征的被引], [没用的被引]
    for name, (cites, msgs, names) in live.items():
        recv = Counter(c["cited"] for c in cites)
        by_agent = defaultdict(list)
        for m in msgs:
            by_agent[m["from"]].append(m["text"])
        for a, texts in by_agent.items():
            joined = "\n".join(texts)
            for k, fn in feats.items():
                agg[k][0 if fn(joined) else 1].append(recv.get(a, 0))
    print(f"\n  {'措辞特征':<14}{'用了→平均被引':>15}{'没用→平均被引':>15}{'倍数':>8}")
    print("  " + "-" * 52)
    for k, (yes, no) in agg.items():
        if len(yes) < 5 or len(no) < 5:
            continue
        y, n = sum(yes)/len(yes), sum(no)/len(no)
        # A zero baseline makes any ratio meaningless — say so rather than
        # printing a large fake-precise multiple.
        ratio = f"{y/n:.1f}×" if n > 0.5 else "对照组为0"
        print(f"  {k:<14}{y:>14.1f}{n:>15.1f}{ratio:>10}")

    # ── 8. 词汇收敛还是分裂 ─────────────────────────────────────
    print("\n" + "=" * 86)
    print("8. 群体会不会形成共同语汇（看文件名用词的集中度随时间变化）")
    print("=" * 86)
    print(f"\n  {'群体':<16}{'前半独有词':>11}{'后半独有词':>11}{'沿用率':>9}")
    print("  " + "-" * 48)
    for name, (cites, msgs, names) in live.items():
        allf = sorted((fn for lst in names.values() for _, fn in lst))
        if len(allf) < 40:
            continue
        half = len(allf) // 2
        def words(fs):
            w = Counter()
            for fn in fs:
                body = re.sub(r"^agent-\d+_|_?\d{8}T?\d*Z?", "", fn)
                w.update(set(re.findall(r"[a-z]{4,}", body.lower())))
            return w
        w1, w2 = words(allf[:half]), words(allf[half:])
        carried = len(set(w1) & set(w2))
        print(f"  {name:<16}{len(w1):>11}{len(w2):>11}{carried/max(len(w2),1)*100:>8.1f}%")

    # ── 9. 被引之后行为怎么变 ───────────────────────────────────
    print("\n" + "=" * 86)
    print("9. 第一次被引之后，产出速度变了吗")
    print("=" * 86)
    print(f"\n  {'群体':<16}{'首次被引前/小时':>15}{'之后/小时':>12}{'变化':>9}")
    print("  " + "-" * 54)
    for name, (cites, msgs, names) in live.items():
        dated = [c for c in cites if c["t"]]
        if len(dated) < 60:
            continue
        first_recv = {}
        for c in sorted(dated, key=lambda c: c["t"]):
            first_recv.setdefault(c["cited"], c["t"])
        # use each agent's own citing activity as an activity proxy
        acts = defaultdict(list)
        for c in dated:
            acts[c["citer"]].append(c["t"])
        before_rates, after_rates = [], []
        for a, times in acts.items():
            f = first_recv.get(a)
            if not f or len(times) < 6:
                continue
            times.sort()
            b = [t for t in times if t < f]
            aft = [t for t in times if t >= f]
            # A span shorter than a few minutes makes the rate explode, so
            # require a real window on both sides instead of clamping.
            if len(b) >= 3 and len(aft) >= 3:
                bh = (b[-1]-b[0]).total_seconds()/3600
                ah = (aft[-1]-aft[0]).total_seconds()/3600
                if bh >= 0.08 and ah >= 0.08:
                    before_rates.append(len(b)/bh); after_rates.append(len(aft)/ah)
        if before_rates:
            bm = sum(before_rates)/len(before_rates)
            am = sum(after_rates)/len(after_rates)
            print(f"  {name:<16}{bm:>15.1f}{am:>12.1f}{(am/bm-1)*100:>8.0f}%")

    # ── 10. 重复劳动 ───────────────────────────────────────────
    print("\n" + "=" * 86)
    print("10. 有多少重复造轮子（不同 agent 造了名字高度相似的东西）")
    print("=" * 86)
    for name, (cites, msgs, names) in live.items():
        stems = defaultdict(set)
        for a, lst in names.items():
            for kind, fn in lst:
                body = re.sub(r"^agent-\d+_|_?\d{8}T?\d*Z?.*$", "", fn)
                key = tuple(sorted(set(re.findall(r"[a-z]{4,}", body.lower()))))
                if len(key) >= 2:
                    stems[key].add(a)
        dup = {k: v for k, v in stems.items() if len(v) >= 3}
        tot = sum(len(l) for l in names.values())
        print(f"  {name:<16} ≥3 个 agent 撞题的主题 {len(dup):3d} 个"
              f"   占全部产出 {sum(len(v) for v in dup.values())/max(tot,1)*100:4.1f}%")
        if dup:
            top = sorted(dup.items(), key=lambda kv: -len(kv[1]))[:2]
            for k, v in top:
                print(f"      「{'_'.join(k[:4])}」 {len(v)} 个 agent 各做一遍")


if __name__ == "__main__":
    main()
