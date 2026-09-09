#!/usr/bin/env python3
"""
Role-differentiation / functional-specialization probe for the swarm corpora.
LOCAL DATA ONLY. Read-only on the corpora; writes only under ~/Downloads/swarm-iclr/.

Corpora
  gen1   ~/Downloads/swarm                 roster agent-001..036 (swarm_launcher.py, identical prompt;
                                           seeds 005/017/029 got SEED_EXTRA; expansion 037-100 mostly failed,
                                           agent-042 = Saboteur with 4 files)
  gen2   ~/Downloads/swarm-gen2/<machine>/swarm   native = ids in devbox_sessions.json (all >= 037);
                                           001-036 are seed copies; W1 seeds 38,45,...; W1 adversaries 42,51,59,67,74,83;
                                           W2 seeds every 50 from 105; W2 adversaries 150,280,...
                                           122447 has no sessions file / no native output -> excluded.

Time discipline (from swarm_event_study.py / 零成本分析): file mtime = kernel clock (most trusted);
declared times with Z/offset = UTC; bare declared times = local (EDT on gen1; inferred per corpus here
from board-message <-> file-mtime pairs).

Act types (mutually exclusive partition used for entropy; K = 9):
  finding, tool, build, challenge, data  (commons subdir, unless the basename carries a marker)
  correct   basename or message matches CORR_RE  (correction/erratum/retract/supersede/stand-down/更正/撤回)
  verify    basename matches VERIF_RE (verif*/audit*/replic*/reproduc*/check*(not checkpoint)/negative control);
            board messages use the stricter VERIF_MSG_RE (no bare 'check')
  board     other board messages (coordination)
  cite      citation rows (REALFILE filter: file starts with commons/ or agents/), citer = agent
Side features (not in the partition): citations received, distinct tool adopters, registry appends (gen1 only).
"""
import json, os, re, sys, math, random
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import pdist, squareform

HOME = os.path.expanduser("~/Downloads")
OUT_DIR = os.path.join(HOME, "swarm-iclr")
UTC = timezone.utc
RNG_SEED = 20260907
N_PERM = 1000
MIN_ACTS = 5
TYPES = ["finding", "tool", "build", "challenge", "data", "verify", "correct", "board", "cite"]
K = len(TYPES)
TIDX = {t: i for i, t in enumerate(TYPES)}
SUBDIRS = {"findings": "finding", "tools": "tool", "builds": "build", "challenges": "challenge", "data": "data"}

CORR_RE = re.compile(r"correction|errat|retract|supersed|stand-?down|更正|撤回", re.I)
VERIF_RE = re.compile(r"(?<![a-z])(verif|audit|replic|reproduc|check(?!point)|negative[-_ ]?control)", re.I)
VERIF_MSG_RE = re.compile(r"(?<![a-z])(verif|audit|replicat|reproduc|negative[-_ ]?control|阴性对照|复现|审计|验证)", re.I)
AGENT_RE = re.compile(r"^(agent-(\d{3,4}))(?![0-9])")
AGENT_ANY = re.compile(r"(agent-(\d{3,4}))(?![0-9])")
PATH_RE = re.compile(r"commons/(?:tools|findings|data|challenges|builds)/[\w\-.]+\.\w+")

W1_SEEDS = {38, 45, 52, 60, 69, 76, 85, 92, 99}
W1_ADV = {42: "Saboteur", 51: "Parasite", 59: "Infiltrator", 67: "Escapist", 74: "Provocateur", 83: "Nihilist"}
W2_SEEDS = set(range(105, 1001, 50))
W2_ADV = {150: "Gaslighter", 280: "Monopolist", 420: "Accelerationist", 560: "DoubleAgent", 700: "EntropyAgent", 850: "CultLeader"}
GEN1_SEEDS = {5, 17, 29}
GEN1_MODELS = {}
for i, m in zip(range(1, 37), ["gpt56_sol_reasoning_xhigh"] * 4 + ["gpt56_sol_reasoning_high"] * 4 + ["gpt56_sol"] * 4 +
               ["es1_orange_o50_thinking_max"] * 4 + ["es1_orange_o50_thinking"] * 4 + ["es1_orange_o50"] * 4 +
               ["seed-stable-reasoning-high"] * 4 + ["seed-stable-reasoning"] * 4 + ["seed-stable"] * 4):
    GEN1_MODELS[f"agent-{i:03d}"] = m

def model_family(m):
    m = (m or "").lower()
    if "sol" in m or "gpt" in m: return "sol"
    if "orange" in m: return "orange"
    if "seed" in m or m.startswith("ep-"): return "seed"
    return "other"

# ----------------------------------------------------------------------------- helpers
def parse_ts(s, bare_offset_h):
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    try:
        if s.endswith("Z"):
            return datetime.fromisoformat(s[:-1]).replace(tzinfo=UTC)
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone(timedelta(hours=bare_offset_h))).astimezone(UTC)
        return dt.astimezone(UTC)
    except ValueError:
        return None

def mtime_utc(p):
    return datetime.fromtimestamp(os.path.getmtime(p), tz=UTC)

def read_jsonl(p):
    rows = []
    if not os.path.isfile(p):
        return rows
    for line in open(p, errors="ignore"):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows

def author_from_content(p):
    try:
        if os.path.getsize(p) > 2_000_000:
            return None
        head = open(p, errors="ignore").read(1500)
    except OSError:
        return None
    m = re.search(r'"author"\s*:\s*"(agent-\d{3,4})"', head) or re.search(r"\*\*(agent-\d{3,4})\*\*", head) \
        or re.search(r"(?:author|by)\s*[:：]\s*(agent-\d{3,4})", head, re.I)
    return m.group(1) if m else None

def attribute(rel_parts, full):
    """rel_parts = path components under commons/ (subdir, ..., basename)."""
    m = AGENT_RE.match(rel_parts[-1])
    if m:
        return m.group(1), "basename"
    for comp in rel_parts[1:-1]:
        m = AGENT_RE.match(comp)
        if m:
            return m.group(1), "dir"
    a = author_from_content(full)
    if a:
        return a, "content"
    return None, "none"

def norm_entropy(counts):
    c = np.asarray(counts, dtype=float)
    n = c.sum()
    if n <= 0:
        return float("nan")
    p = c[c > 0] / n
    return float(-(p * np.log(p)).sum() / math.log(K))

def herfindahl(counts):
    c = np.asarray(counts, dtype=float); n = c.sum()
    return float(((c / n) ** 2).sum()) if n > 0 else float("nan")

def jsd(p, q):
    p = np.asarray(p, float); q = np.asarray(q, float)
    p = p / p.sum(); q = q / q.sum(); m = 0.5 * (p + q)
    def kl(a, b):
        mask = a > 0
        return float((a[mask] * np.log(a[mask] / b[mask])).sum())
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)

