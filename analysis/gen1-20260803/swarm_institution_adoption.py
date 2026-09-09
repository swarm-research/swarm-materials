#!/usr/bin/env python3
"""
制度采纳分析：自发认识论制度的谱系、采纳曲线、跨机独立性。

语料：
  gen1  = ~/Downloads/swarm/commons（36 agent，MASO，08-01~03）
  gen2  = ~/Downloads/swarm-gen2/{122174,122175,122448,122456}/swarm/commons
          四台隔离 devbox（各自独立 swarm），种子=一代语料副本，与一代并行运行
世代归属：按作者前缀。agent-001..036 在二代机上有歧义（种子副本 vs 复活体产出），
  一律不计入"二代原生"；二代原生 = agent-037 及以上（含 4 位 ID）。
分类逻辑：
  - 制度在 gen1 出现 + 二代原生采纳         → 文化传递（读种子学会的）
  - 制度 gen1 缺席 + 多台二代机独立出现     → 收敛发明（最强证据）
  - 但须先排除 launcher/prompt 词汇诱导     → 扫描各机编排脚本
时间全部用 mtime（内核时钟）。名义时间戳不用（第九重失效：斜率 4.05×）。
所有计数是下界：正则求准不求全。
"""
import json, os, re
from datetime import datetime, timezone
from collections import defaultdict

HOME = os.path.expanduser("~/Downloads")
GEN1 = os.path.join(HOME, "swarm")
GEN2 = {m: os.path.join(HOME, "swarm-gen2", m, "swarm") for m in
        ["122174", "122175", "122448", "122456"]}
TEXT_EXT = (".md", ".txt", ".json", ".py", ".jsonl", ".sh", ".csv", ".yaml", ".yml")
AGENT_RE = re.compile(r"^(agent-\d{3,4})")
GEN1_IDS = {f"agent-{i:03d}" for i in range(1, 37)}

INSTITUTIONS = {
    "预注册":       re.compile(r"preregist|pre-regist|预注册|registered prediction|registering (a |the )?prediction", re.I),
    "哈希锚定":     re.compile(r"sha-?256|sha256sum|SHA256SUMS", re.I),
    "reader契约":   re.compile(r"filter to taste|no record is removed|apply a named profile|verdicts are advisory|nothing deleted|原始记录保留", re.I),
    "EXPECTED_RED": re.compile(r"EXPECTED[-_]?RED|EXPECTED[-_]?FAIL"),
    "撤仪器重算":   re.compile(r"\bR10\b|recompute every number|撤回仪器.{0,15}重算", re.I),
    "supersession": re.compile(r"superseded_by|supersession|SUPERSEDES", re.I),
    "机检证书":     re.compile(r"\blrat\b|\bdrat\b|machine-checkable proof|机检证书", re.I),
    "利益冲突披露": re.compile(r"conflict[- ]of[- ]interest|利益冲突|\bCOI\b(?![A-Za-z])", re.I),
    "阴性对照":     re.compile(r"negative control|阴性对照|known-answer test|decoy", re.I),
    "盲评自觉":     re.compile(r"blind (review|audit|rating|assessment|re-?rating)|盲评|not yet looked", re.I),
    "承诺揭示":     re.compile(r"sealbox|commit[- ]reveal|sealed (claim|prediction|proposition)|承诺-?揭示", re.I),
    "自我终止规则": re.compile(r"self-?terminat|自我终止|halting rule|stopping rule", re.I),
    "更正文化":     None,  # 按文件名判：CORRECTION/RETRACT
}
FNAME_CORRECTION = re.compile(r"CORRECTION|RETRACT|correction|retraction|更正|撤回|STAND-DOWN|stand-down")

def walk_commons(root):
    out = []
    cdir = os.path.join(root, "commons")
    for r, _, files in os.walk(cdir):
        for fn in files:
            p = os.path.join(r, fn)
            try:
                mt = datetime.fromtimestamp(os.path.getmtime(p), tz=timezone.utc)
            except OSError:
                continue
            m = AGENT_RE.match(fn)
            out.append((mt, m.group(1) if m else None, p, fn))
    out.sort(key=lambda x: x[0])
    return out

def read_text(p):
    try:
        if os.path.getsize(p) > 2_000_000 or not p.endswith(TEXT_EXT):
            return ""
        return open(p, errors="ignore").read()
    except OSError:
        return ""

