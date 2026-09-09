#!/usr/bin/env python3
"""
Two zero-cost analyses on the gen1 swarm corpus (LOCAL, read-only on ~/Downloads/swarm; writes only to ~/Downloads/swarm-iclr).

Analysis 1  SwarmWorld-style role states (arXiv 2608.26081, pipeline steps 1-11 as summarised in lit_batch3.md §1(c)),
            adapted to a filesystem society: per-agent-per-window feature rows -> log1p -> RobustScaler(5,95) -> clip ±10 ->
            k-means (n_init=32) k=2..6 by silhouette -> hierarchical split of k=2 into <=4 states -> occupancy per window,
            switching rate, leave-agent-out ARI, column-shuffle silhouette null, states x model family, within-window entropy
            (phase vs division of labour).
Analysis 2  3x3 factorial (family x reasoning level) cell profiles + two-way permutation ANOVA (Freedman-Lane, type II).

Act extraction is IMPORTED from swarm_role_diff.py (same attribution rules, regexes, time discipline, exclusions) and the
augmented act table is asserted equal to swarm_role_diff.load_corpus() output, so the act tables match the earlier probe.
"""
import os, sys, re, json, math
from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone
import numpy as np
from scipy.spatial.distance import pdist, squareform

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swarm_role_diff as srd  # act-extraction code reused, not rewritten

HOME = os.path.expanduser("~/Downloads")
ROOT = os.path.join(HOME, "swarm")
OUT_DIR = os.path.join(HOME, "swarm-iclr")
OUT_JSON = os.path.join(OUT_DIR, "swarm_states_3x3_results.json")
UTC = timezone.utc
RNG_SEED = 20260907
EPOCH_END = datetime(2026, 8, 10, tzinfo=UTC)
WINDOW_H = 2.0
MIN_ACTS_ROW = 3          # agent-window rows with fewer acts are not clustered (reported)
N_INIT = 32
N_PERM = 1000
N_SIL_NULL = 200
TYPES = srd.TYPES
K = srd.K
EXCLUDED = {"agent-005", "agent-017", "agent-029", "agent-042"}
ROSTER = {f"agent-{i:03d}" for i in range(1, 37)}
SPECIAL = {f"agent-{i:03d}": "seed" for i in srd.GEN1_SEEDS}
SPECIAL.update({f"agent-{i:03d}": "adversary:" + n for i, n in srd.W1_ADV.items()})

AGENT_ANY = srd.AGENT_ANY
PATH_ANY = re.compile(r"commons/(?:tools|findings|data|challenges|builds)/((agent-\d{3,4})[\w\-.]*\.\w+)")

def level_of(model):
    """Reasoning level from the model config string: 3 = highest tier, 1 = no explicit reasoning."""
    m = model.lower()
    if "xhigh" in m or "thinking_max" in m or "reasoning-high" in m:
        return 3
    if "reasoning_high" in m or "thinking" in m or "reasoning" in m:
        return 2
    return 1

LEVEL_NAME = {3: "L3(max)", 2: "L2(mid)", 1: "L1(none)"}
FAMILIES = ["sol", "orange", "seed"]

# ----------------------------------------------------------------------------- augmented act table
def load_acts_augmented():
    """Mirror srd.load_corpus for gen1, but keep per-act extras:
       file acts: size, other agents referenced in content, other agents' artifact paths referenced
       board acts: addressee, agents mentioned, other agents' paths mentioned
       cite acts: cited agent (from citation row)
       Returns list of dicts and the srd coverage dict; asserts equality with srd.load_corpus acts."""
    ref_acts, ref_side, cov = srd.load_corpus("gen1", ROOT, ROSTER, SPECIAL, epoch_end=EPOCH_END)
    bare_off = cov["bare_time_offset_chosen_h"]
    commons = os.path.join(ROOT, "commons")
    acts = []
    for r, _, fns in os.walk(commons):
        for fn in fns:
            if fn == ".DS_Store" or fn.endswith(".lock") or fn.endswith(".pyc") or "__pycache__" in r:
                continue
            full = os.path.join(r, fn)
            rel = os.path.relpath(full, commons)
            parts = rel.split(os.sep)
            if parts[0] not in srd.SUBDIRS:
                continue
            a, mode = srd.attribute(parts, full)
            if a is None:
                continue
            b = parts[-1]
            if srd.CORR_RE.search(b):
                t = "correct"
            elif srd.VERIF_RE.search(b):
                t = "verify"
            else:
                t = srd.SUBDIRS[parts[0]]
            size = os.path.getsize(full)
            others, other_paths = set(), set()
            try:
                if size <= 2_000_000:
                    txt = open(full, errors="ignore").read(300_000)
                    for mm in AGENT_ANY.finditer(txt):
                        if mm.group(1) != a and mm.group(1) in ROSTER:
                            others.add(mm.group(1))
                    for mm in PATH_ANY.finditer(txt):
                        if mm.group(2) != a and mm.group(2) in ROSTER:
                            other_paths.add(mm.group(2))
            except OSError:
                pass
            acts.append({"agent": a, "type": t, "time": srd.mtime_utc(full), "path": "commons/" + "/".join(parts),
                         "kind": "file", "size": size, "others": others, "other_paths": other_paths, "addressee": None})
    board_rows = srd.read_jsonl(os.path.join(ROOT, "board", "messages.jsonl"))
    for m in board_rows:
        mm = AGENT_ANY.search(str(m.get("from", "")))
        if not mm:
            continue
        a = mm.group(1)
        msg = str(m.get("message", ""))
        txt = msg[:300]
        if srd.CORR_RE.search(txt):
            t = "correct"
        elif srd.VERIF_MSG_RE.search(txt):
            t = "verify"
        else:
            t = "board"
        to = str(m.get("to", "all"))
        tm = AGENT_ANY.search(to)
        addressee = tm.group(1) if tm and tm.group(1) != a and tm.group(1) in ROSTER else None
        others = {x.group(1) for x in AGENT_ANY.finditer(msg) if x.group(1) != a and x.group(1) in ROSTER}
        if addressee:
            others.add(addressee)
        other_paths = {x.group(2) for x in PATH_ANY.finditer(msg) if x.group(2) != a and x.group(2) in ROSTER}
        acts.append({"agent": a, "type": t, "time": srd.parse_ts(m.get("time", ""), bare_off), "path": "board/messages.jsonl",
                     "kind": "board", "size": len(msg), "others": others, "other_paths": other_paths, "addressee": addressee})
    cit_rows = srd.read_jsonl(os.path.join(ROOT, "citations.jsonl")) + srd.read_jsonl(os.path.join(ROOT, "board", "citations.jsonl"))
    for c in cit_rows:
        if not isinstance(c.get("file"), str) and isinstance(c.get("artifact"), str):
            c["file"] = c["artifact"]
    cit_real = [c for c in cit_rows if isinstance(c.get("file"), str) and (c["file"].startswith("commons/") or c["file"].startswith("agents/"))]
    for c in cit_real:
        citer = str(c.get("citer", "")); cited = str(c.get("cited", ""))
        if not AGENT_ANY.match(citer):
            continue
        cited_ok = AGENT_ANY.match(cited) is not None and cited != citer
        acts.append({"agent": citer, "type": "cite", "time": srd.parse_ts(c.get("time", ""), bare_off), "path": c["file"],
                     "kind": "cite", "size": None, "others": {cited} if cited_ok else set(),
                     "other_paths": {cited} if cited_ok else set(), "addressee": None, "cited": cited if cited_ok else None,
                     "tool_cite": "commons/tools/" in c["file"]})
    acts = [x for x in acts if not (x["time"] is not None and x["time"] >= EPOCH_END)]
    # equality check against the probe's act table
    mine = sorted((x["agent"], x["type"], x["time"].isoformat() if x["time"] else None, x["path"]) for x in acts)
    ref = sorted((a, t, tm.isoformat() if tm else None, rp) for (a, t, tm, rp) in ref_acts)
    assert mine == ref, f"act table mismatch: {len(mine)} vs {len(ref)}"
    return acts, ref_side, cov