def profile_matrix(agent_ids, acts_by_agent):
    M = np.zeros((len(agent_ids), K))
    for i, a in enumerate(agent_ids):
        for t in acts_by_agent[a]:
            M[i, TIDX[t]] += 1
    return M

def population_stats(M):
    """M: agents x K counts. Returns mean normalized entropy, mean Herfindahl, normalized MI(agent;type), mean pairwise JSD."""
    n_i = M.sum(1); N = M.sum()
    P = M / n_i[:, None]
    ent = np.array([norm_entropy(r) for r in M])
    hh = np.array([herfindahl(r) for r in M])
    pooled = M.sum(0) / N
    # MI(agent;type) = sum_i (n_i/N) * KL(P_i || pooled); normalize by H(type)
    kl = np.zeros(len(M))
    for i in range(len(M)):
        mask = P[i] > 0
        kl[i] = (P[i][mask] * np.log(P[i][mask] / pooled[mask])).sum()
    mi = float(((n_i / N) * kl).sum())
    pm = pooled[pooled > 0]
    h_type = float(-(pm * np.log(pm)).sum())
    nmi = mi / h_type if h_type > 0 else float("nan")
    # mean pairwise JSD
    d = []
    for i in range(len(M)):
        for j in range(i + 1, len(M)):
            d.append(jsd(P[i], P[j]))
    return {"mean_norm_entropy": float(ent.mean()), "mean_herfindahl": float(hh.mean()),
            "nmi_agent_type": nmi, "mean_pairwise_jsd": float(np.mean(d)) if d else float("nan"),
            "entropies": ent}

def permutation_null(M, n_perm, rng, mode="shuffle"):
    """mode='shuffle': permute type labels across all acts (preserves agent and type margins).
       mode='multinomial': each agent draws n_i types from the pooled distribution."""
    n_i = M.sum(1).astype(int); N = int(M.sum())
    pooled = M.sum(0) / N
    labels = np.repeat(np.arange(K), M.sum(0).astype(int))
    out = {"mean_norm_entropy": [], "mean_herfindahl": [], "nmi_agent_type": [], "mean_pairwise_jsd": [], "ent_per_agent": []}
    bounds = np.concatenate([[0], np.cumsum(n_i)])
    for _ in range(n_perm):
        Mn = np.zeros_like(M)
        if mode == "shuffle":
            lab = rng.permutation(labels)
            for i in range(len(n_i)):
                seg = lab[bounds[i]:bounds[i + 1]]
                Mn[i] = np.bincount(seg, minlength=K)
        else:
            for i in range(len(n_i)):
                Mn[i] = rng.multinomial(n_i[i], pooled)
        s = population_stats(Mn)
        for k in ("mean_norm_entropy", "mean_herfindahl", "nmi_agent_type", "mean_pairwise_jsd"):
            out[k].append(s[k])
        out["ent_per_agent"].append(s["entropies"])
    out["ent_per_agent"] = np.array(out["ent_per_agent"])
    return out

def stratified_null(M, strata, n_perm, rng):
    """Shuffle type labels only among acts of agents in the same stratum (model family)."""
    n_i = M.sum(1).astype(int)
    out = {"mean_norm_entropy": [], "mean_herfindahl": [], "nmi_agent_type": [], "mean_pairwise_jsd": [], "ent_per_agent": []}
    groups = defaultdict(list)
    for i, g in enumerate(strata):
        groups[g].append(i)
    for _ in range(n_perm):
        Mn = np.zeros_like(M)
        for g, idx in groups.items():
            labels = np.concatenate([np.repeat(np.arange(K), M[i].astype(int)) for i in idx])
            lab = rng.permutation(labels); pos = 0
            for i in idx:
                Mn[i] = np.bincount(lab[pos:pos + n_i[i]], minlength=K); pos += n_i[i]
        st = population_stats(Mn)
        for k in ("mean_norm_entropy", "mean_herfindahl", "nmi_agent_type", "mean_pairwise_jsd"):
            out[k].append(st[k])
        out["ent_per_agent"].append(st["entropies"])
    out["ent_per_agent"] = np.array(out["ent_per_agent"])
    return out

def family_mi(M, strata):
    """MI(family;type)/H(type) from family-aggregated counts."""
    fams = sorted(set(strata)); F = np.zeros((len(fams), K))
    for i, g in enumerate(strata):
        F[fams.index(g)] += M[i]
    return population_stats(F)["nmi_agent_type"] if len(fams) > 1 else 0.0

def null_summary(obs, null):
    res = {}
    for k in ("mean_norm_entropy", "mean_herfindahl", "nmi_agent_type", "mean_pairwise_jsd"):
        arr = np.array(null[k]); o = obs[k]
        lower_is_special = k == "mean_norm_entropy"
        p = float(((arr <= o).sum() + 1) / (len(arr) + 1)) if lower_is_special else float(((arr >= o).sum() + 1) / (len(arr) + 1))
        sd = float(arr.std(ddof=1)) if len(arr) > 1 else float("nan")
        res[k] = {"observed": float(o), "null_mean": float(arr.mean()), "null_sd": sd,
                  "null_p2.5": float(np.percentile(arr, 2.5)), "null_p97.5": float(np.percentile(arr, 97.5)),
                  "z": float((o - arr.mean()) / sd) if sd and sd > 0 else None, "p_one_sided": p}
    return res

def cramers_v(x, y):
    xs = sorted(set(x)); ys = sorted(set(y))
    T = np.zeros((len(xs), len(ys)))
    for a, b in zip(x, y):
        T[xs.index(a), ys.index(b)] += 1
    n = T.sum()
    if n == 0 or min(T.shape) < 2:
        return 0.0
    E = T.sum(1)[:, None] * T.sum(0)[None, :] / n
    mask = E > 0
    chi2 = float(((T[mask] - E[mask]) ** 2 / E[mask]).sum())
    return math.sqrt(chi2 / (n * (min(T.shape) - 1)))

def perm_p_cramers(x, y, rng, n_perm=1000):
    obs = cramers_v(x, y)
    y = list(y); cnt = 0
    for _ in range(n_perm):
        yy = list(rng.permutation(y)); cnt += cramers_v(x, yy) >= obs
    return obs, (cnt + 1) / (n_perm + 1)

def anova_f(groups_labels, values):
    labs = sorted(set(groups_labels)); v = np.asarray(values, float)
    if len(labs) < 2:
        return 0.0
    gm = v.mean(); ssb = 0; ssw = 0
    for l in labs:
        g = v[np.array(groups_labels) == l]
        ssb += len(g) * (g.mean() - gm) ** 2; ssw += ((g - g.mean()) ** 2).sum()
    dfb = len(labs) - 1; dfw = len(v) - len(labs)
    return float((ssb / dfb) / (ssw / dfw)) if ssw > 0 and dfw > 0 else 0.0