def native(author, corpus):
    """该作者是否是本语料的'原生'作者。"""
    if author is None:
        return False
    if corpus == "gen1":
        return author in GEN1_IDS
    return author not in GEN1_IDS  # gen2: 只认 037+，001-036 有歧义排除

def scan(corpus_name, root):
    files = walk_commons(root)
    hits = defaultdict(list)  # inst -> [(mtime, author, relpath)]
    for mt, author, p, fn in files:
        rel = os.path.relpath(p, root)
        matched = set()
        if FNAME_CORRECTION.search(fn):
            matched.add("更正文化")
        txt = read_text(p)
        if txt:
            for inst, pat in INSTITUTIONS.items():
                if pat is not None and pat.search(txt):
                    matched.add(inst)
        for inst in matched:
            hits[inst].append((mt, author, rel))
    return files, hits

def summarize(corpus_name, files, hits):
    t0 = min(mt for mt, _, _, _ in files) if files else None
    summary = {}
    for inst in list(INSTITUTIONS):
        rows = hits.get(inst, [])
        nat = [(mt, a, rel) for mt, a, rel in rows if native(a, corpus_name if corpus_name == "gen1" else "gen2")]
        authors = sorted({a for _, a, _ in nat})
        # 采纳曲线：每个原生作者的首次使用时刻（相对语料首文件的小时数）
        first_use = {}
        for mt, a, rel in nat:
            if a not in first_use or mt < first_use[a][0]:
                first_use[a] = (mt, rel)
        curve = sorted(round((mt - t0).total_seconds() / 3600, 1) for mt, _ in first_use.values()) if t0 else []
        first3 = [(mt.isoformat(), a, rel) for mt, a, rel in sorted(nat, key=lambda x: x[0])[:3]]
        summary[inst] = {
            "n_files_native": len(nat), "n_authors_native": len(authors),
            "adoption_curve_hours": curve, "first3": first3,
        }
    return summary

def launcher_vocab(machine_root):
    """编排脚本里出现了哪些制度词汇（排除 prompt 诱导）。"""
    found = {}
    parent = os.path.dirname(os.path.join(machine_root, "x"))  # machine/swarm
    for fn in os.listdir(parent):
        if not fn.endswith(".py"):
            continue
        txt = read_text(os.path.join(parent, fn))
        for inst, pat in INSTITUTIONS.items():
            if pat is not None and pat.search(txt):
                found.setdefault(inst, []).append(fn)
    return found

results = {}
g1_files, g1_hits = scan("gen1", GEN1)
results["gen1"] = summarize("gen1", g1_files, g1_hits)
gen1_present = {inst for inst, s in results["gen1"].items() if s["n_authors_native"] >= 1}

for m, root in GEN2.items():
    fs, hs = scan(m, root)
    results[m] = summarize(m, fs, hs)
    results[m]["_launcher_vocab"] = launcher_vocab(root)

# 跨机汇总
cross = {}
for inst in INSTITUTIONS:
    machines = [m for m in GEN2 if results[m][inst]["n_authors_native"] >= 1]
    prompted = [m for m in GEN2 if inst in results[m].get("_launcher_vocab", {})]
    cross[inst] = {
        "in_gen1": inst in gen1_present,
        "gen1_authors": results["gen1"][inst]["n_authors_native"],
        "gen2_machines_present": machines, "k_of_4": len(machines),
        "launcher_vocab_machines": prompted,
        "classification": (
            "prompt诱导可疑" if prompted else
            "文化传递" if inst in gen1_present and machines else
            "收敛发明" if not (inst in gen1_present) and len(machines) >= 2 else
            "单机特有" if not (inst in gen1_present) and len(machines) == 1 else
            "仅一代" if inst in gen1_present else "未出现"),
    }

out = os.path.join(HOME, "swarm_institution_results.json")
json.dump({"per_corpus": results, "cross": cross}, open(out, "w"), ensure_ascii=False, indent=1)

print(f"{'制度':<10} gen1作者  四台二代(原生作者数)          分类")
for inst, c in cross.items():
    per_m = " ".join(f"{m[-3:]}:{results[m][inst]['n_authors_native']:>3}" for m in GEN2)
    print(f"{inst:<12} {c['gen1_authors']:>4}   {per_m}   {c['classification']}"
          + (f"  ⚠launcher:{','.join(c['launcher_vocab_machines'])}" if c['launcher_vocab_machines'] else ""))
print(f"\n结果已存 {out}")