# ----------------------------------------------------------------------------- feature construction
FEATURES = [("r_" + t) for t in TYPES] + [
    "cites_given_other", "cites_received", "distinct_cited", "distinct_citers", "tool_adopters",
    "frac_on_others", "frac_new_artifact", "mean_log_size", "proximity", "n_other_agents"]
FILE_ONLY_FEATURES = [("r_" + t) for t in ("finding", "tool", "build", "challenge", "data", "verify", "correct")] + \
                     ["frac_new_artifact", "mean_log_size"]
LOG_FEATURES = {f for f in FEATURES if f.startswith("r_") or f in ("cites_given_other", "cites_received", "distinct_cited", "distinct_citers", "tool_adopters", "n_other_agents")}

def feature_row(agent, own, received_in_window, hours):
    """own = list of act dicts by `agent` in the window; received_in_window = list of cite act dicts by others citing `agent`."""
    n = len(own)
    c = Counter(x["type"] for x in own)
    f = {}
    for t in TYPES:
        f["r_" + t] = c.get(t, 0) / hours
    cites_other = [x for x in own if x["kind"] == "cite" and x.get("cited")]
    f["cites_given_other"] = len(cites_other)
    f["cites_received"] = len(received_in_window)
    f["distinct_cited"] = len({x["cited"] for x in cites_other})
    f["distinct_citers"] = len({x["agent"] for x in received_in_window})
    f["tool_adopters"] = len({x["agent"] for x in received_in_window if x.get("tool_cite")})
    on_others = [x for x in own if x["others"] or x["addressee"]]
    f["frac_on_others"] = len(on_others) / n if n else float("nan")
    f["frac_new_artifact"] = sum(1 for x in own if x["kind"] == "file") / n if n else float("nan")
    sizes = [math.log1p(x["size"]) for x in own if x["kind"] == "file" and x["size"] is not None]
    f["mean_log_size"] = float(np.mean(sizes)) if sizes else float("nan")
    prox = [x for x in own if x["other_paths"]]
    f["proximity"] = len(prox) / n if n else float("nan")
    f["n_other_agents"] = len(set().union(*[x["others"] for x in own]) if own else set())
    return f