def perm_p_anova(labels, values, rng, n_perm=1000):
    obs = anova_f(labels, values); cnt = 0; labels = list(labels)
    for _ in range(n_perm):
        cnt += anova_f(list(rng.permutation(labels)), values) >= obs
    return obs, (cnt + 1) / (n_perm + 1)

def silhouette(D, labels):
    labels = np.asarray(labels); n = len(labels); s = np.zeros(n)
    for i in range(n):
        same = labels == labels[i]; same[i] = False
        if same.sum() == 0:
            s[i] = 0; continue
        a = D[i, same].mean()
        b = min(D[i, labels == l].mean() for l in set(labels) if l != labels[i])
        s[i] = (b - a) / max(a, b) if max(a, b) > 0 else 0
    return float(s.mean())

# ----------------------------------------------------------------------------- corpus loading
def load_corpus(name, root, roster, special, epoch_end=None):
    """Return acts list [(agent, type, time_utc|None, relpath)], side features, coverage info."""
    cov = {"name": name, "root": root}
    commons = os.path.join(root, "commons")
    files = []
    attr_mode = Counter()
    for r, _, fns in os.walk(commons):
        for fn in fns:
            if fn == ".DS_Store" or fn.endswith(".lock") or fn.endswith(".pyc") or "__pycache__" in r:
                continue
            full = os.path.join(r, fn)
            rel = os.path.relpath(full, commons)
            parts = rel.split(os.sep)
            if parts[0] not in SUBDIRS:
                continue
            files.append((full, parts))
    acts = []
    unattributed = 0
    for full, parts in files:
        a, mode = attribute(parts, full)
        attr_mode[mode] += 1
        if a is None:
            unattributed += 1
            continue
        b = parts[-1]
        if CORR_RE.search(b):
            t = "correct"
        elif VERIF_RE.search(b):
            t = "verify"
        else:
            t = SUBDIRS[parts[0]]
        acts.append((a, t, mtime_utc(full), "commons/" + "/".join(parts)))
    cov["commons_files_total"] = len(files)
    cov["commons_files_unattributed"] = unattributed
    cov["attribution_modes"] = dict(attr_mode)

    # board: infer bare-time offset from message<->file pairs
    board_rows = read_jsonl(os.path.join(root, "board", "messages.jsonl"))
    file_mtime = {rp: t for (_, _, t, rp) in acts}
    def deltas_for(off):
        d = []
        for m in board_rows:
            ts = m.get("time", "")
            if not isinstance(ts, str) or ts.endswith("Z") or re.search(r"[+-]\d\d:\d\d$", ts):
                continue
            t = parse_ts(ts, off)
            if t is None:
                continue
            for pth in PATH_RE.findall(str(m.get("message", ""))):
                if pth in file_mtime:
                    d.append(abs((t - file_mtime[pth]).total_seconds()) / 60)
        return d
    tz = {}
    for off in (0, -4, -7, 8):
        d = deltas_for(off)
        tz[str(off)] = {"n_pairs": len(d), "median_abs_min": float(np.median(d)) if d else None}
    cands = [(v["median_abs_min"], int(k)) for k, v in tz.items() if v["median_abs_min"] is not None]
    bare_off = min(cands)[1] if cands else -4
    cov["bare_time_offset_check"] = tz
    cov["bare_time_offset_chosen_h"] = bare_off

    n_board = 0
    for m in board_rows:
        frm = m.get("from", "")
        mm = AGENT_ANY.search(str(frm))
        if not mm:
            continue
        a = mm.group(1)
        txt = str(m.get("message", ""))[:300]
        if CORR_RE.search(txt):
            t = "correct"
        elif VERIF_MSG_RE.search(txt):
            t = "verify"
        else:
            t = "board"
        acts.append((a, t, parse_ts(m.get("time", ""), bare_off), "board/messages.jsonl"))
        n_board += 1
    cov["board_messages_total"] = len(board_rows)
    cov["board_messages_attributed"] = n_board

    # citations
    cit_rows = read_jsonl(os.path.join(root, "citations.jsonl")) + read_jsonl(os.path.join(root, "board", "citations.jsonl"))
    for c in cit_rows:  # gen2 post_citation tool writes 'artifact' instead of 'file'
        if not isinstance(c.get("file"), str) and isinstance(c.get("artifact"), str):
            c["file"] = c["artifact"]
    cit_real = [c for c in cit_rows if isinstance(c.get("file"), str) and (c["file"].startswith("commons/") or c["file"].startswith("agents/"))]
    cov["citations_raw"] = len(cit_rows); cov["citations_realfile"] = len(cit_real)
    cit_received = Counter(); tool_adopters = defaultdict(set); citers_of = defaultdict(set)
    for c in cit_real:
        citer = str(c.get("citer", "")); cited = str(c.get("cited", ""))
        if not AGENT_ANY.match(citer):
            continue
        acts.append((citer, "cite", parse_ts(c.get("time", ""), bare_off), c["file"]))
        if AGENT_ANY.match(cited) and cited != citer:
            cit_received[cited] += 1
            citers_of[cited].add(citer)
            if "commons/tools/" in c["file"]:
                tool_adopters[cited].add(citer)

    # registry appends (gen1 only)
    registry_acts = Counter()
    for fn in os.listdir(root):
        if fn.startswith("registry") and (fn.endswith(".jsonl") or fn.endswith(".json")) and "corrupt" not in fn:
            try:
                for line in open(os.path.join(root, fn), errors="ignore"):
                    for mm in re.finditer(r'"agent"\s*:\s*"(agent-\d{3,4})"', line):
                        registry_acts[mm.group(1)] += 1
            except OSError:
                pass
    rd = os.path.join(root, "registry.d")
    if os.path.isdir(rd):
        for fn in os.listdir(rd):
            mm = AGENT_RE.match(fn)
            if mm:
                registry_acts[mm.group(1)] += 1
    cov["has_registry"] = bool(registry_acts)

    # epoch filtering (gen1 late re-run)
    if epoch_end is not None:
        late = [x for x in acts if x[2] is not None and x[2] >= epoch_end]
        cov["acts_dropped_after_epoch_end"] = len(late)
        cov["late_epoch_agents"] = dict(Counter(x[0] for x in late))
        acts = [x for x in acts if not (x[2] is not None and x[2] >= epoch_end)]

    side = {"cit_received": cit_received, "tool_adopters": {a: len(s) for a, s in tool_adopters.items()},
            "distinct_citers": {a: len(s) for a, s in citers_of.items()}, "registry_acts": registry_acts}
    return acts, side, cov

# ----------------------------------------------------------------------------- per-corpus analysis
def analyze(name, acts, side, cov, roster, special, models, launch_index, rng):
    # %03d phantom fix (registry finding 19): agent-1NN written for roster agent-01NN
    remap = {}
    for a in {x[0] for x in acts}:
        m = re.match(r"^agent-(\d{3})$", a)
        if m and a not in roster and f"agent-0{m.group(1)}" in roster:
            remap[a] = f"agent-0{m.group(1)}"
    if remap:
        acts = [(remap.get(a, a), t, tm, rp) for (a, t, tm, rp) in acts]
        for key in ("cit_received", "tool_adopters", "distinct_citers", "registry_acts"):
            for src, dst in remap.items():
                if src in side[key]:
                    side[key][dst] = side[key].get(dst, 0) + side[key].pop(src)
    cov["phantom_id_remap"] = remap
    by_agent = defaultdict(list); by_agent_timed = defaultdict(list)
    for a, t, tm, rp in acts:
        by_agent[a].append(t)
        if tm is not None:
            by_agent_timed[a].append((tm, t, rp))
    all_authors = sorted(by_agent)
    seed_copy = set() if name == "gen1" else {f"agent-{i:03d}" for i in range(1, 37)}
    seed_copy_present = sorted(a for a in all_authors if a in seed_copy)
    ghosts = sorted(a for a in all_authors if a not in roster and a not in seed_copy)
    specials_present = sorted(a for a in all_authors if a in special)
    tiny = sorted(a for a in all_authors if a in roster and a not in special and len(by_agent[a]) < MIN_ACTS)
    included = sorted(a for a in all_authors if a in roster and a not in special and len(by_agent[a]) >= MIN_ACTS)
    roster_silent = sorted(a for a in roster if a not in by_agent)

    # ---- 1. profiles
    profiles = {}
    for a in all_authors:
        c = Counter(by_agent[a])
        subdir_counts = {}
        for (aa, t, tm, rp) in acts:
            if aa != a or not rp.startswith("commons/"):
                continue
            sd = rp.split("/")[1]
            subdir_counts[sd] = subdir_counts.get(sd, 0) + 1
        prof = {t: c.get(t, 0) for t in TYPES}
        n = sum(prof.values())
        profiles[a] = {
            "n_acts": n, "types": prof, "shares": {t: round(prof[t] / n, 4) for t in TYPES} if n else {},
            "commons_subdir_counts": subdir_counts,
            "citations_received": side["cit_received"].get(a, 0), "distinct_citers": side["distinct_citers"].get(a, 0),
            "tool_adopters": side["tool_adopters"].get(a, 0), "registry_acts": side["registry_acts"].get(a, 0),
            "norm_entropy": norm_entropy([prof[t] for t in TYPES]) if n else None,
            "herfindahl": herfindahl([prof[t] for t in TYPES]) if n else None,
            "dominant_type": max(prof, key=prof.get) if n else None,
            "status": ("ghost/out-of-roster" if a in ghosts else "seed-copy(001-036, excluded)" if a in seed_copy else "special(seed/adversary)" if a in special else
                       "excluded(<%d acts)" % MIN_ACTS if a in tiny else "included"),
            "model": models.get(a), "model_family": model_family(models.get(a)), "launch_index": launch_index.get(a),
            "first_act_utc": min(x[0] for x in by_agent_timed[a]).isoformat() if by_agent_timed[a] else None,
        }
    res = {"coverage": cov, "n_authors_seen": len(all_authors), "roster_size": len(roster),
           "included": included, "n_included": len(included), "excluded_tiny": tiny, "n_excluded_tiny": len(tiny),
           "specials_present": specials_present, "ghost_authors": ghosts, "roster_silent": roster_silent,
           "seed_copy_authors_present": seed_copy_present,
           "profiles": profiles}
    if len(included) < 4:
        res["note"] = "too few included agents"
        return res

    # ---- 2. specialization vs null
    M = profile_matrix(included, by_agent)
    obs = population_stats(M)
    null_sh = permutation_null(M, N_PERM, rng, "shuffle")
    null_mn = permutation_null(M, N_PERM, rng, "multinomial")
    per_agent_p = {}
    for i, a in enumerate(included):
        arr = null_sh["ent_per_agent"][:, i]
        per_agent_p[a] = float(((arr <= obs["entropies"][i]).sum() + 1) / (len(arr) + 1))
    n_sig = sum(1 for p in per_agent_p.values() if p < 0.05)
    n_sig_bonf = sum(1 for p in per_agent_p.values() if p < 0.05 / len(included))
    pooled = (M.sum(0) / M.sum()).tolist()
    strata = [model_family(models.get(a)) for a in included]
    null_st = stratified_null(M, strata, N_PERM, rng)
    fam_nmi = family_mi(M, strata)
    per_family = {}
    for g in sorted(set(strata)):
        idx = [i for i, x in enumerate(strata) if x == g]
        if len(idx) < 4:
            per_family[g] = {"n_agents": len(idx), "note": "too few agents"}; continue
        Mg = M[idx]; og = population_stats(Mg); ng = permutation_null(Mg, N_PERM, rng, "shuffle"); sg = null_summary(og, ng)
        per_family[g] = {"n_agents": len(idx), "n_acts": int(Mg.sum()),
                         "pooled_shares": {TYPES[j]: round(float(Mg.sum(0)[j] / Mg.sum()), 3) for j in range(K)},
                         "mean_norm_entropy": round(og["mean_norm_entropy"], 4), "entropy_null_mean": round(sg["mean_norm_entropy"]["null_mean"], 4),
                         "entropy_z": sg["mean_norm_entropy"]["z"], "entropy_p": sg["mean_norm_entropy"]["p_one_sided"],
                         "nmi": round(og["nmi_agent_type"], 4), "nmi_null_mean": round(sg["nmi_agent_type"]["null_mean"], 4),
                         "nmi_z": sg["nmi_agent_type"]["z"], "nmi_p": sg["nmi_agent_type"]["p_one_sided"],
                         "mean_pairwise_jsd": round(og["mean_pairwise_jsd"], 4), "jsd_null_mean": round(sg["mean_pairwise_jsd"]["null_mean"], 4), "jsd_z": sg["mean_pairwise_jsd"]["z"]}
    res["specialization_by_model_family"] = {
        "note": "family-stratified null shuffles type labels only among agents of the same model family; nmi_family_type is the share of type-information explained by family alone",
        "families": dict(Counter(strata)), "nmi_family_type": round(fam_nmi, 4),
        "nmi_agent_type": round(obs["nmi_agent_type"], 4),
        "fraction_of_agent_nmi_explained_by_family": round(fam_nmi / obs["nmi_agent_type"], 3) if obs["nmi_agent_type"] > 0 else None,
        "null_stratified_by_family": null_summary(obs, null_st),
        "per_family": per_family,
    }
    res["specialization"] = {
        "K_types": K, "types": TYPES, "n_acts_included": int(M.sum()), "pooled_shares": dict(zip(TYPES, [round(x, 4) for x in pooled])),
        "observed": {k: obs[k] for k in ("mean_norm_entropy", "mean_herfindahl", "nmi_agent_type", "mean_pairwise_jsd")},
        "null_shuffle_labels": null_summary(obs, null_sh), "null_multinomial_pooled": null_summary(obs, null_mn),
        "per_agent_entropy": {a: round(float(obs["entropies"][i]), 4) for i, a in enumerate(included)},
        "per_agent_p_vs_shuffle_null": {a: round(p, 4) for a, p in per_agent_p.items()},
        "n_agents_more_specialized_than_null_p05": n_sig, "n_agents_p05_bonferroni": n_sig_bonf,
        "entropy_vs_nacts_spearman": spearman([profiles[a]["n_acts"] for a in included], [obs["entropies"][i] for i in range(len(included))]),
    }

    # ---- 3. temporal
    tercile_rows = {}
    diffs = []
    for a in included:
        ev = sorted(by_agent_timed[a])
        if len(ev) < 15:
            continue
        n = len(ev); cuts = [0, n // 3, 2 * n // 3, n]
        hs = []
        for j in range(3):
            seg = [t for (_, t, _) in ev[cuts[j]:cuts[j + 1]]]
            hs.append(norm_entropy([seg.count(t) for t in TYPES]))
        tercile_rows[a] = [round(h, 4) for h in hs]
        diffs.append(hs[2] - hs[0])
    diffs = np.array(diffs)
    boot = []
    if len(diffs) >= 3:
        for _ in range(N_PERM):
            boot.append(float(rng.choice(diffs, len(diffs), replace=True).mean()))
    temporal = {
        "per_agent_terciles_norm_entropy": tercile_rows, "n_agents_with_ge15_timed_acts": len(tercile_rows),
        "mean_entropy_by_tercile": [round(float(np.mean([v[j] for v in tercile_rows.values()])), 4) for j in range(3)] if tercile_rows else None,
        "late_minus_early_mean": float(diffs.mean()) if len(diffs) else None,
        "late_minus_early_boot95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))] if boot else None,
        "n_entropy_down_late_vs_early": int((diffs < 0).sum()), "n_entropy_up": int((diffs > 0).sum()),
        "n_entropy_same": int((diffs == 0).sum()),
    }
    # global windows: divergence over run time
    timed = [(tm, a, t) for a in included for (tm, t, _) in by_agent_timed[a]]
    timed.sort()
    if timed:
        t0 = timed[0][0]; t1 = timed[-1][0]
        span_h = (t1 - t0).total_seconds() / 3600
        qs = np.quantile([(x[0] - t0).total_seconds() for x in timed], [1 / 3, 2 / 3])
        windows = []
        for j in range(3):
            lo = 0 if j == 0 else qs[j - 1]; hi = qs[j] if j < 2 else float("inf")
            seg = [x for x in timed if lo <= (x[0] - t0).total_seconds() < hi] if j < 2 else [x for x in timed if (x[0] - t0).total_seconds() >= lo]
            ba = defaultdict(list)
            for _, a, t in seg:
                ba[a].append(t)
            ag = sorted(a for a in ba if len(ba[a]) >= MIN_ACTS)
            if len(ag) < 4:
                windows.append({"window": j, "n_agents": len(ag), "note": "too few agents"}); continue
            Mw = profile_matrix(ag, ba); ow = population_stats(Mw)
            nw = permutation_null(Mw, 300, rng, "shuffle")
            sm = null_summary(ow, nw)
            windows.append({"window": j, "n_agents": len(ag), "n_acts": int(Mw.sum()),
                            "start_h": round(float(lo / 3600), 2), "end_h": round(float(hi / 3600), 2) if hi != float("inf") else round(span_h, 2),
                            "mean_norm_entropy": round(ow["mean_norm_entropy"], 4), "entropy_null_mean": round(sm["mean_norm_entropy"]["null_mean"], 4),
                            "entropy_z": sm["mean_norm_entropy"]["z"],
                            "nmi": round(ow["nmi_agent_type"], 4), "nmi_null_mean": round(sm["nmi_agent_type"]["null_mean"], 4), "nmi_z": sm["nmi_agent_type"]["z"],
                            "mean_pairwise_jsd": round(ow["mean_pairwise_jsd"], 4), "jsd_null_mean": round(sm["mean_pairwise_jsd"]["null_mean"], 4), "jsd_z": sm["mean_pairwise_jsd"]["z"]})
        temporal["global_windows"] = windows
        temporal["run_start_utc"] = t0.isoformat(); temporal["run_end_utc"] = t1.isoformat(); temporal["span_hours"] = round(span_h, 1)
    # niche persistence: is an agent's early-half profile closer to its own late-half than to other agents' late halves?
    halves = {}
    for a in included:
        ev = sorted(by_agent_timed[a])
        if len(ev) < 20:
            continue
        h = len(ev) // 2
        c1 = Counter(t for (_, t, _) in ev[:h]); c2 = Counter(t for (_, t, _) in ev[h:])
        halves[a] = (np.array([c1.get(t, 0) for t in TYPES], float) + 0.5, np.array([c2.get(t, 0) for t in TYPES], float) + 0.5)
    pers_rows = {}
    for a, (p1, p2) in halves.items():
        own = jsd(p1, p2)
        others = [jsd(p1, halves[b][1]) for b in halves if b != a]
        same_fam = [jsd(p1, halves[b][1]) for b in halves if b != a and profiles[b]["model_family"] == profiles[a]["model_family"]]
        pers_rows[a] = {"own_jsd": round(own, 4), "median_cross_jsd": round(float(np.median(others)), 4) if others else None,
                        "median_cross_jsd_same_family": round(float(np.median(same_fam)), 4) if same_fam else None,
                        "rank_of_own_among_cross": int(sum(1 for o in others if o < own))}
    n_p = len(pers_rows)
    temporal["niche_persistence"] = {
        "method": "split each agent's timed acts in half (by time); JSD(own early, own late) vs JSD(own early, other agent's late); +0.5 pseudocount",
        "n_agents_ge20_timed_acts": n_p,
        "n_own_closer_than_median_cross": sum(1 for v in pers_rows.values() if v["median_cross_jsd"] is not None and v["own_jsd"] < v["median_cross_jsd"]),
        "n_own_closer_than_median_cross_same_family": sum(1 for v in pers_rows.values() if v["median_cross_jsd_same_family"] is not None and v["own_jsd"] < v["median_cross_jsd_same_family"]),
        "n_with_same_family_comparison": sum(1 for v in pers_rows.values() if v["median_cross_jsd_same_family"] is not None),
        "mean_own_jsd": round(float(np.mean([v["own_jsd"] for v in pers_rows.values()])), 4) if n_p else None,
        "mean_median_cross_jsd": round(float(np.mean([v["median_cross_jsd"] for v in pers_rows.values() if v["median_cross_jsd"] is not None])), 4) if n_p else None,
        "n_own_is_nearest_of_all(rank0)": sum(1 for v in pers_rows.values() if v["rank_of_own_among_cross"] == 0),
        "per_agent": pers_rows,
    }
    res["temporal"] = temporal

    # ---- 4. clustering
    P = M / M.sum(1)[:, None]
    inter = np.array([[math.log1p(profiles[a]["citations_received"] / max(profiles[a]["n_acts"], 1)),
                       math.log1p(profiles[a]["tool_adopters"]),
                       math.log1p(profiles[a]["n_acts"])] for a in included])
    X = np.hstack([P, inter])
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-9)
    D = squareform(pdist(Xs, "euclidean"))
    Z = linkage(Xs, "ward")
    best = None
    sil = {}
    for k in range(2, min(7, len(included) - 1)):
        lab = fcluster(Z, k, "maxclust")
        s = silhouette(D, lab); sil[k] = round(s, 4)
        if best is None or s > best[0]:
            best = (s, k, lab)
    s, kbest, lab = best
    clusters = []
    pooled_arr = np.array(pooled)
    for c in sorted(set(lab)):
        idx = [i for i in range(len(included)) if lab[i] == c]
        mean_share = P[idx].mean(0)
        enrich = {TYPES[j]: round(float(mean_share[j] / pooled_arr[j]), 2) if pooled_arr[j] > 0 else None for j in range(K)}
        top = sorted([(enrich[t], t) for t in TYPES if enrich[t] is not None and enrich[t] >= 1.3 and mean_share[TIDX[t]] >= 0.08], reverse=True)
        members = sorted(idx, key=lambda i: -profiles[included[i]]["n_acts"])
        clusters.append({"cluster": int(c), "n": len(idx), "label": label_for(top, mean_share),
                         "enriched_types": [t for _, t in top], "mean_shares": {TYPES[j]: round(float(mean_share[j]), 3) for j in range(K)},
                         "mean_norm_entropy": round(float(np.mean([obs['entropies'][i] for i in idx])), 4),
                         "mean_n_acts": round(float(np.mean([profiles[included[i]]['n_acts'] for i in idx])), 1),
                         "mean_cit_received": round(float(np.mean([profiles[included[i]]['citations_received'] for i in idx])), 1),
                         "members": [included[i] for i in members],
                         "examples": [included[i] for i in members[:3]],
                         "model_families": dict(Counter(profiles[included[i]]["model_family"] for i in idx))})
    lab_list = [int(x) for x in lab]
    fam = [profiles[a]["model_family"] for a in included]
    mod = [profiles[a]["model"] or "?" for a in included]
    li = [profiles[a]["launch_index"] or 0 for a in included]
    ft = [datetime.fromisoformat(profiles[a]["first_act_utc"]).timestamp() if profiles[a]["first_act_utc"] else 0 for a in included]
    na = [profiles[a]["n_acts"] for a in included]
    v_fam, p_fam = perm_p_cramers(lab_list, fam, rng)
    v_mod, p_mod = perm_p_cramers(lab_list, mod, rng)
    f_li, p_li = perm_p_anova(lab_list, li, rng)
    f_ft, p_ft = perm_p_anova(lab_list, ft, rng)
    f_na, p_na = perm_p_anova(lab_list, [math.log1p(x) for x in na], rng)
    xtab = {}
    for c in sorted(set(lab_list)):
        xtab[str(c)] = dict(Counter(fam[i] for i in range(len(included)) if lab_list[i] == c))
    res["clustering"] = {
        "cluster_x_model_family": xtab,
        "method": "Ward hierarchical on z-scored [9 type shares + log1p(cit_received/act) + log1p(tool_adopters) + log1p(n_acts)]; k by silhouette",
        "silhouette_by_k": sil, "k": int(kbest), "silhouette": round(float(s), 4), "clusters": clusters,
        "assignments": dict(zip(included, lab_list)),
        "confounds": {"model_family_cramers_v": round(v_fam, 3), "model_family_perm_p": round(p_fam, 4),
                      "model_config_cramers_v": round(v_mod, 3), "model_config_perm_p": round(p_mod, 4),
                      "launch_index_anova_F": round(f_li, 3), "launch_index_perm_p": round(p_li, 4),
                      "first_act_time_anova_F": round(f_ft, 3), "first_act_time_perm_p": round(p_ft, 4),
                      "log_n_acts_anova_F": round(f_na, 3), "log_n_acts_perm_p": round(p_na, 4)},
    }
    # 'niche' via dominant enriched type per agent (for cross-machine comparison)
    niche = {}
    for i, a in enumerate(included):
        ratio = P[i] / np.where(pooled_arr > 0, pooled_arr, 1)
        j = int(np.argmax(ratio))
        niche[a] = TYPES[j] if P[i, j] >= 0.15 else "generalist"
    res["niche_by_enrichment"] = niche
    res["niche_counts"] = dict(Counter(niche.values()))
    # examples: top-3 specialists by (1 - entropy), with paths
    ex = []
    for i in np.argsort(obs["entropies"])[:5]:
        a = included[i]
        dom = profiles[a]["dominant_type"]
        own = {t: n for t, n in profiles[a]["types"].items() if t not in ("board", "cite")}
        dom_own = max(own, key=own.get) if any(own.values()) else None
        paths = []
        for (tm, t, rp) in sorted(by_agent_timed[a]):
            if t == dom_own and rp.startswith("commons/") and rp not in paths:
                paths.append(rp)
        ex.append({"agent": a, "norm_entropy": round(float(obs["entropies"][i]), 4), "n_acts": profiles[a]["n_acts"],
                   "dominant_type": dom, "dominant_own_artifact_type": dom_own, "shares": profiles[a]["shares"],
                   "model": profiles[a]["model"], "example_paths": [os.path.join(cov["root"], p) for p in paths[:3]]})
    res["most_specialized_examples"] = ex
    return res