def build_rows(acts, included, t0, n_windows):
    timed = [x for x in acts if x["time"] is not None and x["agent"] in included]
    win_of = lambda x: int((x["time"] - t0).total_seconds() // (WINDOW_H * 3600))
    by_aw = defaultdict(list); recv = defaultdict(list)
    for x in timed:
        w = win_of(x)
        if 0 <= w < n_windows:
            by_aw[(x["agent"], w)].append(x)
            if x["kind"] == "cite" and x.get("cited") in included:
                recv[(x["cited"], w)].append(x)
    rows, meta, small = [], [], 0
    for (a, w), own in sorted(by_aw.items()):
        if len(own) < MIN_ACTS_ROW:
            small += 1; continue
        rows.append(feature_row(a, own, recv.get((a, w), []), WINDOW_H))
        meta.append({"agent": a, "window": w, "n_acts": len(own)})
    # whole-run rows
    whole_rows, whole_meta = [], []
    by_a = defaultdict(list); recv_a = defaultdict(list)
    for x in timed:
        by_a[x["agent"]].append(x)
        if x["kind"] == "cite" and x.get("cited") in included:
            recv_a[x["cited"]].append(x)
    span_h = n_windows * WINDOW_H
    for a in sorted(by_a):
        whole_rows.append(feature_row(a, by_a[a], recv_a.get(a, []), span_h))
        whole_meta.append({"agent": a, "n_acts": len(by_a[a])})
    return rows, meta, small, whole_rows, whole_meta, len(timed)

def to_matrix(rows, feats):
    X = np.array([[r[f] for f in feats] for r in rows], float)
    for j, f in enumerate(feats):
        if f in LOG_FEATURES:
            X[:, j] = np.log1p(X[:, j])
    # median impute
    for j in range(X.shape[1]):
        col = X[:, j]; m = np.isnan(col)
        if m.any():
            col[m] = np.nanmedian(col) if (~m).any() else 0.0
    return X

def robust_scale(X, feats):
    med = np.median(X, 0); q05 = np.quantile(X, 0.05, 0); q95 = np.quantile(X, 0.95, 0)
    scale = q95 - q05
    keep = [j for j in range(X.shape[1]) if scale[j] > 1e-12 and X[:, j].std() > 1e-12]
    Xs = (X[:, keep] - med[keep]) / scale[keep]
    Xs = np.clip(Xs, -10, 10)
    params = {"median": med[keep], "scale": scale[keep], "keep": keep}
    return Xs, [feats[j] for j in keep], params

def apply_scale(X, params):
    return np.clip((X[:, params["keep"]] - params["median"]) / params["scale"], -10, 10)

# ----------------------------------------------------------------------------- k-means (numpy), silhouette, ARI
def kmeans_once(X, k, rng, iters=300):
    n = len(X)
    # k-means++ init
    centers = [X[rng.integers(n)]]
    for _ in range(1, k):
        d2 = np.min(((X[:, None, :] - np.array(centers)[None, :, :]) ** 2).sum(2), 1)
        p = d2 / d2.sum() if d2.sum() > 0 else np.full(n, 1 / n)
        centers.append(X[rng.choice(n, p=p)])
    C = np.array(centers)
    lab = None
    for _ in range(iters):
        d = ((X[:, None, :] - C[None, :, :]) ** 2).sum(2)
        new = d.argmin(1)
        if lab is not None and (new == lab).all():
            break
        lab = new
        for c in range(k):
            m = lab == c
            if m.any():
                C[c] = X[m].mean(0)
            else:
                C[c] = X[rng.integers(n)]
    inertia = float(((X - C[lab]) ** 2).sum())
    return lab, C, inertia

def kmeans(X, k, rng, n_init=N_INIT):
    best = None
    for _ in range(n_init):
        lab, C, inertia = kmeans_once(X, k, rng)
        if best is None or inertia < best[2]:
            best = (lab, C, inertia)
    return best[0], best[1]

def silhouette(D, labels):
    return srd.silhouette(D, np.asarray(labels))

def ari(a, b):
    a = np.asarray(a); b = np.asarray(b)
    la = sorted(set(a)); lb = sorted(set(b))
    T = np.zeros((len(la), len(lb)))
    for x, y in zip(a, b):
        T[la.index(x), lb.index(y)] += 1
    comb = lambda v: v * (v - 1) / 2
    sum_ij = comb(T).sum(); sa = comb(T.sum(1)).sum(); sb = comb(T.sum(0)).sum(); n = comb(len(a))
    exp = sa * sb / n if n > 0 else 0
    mx = 0.5 * (sa + sb)
    return float((sum_ij - exp) / (mx - exp)) if mx != exp else 1.0

def hier_states(Xs, rng, n_init=N_INIT, min_child=0.05):
    """k=2 top split, then each mode split in 2 if both children >= min_child of all rows. Returns labels (0..3), tree info."""
    n = len(Xs)
    top, Ctop = kmeans(Xs, 2, rng, n_init)
    D = squareform(pdist(Xs))
    tree = {"top_silhouette": round(silhouette(D, top), 4), "top_sizes": [int((top == c).sum()) for c in range(2)], "children": {}}
    labels = np.zeros(n, int); centers = {}
    nxt = 0
    for c in range(2):
        idx = np.where(top == c)[0]
        done = False
        if len(idx) >= 4:
            sub, Csub = kmeans(Xs[idx], 2, rng, n_init)
            sizes = [int((sub == s).sum()) for s in range(2)]
            if min(sizes) >= min_child * n:
                Dsub = D[np.ix_(idx, idx)]
                tree["children"][str(c)] = {"split": True, "sizes": sizes, "silhouette_within_mode": round(silhouette(Dsub, sub), 4)}
                for s in range(2):
                    labels[idx[sub == s]] = nxt; centers[nxt] = (c, Csub[s]); nxt += 1
                done = True
            else:
                tree["children"][str(c)] = {"split": False, "sizes": sizes, "reason": "child < 5% occupancy"}
        if not done:
            labels[idx] = nxt; centers[nxt] = (c, Xs[idx].mean(0)); nxt += 1
    tree["n_states"] = nxt
    tree["final_silhouette"] = round(silhouette(D, labels), 4) if nxt > 1 else None
    if nxt < 4:  # forced 4-state variant (ignoring the 5% rule), for reference only
        f4 = np.zeros(n, int); q = 0
        for c in range(2):
            idx = np.where(top == c)[0]
            sub, _ = kmeans(Xs[idx], 2, rng, n_init)
            for sidx in range(2):
                f4[idx[sub == sidx]] = q; q += 1
        tree["forced_4_states"] = {"sizes": [int((f4 == c).sum()) for c in range(4)], "silhouette": round(silhouette(D, f4), 4)}
    return labels, {"top_centers": Ctop, "centers": centers, "top": top}, tree

def predict_hier(Xs, model):
    top = ((Xs[:, None, :] - model["top_centers"][None, :, :]) ** 2).sum(2).argmin(1)
    out = np.zeros(len(Xs), int)
    for i in range(len(Xs)):
        cands = [(s, c) for s, (mode, c) in model["centers"].items() if mode == top[i]]
        out[i] = min(cands, key=lambda sc: ((Xs[i] - sc[1]) ** 2).sum())[0]
    return out

def entropy_norm(counts, base_n):
    c = np.asarray(counts, float); n = c.sum()
    if n <= 0 or base_n <= 1:
        return float("nan")
    p = c[c > 0] / n
    return float(-(p * np.log(p)).sum() / math.log(base_n))

def cramers_v(x, y):
    return srd.cramers_v(list(x), list(y))

def perm_p_cramers_agentlevel(labels, agent_of, attr_of_agent, rng, n_perm=N_PERM):
    """Cramér's V of row-level state x attribute; null permutes the attribute across AGENTS (rows of one agent move together)."""
    agents = sorted(set(agent_of)); attrs = [attr_of_agent[a] for a in agents]
    obs = cramers_v(labels, [attr_of_agent[a] for a in agent_of]); cnt = 0
    for _ in range(n_perm):
        perm = dict(zip(agents, rng.permutation(attrs)))
        cnt += cramers_v(labels, [perm[a] for a in agent_of]) >= obs
    return round(obs, 4), round((cnt + 1) / (n_perm + 1), 4)

# ----------------------------------------------------------------------------- two-way permutation ANOVA (Freedman-Lane, type II)
def design(fam, lev, interaction):
    n = len(fam)
    cols = [np.ones(n)]
    fams = sorted(set(fam)); levs = sorted(set(lev))
    F = [np.array([1.0 if f == g else 0.0 for f in fam]) for g in fams[1:]]
    L = [np.array([1.0 if l == g else 0.0 for l in lev]) for g in levs[1:]]
    cols += F + L
    if interaction:
        cols += [a * b for a in F for b in L]
    return np.column_stack(cols)

def rss(X, y):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    return float(r @ r), X @ beta, r

def two_way_perm_anova(fam, lev, y, rng, n_perm=5000):
    y = np.asarray(y, float); n = len(y)
    fams = sorted(set(fam)); levs = sorted(set(lev))
    X_full = design(fam, lev, True)
    X_add = design(fam, lev, False)
    X_fam_only = design(fam, ["x"] * n, False)   # intercept + family
    X_lev_only = design(["x"] * n, lev, False)   # intercept + level
    df_res = n - X_full.shape[1]
    rss_full, _, _ = rss(X_full, y)
    out = {}
    terms = {"family": (X_lev_only, X_add, len(fams) - 1), "level": (X_fam_only, X_add, len(levs) - 1),
             "interaction": (X_add, X_full, (len(fams) - 1) * (len(levs) - 1))}
    for name, (X_red, X_big, df_t) in terms.items():
        rss_red, fit_red, res_red = rss(X_red, y)
        rss_big, _, _ = rss(X_big, y)
        F_obs = ((rss_red - rss_big) / df_t) / (rss_full / df_res) if rss_full > 0 else 0.0
        cnt = 0
        for _ in range(n_perm):
            ystar = fit_red + rng.permutation(res_red)
            r_red, _, _ = rss(X_red, ystar); r_big, _, _ = rss(X_big, ystar); r_full, _, _ = rss(X_full, ystar)
            Fp = ((r_red - r_big) / df_t) / (r_full / df_res) if r_full > 0 else 0.0
            cnt += Fp >= F_obs
        eta2 = (rss_red - rss_big) / (rss(np.ones((n, 1)), y)[0]) if n else float("nan")
        out[name] = {"F": round(F_obs, 3), "df": [df_t, df_res], "perm_p": round((cnt + 1) / (n_perm + 1), 4), "partial_eta2_typeII": round(eta2, 3)}
    return out

# ----------------------------------------------------------------------------- main
def main():
    rng = np.random.default_rng(RNG_SEED)
    acts, side, cov = load_acts_augmented()
    prev = json.load(open(os.path.join(OUT_DIR, "swarm_role_diff_results.json")))["gen1"]
    included = sorted(prev["included"])
    assert not (set(included) & EXCLUDED)
    models = srd.GEN1_MODELS
    fam_of = {a: srd.model_family(models[a]) for a in ROSTER}
    lev_of = {a: level_of(models[a]) for a in ROSTER}
    cell_of = {a: f"{fam_of[a]}/{LEVEL_NAME[lev_of[a]]}" for a in ROSTER}

    # sanity: per-agent type counts equal the probe's profiles
    cnt = defaultdict(Counter)
    for x in acts:
        cnt[x["agent"]][x["type"]] += 1
    for a in included:
        assert dict(cnt[a]) == {t: n for t, n in prev["profiles"][a]["types"].items() if n}, a
    results = {"meta": {"generated_utc": datetime.now(UTC).isoformat(), "seed": RNG_SEED, "window_hours": WINDOW_H,
                        "min_acts_per_row": MIN_ACTS_ROW, "kmeans_n_init": N_INIT, "n_perm": N_PERM, "n_silhouette_null": N_SIL_NULL,
                        "act_table_matches_probe": True, "n_acts_all_authors": len(acts),
                        "n_acts_included_agents": sum(1 for x in acts if x["agent"] in included),
                        "n_included_agents": len(included), "excluded": sorted(EXCLUDED),
                        "bare_time_offset_h": cov["bare_time_offset_chosen_h"], "epoch_end": EPOCH_END.isoformat(),
                        "features": FEATURES, "file_only_features": FILE_ONLY_FEATURES,
                        "feature_defs": {
                            "r_<type>": "acts of that type per hour in the window (log1p)",
                            "cites_given_other": "citation rows by the agent whose cited agent is another roster agent (log1p)",
                            "cites_received": "citation rows by other included agents citing this agent, in the window (log1p)",
                            "distinct_cited": "distinct other agents cited in window (log1p)",
                            "distinct_citers": "distinct other agents citing this agent in window (log1p)",
                            "tool_adopters": "distinct other agents citing a commons/tools file of this agent in window (log1p)",
                            "frac_on_others": "share of acts that engage other agents: cite of another's artifact, board message addressed to / mentioning another agent, or file whose text mentions another roster agent",
                            "frac_new_artifact": "share of acts that create a commons file",
                            "mean_log_size": "mean log1p(bytes) of commons files created in window (median-imputed if none)",
                            "proximity": "artifact-proximity analogue: share of acts touching another agent's artifact (cite of other's file; file or board text referencing another agent's commons path)",
                            "n_other_agents": "distinct other agents engaged in the window (log1p)"}}}

    # ---------------------------------------------------------------- Analysis 1: windows
    timed_all = [x for x in acts if x["time"] is not None and x["agent"] in included]
    t0 = min(x["time"] for x in timed_all); t1 = max(x["time"] for x in timed_all)
    span_h = (t1 - t0).total_seconds() / 3600
    n_windows = int(math.ceil(span_h / WINDOW_H))
    rows, meta, n_small, whole_rows, whole_meta, n_timed = build_rows(acts, included, t0, n_windows)
    X = to_matrix(rows, FEATURES); Xs, feats, params = robust_scale(X, FEATURES)
    D = squareform(pdist(Xs))
    a1 = {"run_start_utc": t0.isoformat(), "run_end_utc": t1.isoformat(), "span_hours": round(span_h, 2), "n_windows": n_windows,
          "n_timed_acts": n_timed, "n_untimed_acts_dropped": sum(1 for x in acts if x["time"] is None and x["agent"] in included),
          "n_rows": len(rows), "n_agent_windows_below_min": n_small, "n_agents_in_rows": len({m["agent"] for m in meta}),
          "features_kept": feats, "features_dropped_zero_variance": [f for f in FEATURES if f not in feats],
          "rows_per_window": {str(w): sum(1 for m in meta if m["window"] == w) for w in range(n_windows)}}

    # flat k-means k=2..6 by silhouette
    sil = {}; flat = {}
    for k in range(2, 7):
        lab, C = kmeans(Xs, k, rng); s = silhouette(D, lab); sil[k] = round(s, 4); flat[k] = lab
    k_best = max(sil, key=sil.get)
    a1["flat_kmeans"] = {"silhouette_by_k": sil, "k_best": k_best, "sizes_at_k_best": [int((flat[k_best] == c).sum()) for c in range(k_best)]}

    # hierarchical states
    labels, model, tree = hier_states(Xs, rng)
    n_states = tree["n_states"]
    a1["hierarchical"] = tree
    # signatures + labels
    NAMES = {"r_finding": "finding", "r_tool": "tool", "r_build": "build", "r_challenge": "challenge", "r_data": "data",
             "r_verify": "verify", "r_correct": "correct", "r_board": "board", "r_cite": "cite",
             "cites_given_other": "cites-out", "cites_received": "cites-in", "distinct_cited": "breadth-out", "distinct_citers": "breadth-in",
             "tool_adopters": "tool-adopted", "frac_on_others": "on-others", "frac_new_artifact": "new-artifact", "mean_log_size": "big-files",
             "proximity": "proximity", "n_other_agents": "social-reach"}
    states = []
    for s in range(n_states):
        idx = np.where(labels == s)[0]
        sig = Xs[idx].mean(0)
        order = np.argsort(-sig)
        hi = [(feats[j], round(float(sig[j]), 2)) for j in order[:4] if sig[j] > 0.15]
        lo = [(feats[j], round(float(sig[j]), 2)) for j in order[::-1][:3] if sig[j] < -0.15]
        raw_mean = {f: round(float(np.mean([rows[i][f] for i in idx if not (isinstance(rows[i][f], float) and math.isnan(rows[i][f]))] or [float("nan")])), 3) for f in FEATURES}
        pooled_raw = {f: float(np.nanmean([r[f] for r in rows])) for f in FEATURES}
        enr = sorted(((raw_mean[f] / pooled_raw[f] if pooled_raw[f] > 0 else 0.0), f) for f in FEATURES if f != "mean_log_size")
        top_enr = [f for e, f in enr[::-1][:3] if e >= 1.2]
        inten = float(np.mean([meta[i]["n_acts"] for i in idx])) / float(np.mean([m["n_acts"] for m in meta]))
        itag = "high-intensity" if inten >= 1.5 else "low-intensity" if inten <= 0.67 else "moderate"
        lab_txt = itag + " " + ("+".join(NAMES[f] for f in top_enr) if top_enr else "generalist")
        states.append({"state": s, "mode": int(model["centers"][s][0]), "n_rows": len(idx), "share_rows": round(len(idx) / len(rows), 3),
                       "label": lab_txt, "enriched_vs_pooled": [(f, round(e, 2)) for e, f in enr[::-1][:5]], "intensity_ratio": round(inten, 2),
                       "top_features_scaled": hi, "bottom_features_scaled": lo,
                       "signature_scaled": {feats[j]: round(float(sig[j]), 3) for j in range(len(feats))},
                       "raw_feature_means": raw_mean,
                       "mean_acts_per_row": round(float(np.mean([meta[i]["n_acts"] for i in idx])), 1),
                       "n_distinct_agents": len({meta[i]["agent"] for i in idx}),
                       "family_counts": dict(Counter(fam_of[meta[i]["agent"]] for i in idx))})
    a1["states"] = states

    # occupancy per window
    occ = []
    for w in range(n_windows):
        idx = [i for i in range(len(meta)) if meta[i]["window"] == w]
        c = Counter(int(labels[i]) for i in idx)
        occ.append({"window": w, "start_h": w * WINDOW_H, "n_rows": len(idx),
                    "fractions": [round(c.get(s, 0) / len(idx), 3) if idx else None for s in range(n_states)],
                    "within_window_entropy_norm": round(entropy_norm([c.get(s, 0) for s in range(n_states)], n_states), 4) if idx else None})
    a1["occupancy_by_window"] = occ
    third = max(1, n_windows // 3)
    def phase_frac(ws):
        idx = [i for i in range(len(meta)) if meta[i]["window"] in ws]
        c = Counter(int(labels[i]) for i in idx)
        return [round(c.get(s, 0) / len(idx), 3) if idx else None for s in range(n_states)], len(idx)
    early, n_e = phase_frac(set(range(0, third))); late, n_l = phase_frac(set(range(n_windows - third, n_windows)))
    a1["occupancy_early_vs_late"] = {"early_windows": list(range(0, third)), "late_windows": list(range(n_windows - third, n_windows)),
                                     "early_fractions": early, "n_early_rows": n_e, "late_fractions": late, "n_late_rows": n_l}
    v_w, p_w = None, None
    obs_vw = cramers_v(labels, [m["window"] for m in meta]); cntw = 0
    for _ in range(N_PERM):
        cntw += cramers_v(rng.permutation(labels), [m["window"] for m in meta]) >= obs_vw
    a1["state_x_window"] = {"cramers_v": round(obs_vw, 4), "perm_p_rowshuffle": round((cntw + 1) / (N_PERM + 1), 4)}

    # within-window entropy: phase vs division of labour
    ent_w = [o["within_window_entropy_norm"] for o in occ if o["n_rows"] >= 4]
    pooled_ent = entropy_norm([int((labels == s).sum()) for s in range(n_states)], n_states)
    null_ent = []
    wins = np.array([m["window"] for m in meta])
    for _ in range(N_PERM):
        lp = rng.permutation(labels); e = []
        for w in range(n_windows):
            idx = np.where(wins == w)[0]
            if len(idx) >= 4:
                c = Counter(int(lp[i]) for i in idx); e.append(entropy_norm([c.get(s, 0) for s in range(n_states)], n_states))
        null_ent.append(float(np.mean(e)))
    null_ent = np.array(null_ent)
    mean_ent = float(np.mean(ent_w))
    # co-occurrence: in how many windows are >= 3 of the states present simultaneously
    n_states_present = [sum(1 for f in o["fractions"] if f and f > 0) for o in occ if o["n_rows"] >= 4]
    a1["within_window_entropy"] = {
        "mean_observed": round(mean_ent, 4), "pooled_state_entropy": round(pooled_ent, 4),
        "ratio_within_to_pooled": round(mean_ent / pooled_ent, 3) if pooled_ent else None,
        "null_mean_shuffle_windows": round(float(null_ent.mean()), 4), "null_p2.5": round(float(np.percentile(null_ent, 2.5)), 4),
        "null_p97.5": round(float(np.percentile(null_ent, 97.5)), 4),
        "p_lower_than_null": round(float(((null_ent <= mean_ent).sum() + 1) / (N_PERM + 1)), 4),
        "n_windows_ge4_rows": len(ent_w), "mean_n_states_present_per_window": round(float(np.mean(n_states_present)), 2),
        "n_windows_all_states_present": int(sum(1 for v in n_states_present if v == n_states)),
        "n_windows_single_state": int(sum(1 for v in n_states_present if v == 1))}
    # same test restricted to the states that are NOT the early high-intensity mode (does division of labour survive once the burst is removed?)
    hi_state = max(range(n_states), key=lambda s: states[s]["intensity_ratio"])
    keep01 = np.array([int(labels[i]) != hi_state for i in range(len(meta))])
    lab01 = labels[keep01]; win01 = wins[keep01]
    v01 = cramers_v(lab01, win01); c01 = 0
    for _ in range(N_PERM):
        c01 += cramers_v(rng.permutation(lab01), win01) >= v01
    ent01 = []
    for w in range(n_windows):
        idx = np.where(win01 == w)[0]
        if len(idx) >= 4:
            c = Counter(int(lab01[i]) for i in idx); ent01.append(entropy_norm([c.get(s, 0) for s in range(n_states) if s != hi_state], n_states - 1))
    pooled01 = entropy_norm([int((lab01 == s).sum()) for s in range(n_states) if s != hi_state], n_states - 1)
    n_both = sum(1 for w in range(n_windows) if len(np.where(win01 == w)[0]) >= 4 and len(set(int(x) for x in lab01[win01 == w])) == n_states - 1)
    a1["excluding_high_intensity_state"] = {"high_intensity_state": hi_state, "n_rows": int(keep01.sum()),
                                            "state_x_window_cramers_v": round(v01, 4), "perm_p_rowshuffle": round((c01 + 1) / (N_PERM + 1), 4),
                                            "mean_within_window_entropy": round(float(np.mean(ent01)), 4), "pooled_entropy": round(pooled01, 4),
                                            "n_windows_ge4_rows": len(ent01), "n_windows_with_all_remaining_states_present": n_both}
    hi_occ = [o["fractions"][hi_state] for o in occ if o["n_rows"] >= 4]
    phase_part = (a1["state_x_window"]["perm_p_rowshuffle"] < 0.05 and mean_ent < float(np.percentile(null_ent, 2.5)))
    dol_part = (float(np.mean(ent01)) >= 0.5 * pooled01 and n_both >= 0.5 * len(ent01))
    if phase_part and dol_part:
        verdict = (f"MIXED. (i) A population-wide phase: the high-intensity state {hi_state} is an early burst (occupies {hi_occ[0]:.0%}-{max(hi_occ):.0%} of rows in the first windows, "
                   f"then 0% after hour {WINDOW_H * (max(i for i, f in enumerate(hi_occ) if f > 0) + 1):.0f}), so within-window entropy ({mean_ent:.2f}) is below the window-shuffle null ({float(null_ent.mean()):.2f}, p={((null_ent <= mean_ent).sum() + 1) / (N_PERM + 1):.3f}) "
                   f"and state x window is significant (V={obs_vw:.2f}). (ii) A division of labour among the remaining states: after removing state {hi_state}, "
                   f"state x window V={v01:.2f} (p={(c01 + 1) / (N_PERM + 1):.3f}), within-window entropy {float(np.mean(ent01)):.2f} vs pooled {pooled01:.2f}, and both remaining states co-occur in {n_both}/{len(ent01)} windows: at the same time different agents are in different states.")
    elif phase_part:
        verdict = "population-wide phase: state composition moves with time and agents are mostly in the same state within a window"
    else:
        verdict = "division of labour: agents occupy different states at the same time; time structure weak"
    a1["within_window_entropy"]["verdict"] = verdict

    # per-agent switching rate + modal state
    per_agent = {}
    sw_adj, sw_any = [], []
    for a in sorted({m["agent"] for m in meta}):
        seq = sorted((meta[i]["window"], int(labels[i])) for i in range(len(meta)) if meta[i]["agent"] == a)
        n_sw = sum(1 for j in range(1, len(seq)) if seq[j][1] != seq[j - 1][1])
        adj = [(seq[j - 1][1], seq[j][1]) for j in range(1, len(seq)) if seq[j][0] == seq[j - 1][0] + 1]
        n_sw_adj = sum(1 for p, q in adj if p != q)
        rate_any = n_sw / (len(seq) - 1) if len(seq) > 1 else None
        rate_adj = n_sw_adj / len(adj) if adj else None
        c = Counter(s for _, s in seq)
        per_agent[a] = {"n_windows": len(seq), "switch_rate_consecutive_occupied": round(rate_any, 3) if rate_any is not None else None,
                        "switch_rate_adjacent_windows": round(rate_adj, 3) if rate_adj is not None else None,
                        "n_adjacent_pairs": len(adj), "modal_state": c.most_common(1)[0][0], "modal_share": round(c.most_common(1)[0][1] / len(seq), 3),
                        "state_counts": {str(s): c.get(s, 0) for s in range(n_states)}, "family": fam_of[a], "level": LEVEL_NAME[lev_of[a]], "cell": cell_of[a]}
        if rate_any is not None: sw_any.append(rate_any)
        if rate_adj is not None: sw_adj.append(rate_adj)
    # null switching rate: shuffle labels within agent sequences? Use row shuffle across all rows (preserving per-agent window sets)
    null_sw = []
    for _ in range(300):
        lp = rng.permutation(labels); tot = 0; den = 0
        for a in per_agent:
            seq = sorted((meta[i]["window"], int(lp[i])) for i in range(len(meta)) if meta[i]["agent"] == a)
            tot += sum(1 for j in range(1, len(seq)) if seq[j][1] != seq[j - 1][1]); den += max(len(seq) - 1, 0)
        null_sw.append(tot / den)
    a1["switching"] = {"mean_rate_consecutive_occupied": round(float(np.mean(sw_any)), 4), "median_rate": round(float(np.median(sw_any)), 4),
                       "mean_rate_adjacent_windows": round(float(np.mean(sw_adj)), 4) if sw_adj else None,
                       "null_rowshuffle_mean": round(float(np.mean(null_sw)), 4), "null_p2.5": round(float(np.percentile(null_sw, 2.5)), 4),
                       "mean_modal_share": round(float(np.mean([v["modal_share"] for v in per_agent.values()])), 3),
                       "n_agents_modal_share_ge_0.5": int(sum(1 for v in per_agent.values() if v["modal_share"] >= 0.5)),
                       "per_agent": per_agent}

    # leave-agent-out and leave-family-out ARI
    agents_rows = np.array([m["agent"] for m in meta])
    lao = {}
    for a in sorted(set(agents_rows)):
        keep = agents_rows != a
        Xk = to_matrix([rows[i] for i in np.where(keep)[0]], FEATURES)
        Xks, fk, pk = robust_scale(Xk, FEATURES)
        if fk != feats:
            # different feature set -> restrict both to common
            common = [f for f in feats if f in fk]
            ji = [feats.index(f) for f in common]; jk = [fk.index(f) for f in common]
            Xks = Xks[:, jk]; pk = {"median": pk["median"][jk], "scale": pk["scale"][jk], "keep": [FEATURES.index(f) for f in common]}
        labk, mk, _ = hier_states(Xks, rng, n_init=8)
        pred = predict_hier(apply_scale(to_matrix(rows, FEATURES), pk), mk)
        lao[a] = round(ari(labels, pred), 4)
    lfo = {}
    for f in FAMILIES:
        keep = np.array([fam_of[a] != f for a in agents_rows])
        Xk = to_matrix([rows[i] for i in np.where(keep)[0]], FEATURES); Xks, fk, pk = robust_scale(Xk, FEATURES)
        if fk != feats:
            common = [x for x in feats if x in fk]; jk = [fk.index(x) for x in common]
            Xks = Xks[:, jk]; pk = {"median": pk["median"][jk], "scale": pk["scale"][jk], "keep": [FEATURES.index(x) for x in common]}
        labk, mk, _ = hier_states(Xks, rng, n_init=8)
        pred = predict_hier(apply_scale(to_matrix(rows, FEATURES), pk), mk)
        lfo[f] = round(ari(labels, pred), 4)
    a1["stability"] = {"leave_agent_out_ari": {"mean": round(float(np.mean(list(lao.values()))), 4), "min": min(lao.values()), "max": max(lao.values()), "per_agent": lao},
                       "leave_family_out_ari": lfo,
                       "note": "refit hierarchical k-means (n_init=8) without the held-out agent/family, assign all rows to nearest centroids, ARI vs full-data 4-state labels"}

    # anti-circularity: file-only features
    Xf = to_matrix(rows, FILE_ONLY_FEATURES); Xfs, ff, _ = robust_scale(Xf, FILE_ONLY_FEATURES)
    labf, _, treef = hier_states(Xfs, rng)
    Df = squareform(pdist(Xfs))
    silf = {k: round(silhouette(Df, kmeans(Xfs, k, rng, 8)[0]), 4) for k in range(2, 7)}
    a1["file_only_refit"] = {"features": ff, "silhouette_by_k": silf, "tree": treef, "ari_vs_full_feature_states": round(ari(labels, labf), 4),
                             "crosstab_full_x_fileonly": {str(s): dict(Counter(int(labf[i]) for i in np.where(labels == s)[0])) for s in range(n_states)}}

    # silhouette null: shuffle each feature column independently across rows
    null_sil = []
    for _ in range(N_SIL_NULL):
        Xp = np.column_stack([rng.permutation(Xs[:, j]) for j in range(Xs.shape[1])])
        Dp = squareform(pdist(Xp))
        null_sil.append(max(silhouette(Dp, kmeans(Xp, k, rng, 4)[0]) for k in range(2, 7)))
    null_sil = np.array(null_sil)
    a1["silhouette_null"] = {"observed_best": sil[k_best], "null_mean": round(float(null_sil.mean()), 4), "null_p95": round(float(np.percentile(null_sil, 95)), 4),
                             "null_max": round(float(null_sil.max()), 4), "p": round(float(((null_sil >= sil[k_best]).sum() + 1) / (len(null_sil) + 1)), 4),
                             "note": "column-wise shuffle of scaled features across rows (destroys feature covariance, keeps marginals); best silhouette over k=2..6 with n_init=4 per null draw"}

    # states x family / level / cell
    fam_rows = [fam_of[a] for a in agents_rows]; lev_rows = [LEVEL_NAME[lev_of[a]] for a in agents_rows]
    xt_f = {str(s): dict(Counter(fam_rows[i] for i in np.where(labels == s)[0])) for s in range(n_states)}
    xt_l = {str(s): dict(Counter(lev_rows[i] for i in np.where(labels == s)[0])) for s in range(n_states)}
    v_f, p_f = perm_p_cramers_agentlevel(labels, list(agents_rows), fam_of, rng)
    v_l, p_l = perm_p_cramers_agentlevel(labels, list(agents_rows), {a: LEVEL_NAME[lev_of[a]] for a in ROSTER}, rng)
    modal_by_agent = {a: per_agent[a]["modal_state"] for a in per_agent}
    v_fm, p_fm = srd.perm_p_cramers([modal_by_agent[a] for a in sorted(modal_by_agent)], [fam_of[a] for a in sorted(modal_by_agent)], rng)
    a1["states_x_model"] = {"rows_state_x_family": xt_f, "family_cramers_v": v_f, "family_perm_p_agentlevel": p_f,
                            "rows_state_x_level": xt_l, "level_cramers_v": v_l, "level_perm_p_agentlevel": p_l,
                            "modal_state_x_family": {str(f): dict(Counter(modal_by_agent[a] for a in modal_by_agent if fam_of[a] == f)) for f in FAMILIES},
                            "modal_state_family_cramers_v": round(v_fm, 4), "modal_state_family_perm_p": round(p_fm, 4),
                            "state_share_by_cell": {c: [round(v, 3) for v in np.bincount([int(labels[i]) for i in range(len(meta)) if cell_of[agents_rows[i]] == c], minlength=n_states) / max(1, sum(1 for i in range(len(meta)) if cell_of[agents_rows[i]] == c))] for c in sorted(set(cell_of[a] for a in included))}}

    # whole-run rows projected into the window-state model
    Xw_s, fw, _ = robust_scale(to_matrix(whole_rows, FEATURES), FEATURES)
    Dw = squareform(pdist(Xw_s))
    silw = {k: round(silhouette(Dw, kmeans(Xw_s, k, rng)[0]), 4) for k in range(2, 7)}
    labw, _, treew = hier_states(Xw_s, rng)
    wl = {whole_meta[i]["agent"]: int(labw[i]) for i in range(len(whole_meta))}
    a1["whole_run"] = {"n_agents": len(whole_rows), "note": "whole-run rows (rates per hour over the full span) clustered on their own; projecting them into the window model is scale-mismatched and is not reported",
                       "own_state_per_agent": wl, "own_state_counts": dict(Counter(wl.values())),
                       "own_state_x_family": {f: dict(Counter(wl[a] for a in wl if fam_of[a] == f)) for f in FAMILIES},
                       "own_state_x_modal_window_state": {str(s): dict(Counter(modal_by_agent[a] for a in wl if wl[a] == s and a in modal_by_agent)) for s in sorted(set(wl.values()))},
                       "own_clustering_silhouette_by_k": silw, "own_hierarchical_tree": treew,
                       "own_states_x_family_cramers_v": round(cramers_v(labw, [fam_of[m["agent"]] for m in whole_meta]), 4),
                       "own_states_x_family_perm_p": round(srd.perm_p_cramers([int(x) for x in labw], [fam_of[m["agent"]] for m in whole_meta], rng)[1], 4)}
    a1["agents_020_022"] = {a: {"cell": cell_of[a], "windows_states": {str(w): s for w, s in sorted((meta[i]["window"], int(labels[i])) for i in range(len(meta)) if meta[i]["agent"] == a)},
                                "modal_state": per_agent[a]["modal_state"], "whole_run_own_state": wl[a]} for a in ("agent-020", "agent-022")}
    results["analysis1_states"] = a1

    # ---------------------------------------------------------------- Analysis 2: 3x3 factorial
    prof = prev["profiles"]
    cells = {}
    per_agent_rows = []
    for a in included:
        p = prof[a]; n = p["n_acts"]; ty = p["types"]
        vc = (ty["verify"] + ty["correct"]) / n
        cs = ty["cite"] / n
        per_agent_rows.append({"agent": a, "family": fam_of[a], "level": lev_of[a], "cell": cell_of[a], "model": models[a], "n_acts": n,
                               "entropy": p["norm_entropy"], "verify_correct_share": vc, "cite_share": cs,
                               "cit_received_per_act": p["citations_received"] / n, "tool_adopters": p["tool_adopters"],
                               "board_share": ty["board"] / n, "tool_share": ty["tool"] / n})
    for f in FAMILIES:
        for l in (3, 2, 1):
            c = f"{f}/{LEVEL_NAME[l]}"
            ag = [r for r in per_agent_rows if r["cell"] == c]
            if not ag:
                cells[c] = {"n_agents": 0}; continue
            tot = Counter()
            for r in ag:
                tot.update(prof[r["agent"]]["types"])
            N = sum(tot.values())
            cells[c] = {"family": f, "level": LEVEL_NAME[l], "model": models[ag[0]["agent"]], "agents": [r["agent"] for r in ag], "n_agents": len(ag),
                        "n_acts": N, "acts_per_agent": round(N / len(ag), 1),
                        "act_type_shares": {t: round(tot[t] / N, 3) for t in TYPES},
                        "verify_correct_share_pooled": round((tot["verify"] + tot["correct"]) / N, 3),
                        "verify_correct_share_mean": round(float(np.mean([r["verify_correct_share"] for r in ag])), 3),
                        "cite_share_mean": round(float(np.mean([r["cite_share"] for r in ag])), 3),
                        "citations_received_per_act_pooled": round(sum(prof[r["agent"]]["citations_received"] for r in ag) / N, 3),
                        "citations_received_total": sum(prof[r["agent"]]["citations_received"] for r in ag),
                        "tool_adopters_total": sum(r["tool_adopters"] for r in ag), "tool_adopters_mean": round(float(np.mean([r["tool_adopters"] for r in ag])), 2),
                        "norm_entropy_mean": round(float(np.mean([r["entropy"] for r in ag])), 4),
                        "norm_entropy_sd": round(float(np.std([r["entropy"] for r in ag], ddof=1)), 4) if len(ag) > 1 else None}
    fam_l = [r["family"] for r in per_agent_rows]; lev_l = [r["level"] for r in per_agent_rows]
    anova = {}
    for resp in ("entropy", "verify_correct_share", "cite_share"):
        anova[resp] = two_way_perm_anova(fam_l, lev_l, [r[resp] for r in per_agent_rows], rng)
    within_family = {}
    for f in FAMILIES:
        sub = [r for r in per_agent_rows if r["family"] == f]
        within_family[f] = {}
        for resp in ("entropy", "verify_correct_share", "cite_share"):
            F, p = srd.perm_p_anova([r["level"] for r in sub], [r[resp] for r in sub], rng)
            within_family[f][resp] = {"F": round(F, 3), "perm_p": round(p, 4), "n": len(sub),
                                      "means_by_level": {LEVEL_NAME[l]: round(float(np.mean([r[resp] for r in sub if r["level"] == l])), 4) for l in (3, 2, 1)}}
    # family-level and level-level marginals
    marg = {"family": {}, "level": {}}
    for f in FAMILIES:
        sub = [r for r in per_agent_rows if r["family"] == f]
        marg["family"][f] = {resp: round(float(np.mean([r[resp] for r in sub])), 4) for resp in ("entropy", "verify_correct_share", "cite_share")}
        marg["family"][f]["n"] = len(sub)
    for l in (3, 2, 1):
        sub = [r for r in per_agent_rows if r["level"] == l]
        marg["level"][LEVEL_NAME[l]] = {resp: round(float(np.mean([r[resp] for r in sub])), 4) for resp in ("entropy", "verify_correct_share", "cite_share")}
        marg["level"][LEVEL_NAME[l]]["n"] = len(sub)
    results["analysis2_3x3"] = {
        "level_mapping": {"sol": {"L3(max)": "gpt56_sol_reasoning_xhigh", "L2(mid)": "gpt56_sol_reasoning_high", "L1(none)": "gpt56_sol"},
                          "orange": {"L3(max)": "es1_orange_o50_thinking_max", "L2(mid)": "es1_orange_o50_thinking", "L1(none)": "es1_orange_o50"},
                          "seed": {"L3(max)": "seed-stable-reasoning-high", "L2(mid)": "seed-stable-reasoning", "L1(none)": "seed-stable"}},
        "n_agents": len(per_agent_rows), "cells": cells, "marginals": marg,
        "two_way_perm_anova": {"method": "OLS with dummy coding; type II F for main effects (additive model), interaction F vs additive; Freedman-Lane residual permutation (5000 perms) under the reduced model", **anova},
        "within_family_level_effect": within_family,
        "per_agent": per_agent_rows,
        "agent_020_022": {a: {"cell": cell_of[a], "model": models[a], "n_acts": prof[a]["n_acts"], "types": prof[a]["types"],
                              "norm_entropy": prof[a]["norm_entropy"], "citations_received": prof[a]["citations_received"], "tool_adopters": prof[a]["tool_adopters"],
                              "role_in_story": "detected enforcement failure at minute 19 and published the topology manual commons/findings/agent-020_swarm_topology_20260801T162757Z.md" if a == "agent-020"
                              else "verified from process state at minute 71; replication/self-correction files (e.g. agent-022_replication_and_two_self_corrections_20260801T205500.md)"}
                          for a in ("agent-020", "agent-022")}}
    results["caveats"] = [
        "Rows are agent x 2-hour windows with >= %d timed acts; idle agent-windows are absent, not a state (SwarmWorld keeps all windows because agents always act)." % MIN_ACTS_ROW,
        "Row-level tests treat windows of the same agent as exchangeable; the family/level Cramér's V p-values permute at AGENT level to respect this; state x window p uses row shuffle.",
        "k-means is a numpy re-implementation (k-means++ init, n_init=32, fixed seed); no sklearn on this machine.",
        "verify/correct detected by filename/message regex only (lower bounds); 'proximity' relies on text references to other agents' commons paths (file reads are not logged in gen1).",
        "3x3 cells are unbalanced: the three SEED_EXTRA agents (005/017/029) are all L2(mid) agents, one per family, so every L2 cell has 3 agents and every other cell 4; n=33, so power for the interaction is low.",
        "Entropy depends mechanically on n_acts; the 3x3 ANOVA does not adjust for n_acts (acts_per_agent per cell is reported).",
    ]
    json.dump(results, open(OUT_JSON, "w"), ensure_ascii=False, indent=1, default=str)
    print("wrote", OUT_JSON)
    print("rows", len(rows), "windows", n_windows, "sil", sil, "k_best", k_best)
    print("tree", tree)
    for s in states:
        print(s["state"], s["n_rows"], s["label"], s["family_counts"])
    print("within-window entropy", a1["within_window_entropy"])
    print("switching", {k: v for k, v in a1["switching"].items() if k != "per_agent"})
    print("LAO ARI", a1["stability"]["leave_agent_out_ari"]["mean"], a1["stability"]["leave_family_out_ari"])
    print("sil null", a1["silhouette_null"])
    print("states x family", a1["states_x_model"]["family_cramers_v"], a1["states_x_model"]["family_perm_p_agentlevel"], xt_f)
    print("file-only ARI", a1["file_only_refit"]["ari_vs_full_feature_states"])
    print("early/late", a1["occupancy_early_vs_late"])
    for c, v in cells.items():
        print(c, v.get("n_agents"), v.get("n_acts"), v.get("verify_correct_share_pooled"), v.get("norm_entropy_mean"), v.get("citations_received_per_act_pooled"))
    print(json.dumps(anova, indent=0))
    print(json.dumps(within_family, indent=0))

if __name__ == "__main__":
    main()