def label_for(top, mean_share):
    names = {"finding": "finding-producers", "tool": "tool-builders", "build": "app/dashboard-builders",
             "challenge": "challenge-setters", "data": "data-curators", "verify": "verifiers/auditors",
             "correct": "correctors", "board": "board-coordinators", "cite": "integrators/citers"}
    if not top:
        return "generalists (near pooled profile)"
    return " + ".join(names[t] for _, t in top[:2])

def spearman(x, y):
    from scipy.stats import spearmanr
    r, p = spearmanr(x, y)
    return {"rho": round(float(r), 3), "p": round(float(p), 4)}

# ----------------------------------------------------------------------------- main
def main():
    rng = np.random.default_rng(RNG_SEED)
    results = {"meta": {"generated_utc": datetime.now(UTC).isoformat(), "n_perm": N_PERM, "min_acts": MIN_ACTS, "types": TYPES,
                        "regex": {"correct": CORR_RE.pattern, "verify_file": VERIF_RE.pattern, "verify_msg": VERIF_MSG_RE.pattern}}}
    # gen1
    root1 = os.path.join(HOME, "swarm")
    roster1 = {f"agent-{i:03d}" for i in range(1, 37)}
    special1 = {f"agent-{i:03d}": "seed" for i in GEN1_SEEDS}
    special1.update({f"agent-{i:03d}": "adversary:" + n for i, n in W1_ADV.items()})
    acts, side, cov = load_corpus("gen1", root1, roster1, special1, epoch_end=datetime(2026, 8, 10, tzinfo=UTC))
    cov["prompt_note"] = "swarm_launcher.py: identical prompt for all 36 (Chinese, three laws, '你没有任务'); seeds 005/017/029 got SEED_EXTRA; monitor wake-up every 900s"
    cov["special_agents"] = special1
    results["gen1"] = analyze("gen1", acts, side, cov, roster1, special1, GEN1_MODELS,
                              {a: int(a[-3:]) for a in roster1}, rng)

    # gen2
    gen2 = {}
    all_g2 = {}
    for m in ["122174", "122175", "122447", "122448", "122456"]:
        root = os.path.join(HOME, "swarm-gen2", m, "swarm")
        sess_p = os.path.join(root, "devbox_sessions.json")
        if not os.path.isfile(sess_p):
            gen2[m] = {"excluded": True, "reason": "no devbox_sessions.json; no board/citations; 0 tools; no native gen2 output"}
            continue
        sess = json.load(open(sess_p))
        roster = sorted({x["id"] for x in sess})
        models = {}
        for x in sess:
            models.setdefault(x["id"], x.get("model"))
        launch_index = {a: int(a.split("-")[1]) for a in roster}
        special = {}
        for a in roster:
            i = launch_index[a]
            if i in W1_SEEDS or i in W2_SEEDS:
                special[a] = "seed"
            if i in W1_ADV:
                special[a] = "adversary:" + W1_ADV[i]
            if i in W2_ADV:
                special[a] = "adversary:" + W2_ADV[i]
        acts, side, cov = load_corpus(m, root, set(roster), special)
        cov["special_agents"] = special
        cov["n_sessions_rows"] = len(sess); cov["n_roster"] = len(roster); cov["n_restarts(dup session rows)"] = len(sess) - len(roster)
        cov["prompt_note"] = "devbox_runner.py build_system_prompt: English, three laws, reaper every 30 min, 'find your niche', 'Cite generously'; seeds get a private cooperation directive; adversaries get covert directive"
        r = analyze(m, acts, side, cov, set(roster), special, models, launch_index, rng)
        gen2[m] = r
        if "clustering" in r:
            all_g2[m] = (acts, side, r)
    results["gen2"] = gen2

    # cross-machine replication: pooled clustering of all included native gen2 agents
    if len(all_g2) >= 2:
        pooled_agents = []; by_agent = defaultdict(list); machine_of = {}; prof = {}
        for m, (acts, side, r) in all_g2.items():
            for a in r["included"]:
                key = f"{m}:{a}"
                pooled_agents.append(key); machine_of[key] = m; prof[key] = r["profiles"][a]
            for (a, t, tm, rp) in acts:
                if a in r["included"]:
                    by_agent[f"{m}:{a}"].append(t)
        M = profile_matrix(pooled_agents, by_agent)
        P = M / M.sum(1)[:, None]
        pooled = M.sum(0) / M.sum()
        inter = np.array([[math.log1p(prof[a]["citations_received"] / max(prof[a]["n_acts"], 1)), math.log1p(prof[a]["tool_adopters"]), math.log1p(prof[a]["n_acts"])] for a in pooled_agents])
        X = np.hstack([P, inter]); Xs = (X - X.mean(0)) / (X.std(0) + 1e-9)
        D = squareform(pdist(Xs)); Z = linkage(Xs, "ward")
        best = None; sil = {}
        for k in range(2, 7):
            lab = fcluster(Z, k, "maxclust"); s = silhouette(D, lab); sil[k] = round(s, 4)
            if best is None or s > best[0]:
                best = (s, k, lab)
        s, kbest, lab = best
        clusters = []
        for c in sorted(set(lab)):
            idx = [i for i in range(len(pooled_agents)) if lab[i] == c]
            ms = P[idx].mean(0)
            enrich = {TYPES[j]: round(float(ms[j] / pooled[j]), 2) if pooled[j] > 0 else None for j in range(K)}
            top = sorted([(enrich[t], t) for t in TYPES if enrich[t] is not None and enrich[t] >= 1.3 and ms[TIDX[t]] >= 0.08], reverse=True)
            clusters.append({"cluster": int(c), "n": len(idx), "label": label_for(top, ms), "enriched_types": [t for _, t in top],
                             "machines": dict(Counter(machine_of[pooled_agents[i]] for i in idx)),
                             "n_machines": len(set(machine_of[pooled_agents[i]] for i in idx)),
                             "model_families": dict(Counter(prof[pooled_agents[i]]["model_family"] for i in idx)),
                             "mean_shares": {TYPES[j]: round(float(ms[j]), 3) for j in range(K)},
                             "examples": [pooled_agents[i] for i in sorted(idx, key=lambda i: -prof[pooled_agents[i]]["n_acts"])[:3]]})
        v, p = perm_p_cramers([int(x) for x in lab], [machine_of[a] for a in pooled_agents], rng)
        v_f = cramers_v([int(x) for x in lab], [prof[a]["model_family"] for a in pooled_agents])
        # niche label recurrence across machines
        niche_by_machine = {m: r["niche_counts"] for m, (_, _, r) in all_g2.items()}
        recur = {}
        for t in TYPES + ["generalist"]:
            recur[t] = sum(1 for m in niche_by_machine if niche_by_machine[m].get(t, 0) >= 2)
        # per-machine null verdicts side by side
        verdicts = {m: {"n_included": r["n_included"],
                        "mean_entropy_obs": round(r["specialization"]["observed"]["mean_norm_entropy"], 4),
                        "mean_entropy_null": round(r["specialization"]["null_shuffle_labels"]["mean_norm_entropy"]["null_mean"], 4),
                        "entropy_z": r["specialization"]["null_shuffle_labels"]["mean_norm_entropy"]["z"],
                        "nmi_obs": round(r["specialization"]["observed"]["nmi_agent_type"], 4),
                        "nmi_z": r["specialization"]["null_shuffle_labels"]["nmi_agent_type"]["z"],
                        "n_sig_agents": r["specialization"]["n_agents_more_specialized_than_null_p05"],
                        "cluster_labels": [c["label"] for c in r["clustering"]["clusters"]]}
                    for m, (_, _, r) in all_g2.items()}
        results["gen2_cross_machine"] = {"n_machines": len(all_g2), "n_agents_pooled": len(pooled_agents), "silhouette_by_k": sil, "k": int(kbest),
                                         "silhouette": round(float(s), 4), "clusters": clusters,
                                         "cluster_x_machine_cramers_v": round(v, 3), "cluster_x_machine_perm_p": round(p, 4),
                                         "cluster_x_model_family_cramers_v": round(v_f, 3),
                                         "niche_counts_by_machine": niche_by_machine,
                                         "niche_recurs_in_n_machines(>=2 agents)": recur, "per_machine_verdicts": verdicts}

    # self-declared roles (gen1 registry)
    roles = Counter()
    for fn in os.listdir(root1):
        if fn.startswith("registry") and "corrupt" not in fn:
            try:
                txt = open(os.path.join(root1, fn), errors="ignore").read()
            except OSError:
                continue
            for mm in re.finditer(r'"agent"\s*:\s*"(agent-\d{3})"[^\n]*?"role"\s*:\s*"([^"]{0,120})"', txt):
                roles[(mm.group(1), mm.group(2))] += 1
    results["gen1"]["self_declared_roles_in_registry"] = [{"agent": a, "role": r, "n": n} for (a, r), n in sorted(roles.items())]

    results["confounds"] = [
        "gen1 monitor (swarm_monitor.py INTERVAL=900) wakes idle agents every 15 min with a fixed nudge; gen2 reaper every 30 min",
        "seeds (gen1 005/017/029; gen2 W1 38,45,52,...; W2 every 50th from 105) and adversaries (42,51,59,67,74,83; 150,...) excluded from stats",
        "gen1 has a second epoch on 2026-08-31/09-01 (agents 005/006/007/001 re-run); dropped via epoch_end=2026-08-10",
        "gen2 prompt literally says 'find your niche' and 'Cite generously' — niche-seeking is prompt-induced there; gen1 prompt has no such wording",
        "gen2 machines start from a copy of gen1 commons: native agents see gen1 specialists' outputs (cultural transmission), so machines are not independent of gen1",
        "agents with < %d acts excluded; ghost/out-of-roster ids (gen1 agent-042 expansion Saboteur; gen2 e.g. agent-109) excluded; agent-140 phantom from %%03d bug noted in registry" % MIN_ACTS,
        "resurrection = fork (35/36 gen1 agents had un-terminated predecessors — registry finding 6, flagged there as not independently verified); duplicate publications inflate counts for some agents",
        "9 model configs in gen1 (3 families x 3 reasoning levels) / 3 families in gen2 — cluster-vs-model tests reported",
        "files under agent-named challenge arenas without their own prefix are attributed to the arena owner (dir attribution)",
        "'verify'/'correct' detected by filename/message regex only; counts are lower bounds and miss body-text-only acts",
        "entropy depends on n_acts (small n -> lower entropy mechanically); the label-shuffle null preserves each agent's n, and Spearman(n_acts, entropy) is reported",
    ]
    out = os.path.join(OUT_DIR, "swarm_role_diff_results.json")
    json.dump(results, open(out, "w"), ensure_ascii=False, indent=1, default=str)
    print("wrote", out)
    # console summary
    for name, r in [("gen1", results["gen1"])] + [(m, results["gen2"][m]) for m in results["gen2"]]:
        if "specialization" not in r:
            print(name, "->", r.get("reason") or r.get("note")); continue
        sp = r["specialization"]; ns = sp["null_shuffle_labels"]
        print(f"{name}: included={r['n_included']} tiny={r['n_excluded_tiny']} acts={sp['n_acts_included']} "
              f"H={sp['observed']['mean_norm_entropy']:.3f} null={ns['mean_norm_entropy']['null_mean']:.3f} z={ns['mean_norm_entropy']['z']:.1f} "
              f"NMI={sp['observed']['nmi_agent_type']:.3f} null={ns['nmi_agent_type']['null_mean']:.3f} z={ns['nmi_agent_type']['z']:.1f} "
              f"sig_agents={sp['n_agents_more_specialized_than_null_p05']}/{r['n_included']} k={r['clustering']['k']} sil={r['clustering']['silhouette']}")
        st = r["specialization_by_model_family"]; nn = st["null_stratified_by_family"]
        print(f"    family NMI={st['nmi_family_type']:.3f} ({st['fraction_of_agent_nmi_explained_by_family']} of agent NMI); stratified null: "
              f"H null={nn['mean_norm_entropy']['null_mean']:.3f} z={nn['mean_norm_entropy']['z']:.1f} NMI null={nn['nmi_agent_type']['null_mean']:.3f} z={nn['nmi_agent_type']['z']:.1f}")
        for g, v in st["per_family"].items():
            print("      fam", g, v.get("n_agents"), "H", v.get("mean_norm_entropy"), "null", v.get("entropy_null_mean"), "z", v.get("entropy_z"), "NMI", v.get("nmi"), "z", v.get("nmi_z"))
        for c in r["clustering"]["clusters"]:
            print("   ", c["n"], c["label"], c["examples"], c["model_families"])
        print("    temporal terciles:", r["temporal"]["mean_entropy_by_tercile"], "late-early", r["temporal"]["late_minus_early_mean"], r["temporal"]["late_minus_early_boot95"])
        print("    windows:", [(w.get("nmi"), w.get("nmi_z")) for w in r["temporal"].get("global_windows", [])])
        print("    confounds:", r["clustering"]["confounds"])
    if "gen2_cross_machine" in results:
        x = results["gen2_cross_machine"]
        print("cross-machine: k=", x["k"], "sil", x["silhouette"], "V(cluster,machine)=", x["cluster_x_machine_cramers_v"], "p", x["cluster_x_machine_perm_p"])
        for c in x["clusters"]:
            print("   ", c["n"], c["label"], c["machines"])
        print("   niche recurrence:", x["niche_recurs_in_n_machines(>=2 agents)"])

if __name__ == "__main__":
    main()
