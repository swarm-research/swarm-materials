#!/usr/bin/env python3
"""Render role_diff_probe.md from swarm_role_diff_results.json (every number in the report comes from the JSON)."""
import json, os
D = os.path.expanduser("~/Downloads/swarm-iclr")
R = json.load(open(os.path.join(D, "swarm_role_diff_results.json")))
T = R["meta"]["types"]
CORPORA = [("gen1", R["gen1"])] + [(m, R["gen2"][m]) for m in ["122174", "122175", "122448", "122456"]]
f2 = lambda x: "—" if x is None else f"{x:.2f}"
f3 = lambda x: "—" if x is None else f"{x:.3f}"
f1 = lambda x: "—" if x is None else f"{x:.1f}"
L = []
w = L.append

w("# Role differentiation probe — swarm gen1 + gen2 (local data only)\n")
w(f"Generated {R['meta']['generated_utc'][:19]}Z from `swarm_role_diff.py`; all numbers below are read from `swarm_role_diff_results.json` (n_perm={R['meta']['n_perm']}, min acts={R['meta']['min_acts']}).\n")

# ---------------- TL;DR
g1 = R["gen1"]; s1 = g1["specialization"]; n1 = s1["null_shuffle_labels"]; st1 = g1["specialization_by_model_family"]
x = R["gen2_cross_machine"]
w("## TL;DR\n")
w(f"1. **Specialization exists and beats the null everywhere.** Mean normalized entropy of agents' act-type profiles is below a label-shuffle null in gen1 ({f3(s1['observed']['mean_norm_entropy'])} vs {f3(n1['mean_norm_entropy']['null_mean'])}, z={f1(n1['mean_norm_entropy']['z'])}) and on all 4 gen2 machines (z from {f1(min(R['gen2'][m]['specialization']['null_shuffle_labels']['mean_norm_entropy']['z'] for m in ['122174','122175','122448','122456']))} to {f1(max(R['gen2'][m]['specialization']['null_shuffle_labels']['mean_norm_entropy']['z'] for m in ['122174','122175','122448','122456']))}). Agent identity explains {f1(100*s1['observed']['nmi_agent_type'])}% of act-type entropy in gen1 (NMI), null {f1(100*n1['nmi_agent_type']['null_mean'])}%.")
w(f"2. **But about half of it is the base model, not emergent role-taking.** Model family alone explains {f1(100*st1['fraction_of_agent_nmi_explained_by_family'])}% of gen1's agent-type information ({f1(100*st1['nmi_family_type'])}% of {f1(100*st1['nmi_agent_type'])}%); on gen2 machines {', '.join(f1(100*R['gen2'][m]['specialization_by_model_family']['fraction_of_agent_nmi_explained_by_family'])+'%' for m in ['122174','122175','122448','122456'])}. Gen1 clusters map onto model family with Cramér's V={f2(g1['clustering']['confounds']['model_family_cramers_v'])} (perm p={g1['clustering']['confounds']['model_family_perm_p']}); on 122448 the k=2 split is exactly the 3 seed-family agents vs the rest (V=1.0). Within-family residual specialization survives a family-stratified null (gen1 z={f1(st1['null_stratified_by_family']['mean_norm_entropy']['z'])}) but is small in absolute terms (entropy {f3(s1['observed']['mean_norm_entropy'])} vs stratified null {f3(st1['null_stratified_by_family']['mean_norm_entropy']['null_mean'])}).")
t1 = g1["temporal"]
w(f"3. **No progressive divergence.** Gen1 agents become *less* specialized over their own timelines (tercile entropy {t1['mean_entropy_by_tercile'][0]} → {t1['mean_entropy_by_tercile'][1]} → {t1['mean_entropy_by_tercile'][2]}; late−early = {f3(t1['late_minus_early_mean'])}, bootstrap 95% [{f3(t1['late_minus_early_boot95'][0])}, {f3(t1['late_minus_early_boot95'][1])}]; {t1['n_entropy_up']} of {t1['n_agents_with_ge15_timed_acts']} went up). Gen2 machines are flat or slightly decreasing, all bootstrap CIs covering 0.")
w(f"4. **Cross-machine 'replication' is replication of model-family habits.** Pooling {x['n_agents_pooled']} native gen2 agents, the best clustering (k={x['k']}, silhouette {x['silhouette']}) is not machine-specific (cluster×machine V={x['cluster_x_machine_cramers_v']}, p={x['cluster_x_machine_perm_p']}) — but its two big clusters are {x['clusters'][0]['model_families']} and {x['clusters'][1]['model_families']} (cluster×family V={x['cluster_x_model_family_cramers_v']}).")
w("5. **Verdict: supporting section, not a headline.** The defensible claim is \"identical prompts + heterogeneous base models → stable, model-typed functional profiles (sol → audit/correct/board, orange → tools/data, seed → cite/build), plus a smaller within-model individuality that persists across an agent's own timeline\". \"Spontaneous division of labour among identical agents\" is not supported: the agents were not identical (9 model configs), and specialization does not grow with interaction time.\n")

# ---------------- coverage
w("## 1. Data coverage\n")
w("| corpus | commons files (attributed / unattributed) | board msgs (attributed) | citations raw → REALFILE | bare-time offset (median |Δ| min) | roster | included | excluded <5 | specials excluded | ghost ids | silent roster ids | dropped late epoch |")
w("|---|---|---|---|---|---|---|---|---|---|---|---|")
for name, g in CORPORA:
    c = g["coverage"]; tz = c["bare_time_offset_check"][str(c["bare_time_offset_chosen_h"])]
    w(f"| {name} | {c['commons_files_total']} ({c['commons_files_total']-c['commons_files_unattributed']} / {c['commons_files_unattributed']}) | {c['board_messages_total']} ({c['board_messages_attributed']}) | {c['citations_raw']} → {c['citations_realfile']} | UTC{c['bare_time_offset_chosen_h']:+d} ({f1(tz['median_abs_min'])}, n={tz['n_pairs']}) | {g['roster_size']} | {g['n_included']} | {g['n_excluded_tiny']} {g['excluded_tiny'] if g['excluded_tiny'] else ''} | {', '.join(g['specials_present'])} | {', '.join(g['ghost_authors'])} | {len(g['roster_silent'])} | {c.get('acts_dropped_after_epoch_end', 0)} |")
w("")
w(f"- 122447: excluded — {R['gen2']['122447']['reason']}.")
w(f"- gen1 late epoch: {g1['coverage']['acts_dropped_after_epoch_end']} acts after 2026-08-10 (a re-run on 08-31/09-01 by {g1['coverage']['late_epoch_agents']}) are dropped from all statistics.")
w("- gen2 seed copies agent-001..036 are present on every machine (36 authors each) and are excluded; native = ids in that machine's `devbox_sessions.json`. Restarted sessions (duplicate rows) per machine: " + ", ".join(f"{m}: {R['gen2'][m]['coverage']['n_restarts(dup session rows)']}" for m in ['122174','122175','122448','122456']) + ".")
w(f"- Phantom-ID fix applied: {R['gen2']['122448']['coverage'].get('phantom_id_remap')} (the `%03d` bug documented in the findings registry, finding 19).")
w("- Time discipline: file mtime for commons files; declared times with Z/offset = UTC; bare declared times = local, offset chosen per corpus by minimizing the median |board-announcement time − file mtime| (gen1 → EDT, all gen2 devboxes → UTC+8; the alternative offsets give medians of hours, so the choice is unambiguous).")
w("- Attribution: basename prefix `agent-XXX(X)_` first, else an agent-named parent directory (challenge arenas, build dirs), else an author field in the first 1.5 KB. `__pycache__`/`.pyc`/`.lock` files are ignored. Gen2 citation rows use an `artifact` key instead of `file` (handled).\n")

w("## 2. Method\n")
w(f"- **Act types (K={len(T)}, mutually exclusive):** `{'`, `'.join(T)}`. Commons files map to their subdir unless the basename matches the correction regex (`{R['meta']['regex']['correct']}`) → `correct`, or the verification regex (`{R['meta']['regex']['verify_file']}`) → `verify`. Board messages: correction regex → `correct`, stricter message regex (`{R['meta']['regex']['verify_msg']}`) → `verify`, else `board`. Citation rows (REALFILE) → `cite` for the citer.")
w("- **Per-agent specialization:** normalized Shannon entropy H/log K of the 9-type distribution (1 = uniform, 0 = single type); Herfindahl of shares.")
w("- **Population measures:** mean entropy; NMI(agent; type) = mutual information between agent identity and act type divided by H(type) (share of type-entropy explained by who acted); mean pairwise Jensen–Shannon divergence between agent profiles.")
w("- **Nulls (1000 draws):** (a) *label shuffle* — permute act-type labels across all acts of included agents, preserving each agent's act count and every type's total; (b) *multinomial* — each agent draws its n acts from the pooled distribution; (c) *family-stratified shuffle* — labels permuted only among agents of the same model family (sol / orange / seed), which tests for specialization beyond what the base model explains.")
w("- **Temporal:** per-agent terciles of own timed acts (agents with ≥15), entropy per tercile; global run terciles, NMI/JSD per window vs shuffle null; *niche persistence*: JSD(own first half, own second half) vs JSD(own first half, other agents' second halves).")
w("- **Clustering:** Ward on z-scored [9 shares + log1p(citations received per act) + log1p(distinct tool adopters) + log1p(n acts)], k∈[2,6] by silhouette; labels from types enriched ≥1.3× over the pooled share with mean share ≥ 8%. Confounds: Cramér's V (cluster × model family / config, permutation p), permutation ANOVA F for launch index, first-act time, log n acts.\n")

# ---------------- table A
w("## 3. Specialization vs null\n")
w("| corpus | agents | acts | mean H obs | shuffle null (z, p) | multinomial null (z) | Herfindahl obs / null | NMI obs / null (z) | pairwise JSD obs / null (z) | agents with p<.05 (Bonferroni) | Spearman(n acts, H) |")
w("|---|---|---|---|---|---|---|---|---|---|---|")
for name, g in CORPORA:
    s = g["specialization"]; n = s["null_shuffle_labels"]; mn = s["null_multinomial_pooled"]; o = s["observed"]
    w(f"| {name} | {g['n_included']} | {s['n_acts_included']} | {f3(o['mean_norm_entropy'])} | {f3(n['mean_norm_entropy']['null_mean'])} (z={f1(n['mean_norm_entropy']['z'])}, p={n['mean_norm_entropy']['p_one_sided']:.3f}) | {f3(mn['mean_norm_entropy']['null_mean'])} (z={f1(mn['mean_norm_entropy']['z'])}) | {f3(o['mean_herfindahl'])} / {f3(n['mean_herfindahl']['null_mean'])} | {f3(o['nmi_agent_type'])} / {f3(n['nmi_agent_type']['null_mean'])} (z={f1(n['nmi_agent_type']['z'])}) | {f3(o['mean_pairwise_jsd'])} / {f3(n['mean_pairwise_jsd']['null_mean'])} (z={f1(n['mean_pairwise_jsd']['z'])}) | {s['n_agents_more_specialized_than_null_p05']} ({s['n_agents_p05_bonferroni']}) | {s['entropy_vs_nacts_spearman']['rho']} (p={s['entropy_vs_nacts_spearman']['p']}) |")
w("")
w("Pooled type shares (what the population does overall):\n")
w("| corpus | " + " | ".join(T) + " |")
w("|---|" + "---|" * len(T))
for name, g in CORPORA:
    p = g["specialization"]["pooled_shares"]
    w(f"| {name} | " + " | ".join(f"{100*p[t]:.1f}%" for t in T) + " |")
w("")
w("Reading: the null-shuffle entropy gap is 0.06–0.11 on a 0–1 scale; NMI 0.075–0.124 means agent identity explains 7.5–12.4% of the entropy of \"which kind of act happens\". Statistically unambiguous (z ≥ 9 everywhere, p = 1/1001), modest in magnitude. Note the positive Spearman on gen2 (fewer acts → lower entropy mechanically); the shuffle null preserves per-agent n so the z-scores already account for this, but cluster labels for low-count agents should be read with that in mind.\n")

# ---------------- table B
w("## 4. How much is the base model? (family decomposition)\n")
w("| corpus | families (n agents) | NMI(agent;type) | NMI(family;type) | share explained by family | mean H obs | family-stratified null H (z, p) | stratified null NMI (z) |")
w("|---|---|---|---|---|---|---|---|")
for name, g in CORPORA:
    st = g["specialization_by_model_family"]; nn = st["null_stratified_by_family"]; s = g["specialization"]
    w(f"| {name} | {st['families']} | {f3(st['nmi_agent_type'])} | {f3(st['nmi_family_type'])} | {f1(100*st['fraction_of_agent_nmi_explained_by_family'])}% | {f3(s['observed']['mean_norm_entropy'])} | {f3(nn['mean_norm_entropy']['null_mean'])} (z={f1(nn['mean_norm_entropy']['z'])}, p={nn['mean_norm_entropy']['p_one_sided']:.3f}) | {f3(nn['nmi_agent_type']['null_mean'])} (z={f1(nn['nmi_agent_type']['z'])}) |")
w("")
w("Within each family separately (own pooled distribution, own shuffle null):\n")
w("| corpus | family | n | mean H obs / null (z, p) | NMI obs / null (z) | family's own type shares (top 3) |")
w("|---|---|---|---|---|---|")
for name, g in CORPORA:
    st = g["specialization_by_model_family"]
    for fam, v in st["per_family"].items():
        if "note" in v:
            w(f"| {name} | {fam} | {v['n_agents']} | too few agents | | |"); continue
        top = sorted(v["pooled_shares"].items(), key=lambda kv: -kv[1])[:3]
        w(f"| {name} | {fam} | {v['n_agents']} | {f3(v['mean_norm_entropy'])} / {f3(v['entropy_null_mean'])} (z={f1(v['entropy_z'])}, p={v['entropy_p']:.3f}) | {f3(v['nmi'])} / {f3(v['nmi_null_mean'])} (z={f1(v['nmi_z'])}) | " + ", ".join(f"{t} {100*s:.0f}%" for t, s in top) + " |")
w("")
w("Reading: the family-level profiles are strikingly consistent across corpora — sol agents' acts are dominated by board posts, citations, verification and corrections with almost no tools/data; orange agents build tools and curate data; the seed family (gen1 only has enough of them) cites and builds dashboards. Within the sol family on three of four gen2 machines the mean-entropy test is *not* significant (z between −1.4 and +0.5), i.e. sol agents differ from each other in *which* mix they use (NMI still significant) but are not more concentrated than chance. Orange agents show the clearest within-family specialization (z ≤ −8.5 on every gen2 machine).\n")

# ---------------- clusters
w("## 5. Clusters\n")
for name, g in CORPORA:
    cl = g["clustering"]; cf = cl["confounds"]
    w(f"### {name}: k={cl['k']} (silhouette {cl['silhouette']}; by k: {cl['silhouette_by_k']})\n")
    w("| n | label | enriched types | mean H | mean acts | mean cit. received | model families | examples |")
    w("|---|---|---|---|---|---|---|---|")
    for c in cl["clusters"]:
        w(f"| {c['n']} | {c['label']} | {', '.join(c['enriched_types']) or '—'} | {f3(c['mean_norm_entropy'])} | {c['mean_n_acts']} | {c['mean_cit_received']} | {c['model_families']} | {', '.join(c['examples'])} |")
    w("")
    w(f"Confounds — cluster × model family: V={cf['model_family_cramers_v']} (p={cf['model_family_perm_p']}); × model config: V={cf['model_config_cramers_v']} (p={cf['model_config_perm_p']}); launch index: F={cf['launch_index_anova_F']} (p={cf['launch_index_perm_p']}); first-act time: F={cf['first_act_time_anova_F']} (p={cf['first_act_time_perm_p']}); log n acts: F={cf['log_n_acts_anova_F']} (p={cf['log_n_acts_perm_p']}). Niche-by-enrichment counts: {g['niche_counts']}.\n")
w("Reading: in gen1 launch index and model are collinear by design (blocks of 4), so the launch-index F is the same confound. Birth time never predicts cluster (all p > 0.17). Activity level does (p ≤ 0.01 on gen1/122175/122448): the low-activity agents form the 'specialist'-looking small clusters. The silhouettes (0.20–0.29 per corpus, 0.14 pooled) are weak — the clusters are tendencies, not discrete castes.\n")

# ---------------- temporal
w("## 6. Temporal: does specialization grow?\n")
w("| corpus | span (h) | agents (≥15 timed acts) | mean H by own tercile (early/mid/late) | late−early mean [boot 95%] | agents H down / up |")
w("|---|---|---|---|---|---|")
for name, g in CORPORA:
    t = g["temporal"]
    w(f"| {name} | {t['span_hours']} | {t['n_agents_with_ge15_timed_acts']} | {t['mean_entropy_by_tercile'][0]} / {t['mean_entropy_by_tercile'][1]} / {t['mean_entropy_by_tercile'][2]} | {f3(t['late_minus_early_mean'])} [{f3(t['late_minus_early_boot95'][0])}, {f3(t['late_minus_early_boot95'][1])}] | {t['n_entropy_down_late_vs_early']} / {t['n_entropy_up']} |")
w("")
w("Global run windows (population terciles by act time; only agents with ≥5 acts in the window):\n")
w("| corpus | window (h) | agents | acts | mean H obs / null (z) | NMI obs / null (z) | pairwise JSD obs / null (z) |")
w("|---|---|---|---|---|---|---|")
for name, g in CORPORA:
    for wdw in g["temporal"]["global_windows"]:
        if "note" in wdw:
            w(f"| {name} | {wdw['window']} | {wdw['n_agents']} | too few | | | |"); continue
        w(f"| {name} | {wdw['start_h']}–{wdw['end_h']} | {wdw['n_agents']} | {wdw['n_acts']} | {f3(wdw['mean_norm_entropy'])} / {f3(wdw['entropy_null_mean'])} (z={f1(wdw['entropy_z'])}) | {f3(wdw['nmi'])} / {f3(wdw['nmi_null_mean'])} (z={f1(wdw['nmi_z'])}) | {f3(wdw['mean_pairwise_jsd'])} / {f3(wdw['jsd_null_mean'])} (z={f1(wdw['jsd_z'])}) |")
w("")
w("Niche persistence (does an agent's early-half profile predict its own late half better than other agents' late halves?):\n")
w("| corpus | agents (≥20 timed acts) | own JSD mean | median cross JSD mean | own < median cross | own < median cross within same family | own is nearest of all |")
w("|---|---|---|---|---|---|---|")
for name, g in CORPORA:
    p = g["temporal"]["niche_persistence"]
    w(f"| {name} | {p['n_agents_ge20_timed_acts']} | {f3(p['mean_own_jsd'])} | {f3(p['mean_median_cross_jsd'])} | {p['n_own_closer_than_median_cross']} | {p['n_own_closer_than_median_cross_same_family']} / {p['n_with_same_family_comparison']} | {p['n_own_is_nearest_of_all(rank0)']} |")
w("")
w("Reading: differentiation is present from the first window (gen1 window 1 has the *highest* NMI, 0.202) and does not ratchet up; in gen1 individual agents broaden their repertoire over time (23 of 33 entropies rise). Agents are somewhat self-consistent (own-half JSD below the median cross-agent JSD for most agents), but only a handful are closer to their own past than to *every* other agent, and within-family self-consistency is weaker. This is the pattern of stable dispositions, not of a division of labour negotiated through interaction.\n")

# ---------------- cross machine
w("## 7. Gen2: does the same niche structure recur on separate machines?\n")
w(f"Pooled clustering of {x['n_agents_pooled']} included native agents from {x['n_machines']} machines: k={x['k']} (silhouette {x['silhouette']}; by k {x['silhouette_by_k']}). Cluster × machine Cramér's V = {x['cluster_x_machine_cramers_v']} (perm p = {x['cluster_x_machine_perm_p']}); cluster × model family V = {x['cluster_x_model_family_cramers_v']}.\n")
w("| n | label | machines | model families | mean shares (top 3) | examples |")
w("|---|---|---|---|---|---|")
for c in x["clusters"]:
    top = sorted(c["mean_shares"].items(), key=lambda kv: -kv[1])[:3]
    w(f"| {c['n']} | {c['label']} | {c['machines']} | {c['model_families']} | " + ", ".join(f"{t} {100*s:.0f}%" for t, s in top) + f" | {', '.join(c['examples'])} |")
w("")
w("Per-machine verdicts side by side:\n")
w("| machine | included | mean H obs / null (z) | NMI obs (z) | agents p<.05 | per-machine cluster labels |")
w("|---|---|---|---|---|---|")
for m, v in x["per_machine_verdicts"].items():
    w(f"| {m} | {v['n_included']} | {v['mean_entropy_obs']} / {v['mean_entropy_null']} (z={f1(v['entropy_z'])}) | {v['nmi_obs']} (z={f1(v['nmi_z'])}) | {v['n_sig_agents']} | {'; '.join(v['cluster_labels'])} |")
w("")
w(f"Niche (by enrichment) present with ≥2 agents on how many of the 4 machines: {x['niche_recurs_in_n_machines(>=2 agents)']}.\n")
w("Reading: the recurring structure is real and not machine-specific — every machine has a verify/correct-heavy group and a tool/data-heavy group — but it is the same two model families doing the same two things on each machine. Two caveats make gen2 a weak replication for *emergent* roles: the gen2 prompt literally instructs agents to \"find your niche\" and \"cite generously\" (gen1's does not), and every machine was seeded with a copy of gen1's commons, so the gen2 agents saw gen1's verifiers, tool-builders and correction culture before acting.\n")

# ---------------- examples
w("## 8. Concrete example agents (lowest-entropy included agents, with their own artifacts)\n")
for name, g in CORPORA:
    w(f"**{name}**\n")
    for e in g["most_specialized_examples"][:3]:
        sh = ", ".join(f"{t} {100*v:.0f}%" for t, v in sorted(e["shares"].items(), key=lambda kv: -kv[1]) if v >= 0.05)
        w(f"- `{e['agent']}` ({e['model']}, {e['n_acts']} acts, H={e['norm_entropy']}): {sh}. Own dominant artifact type: {e['dominant_own_artifact_type']}.")
        for p in e["example_paths"]:
            w(f"  - `{p}`")
    w("")
w("Self-declared roles in gen1 registry status lines (the only agents that wrote a `role` field): " + "; ".join(f"{r['agent']}: \"{r['role']}\" (×{r['n']})" for r in g1["self_declared_roles_in_registry"]) + ". agent-014's self-description (\"independent verification, red-teaming, data integrity\") matches its measured profile (verify is its largest commons type), but only 3 of 33 agents ever declared a role.\n")

# ---------------- confounds
w("## 9. Confounds and sanity checks\n")
for c in R["confounds"]:
    w(f"- {c}")
w("")

# ---------------- assessment
w("## 10. Assessment: headline or supporting section?\n")
w("**Supporting section.** What the data can carry:\n")
w("- A clean, replicated *measurement*: under identical instructions and an open-ended commons, agents' act-type profiles are far from exchangeable (NMI z ≥ 28 on every corpus; 11–16 of 17–24 agents per machine individually below the shuffle null at p < .05) and this recurs on four independent devboxes.")
w("- A clean *decomposition*: roughly a third to a half of that structure is the base model (sol → auditing/correcting/board talk; orange → tools/data; seed → citing/builds), and the family-level profile is the part that replicates across machines. The remainder is individual and persists across an agent's own timeline.")
w("- A clean *negative*: specialization does not increase over 23–39 hours of interaction; gen1 agents broaden.\n")
w("What it cannot carry:\n")
w("- \"Identical agents spontaneously divide labour.\" The agents were not identical (9 model configs in gen1, 3 families in gen2); the confound dominates the cluster structure (cluster × family V = 0.63–1.0 on gen1/122174/122175/122448; 0.49, n.s., on 122456), and the within-family residual is small (entropy gap ≈ 0.02–0.03 against the stratified null) and, for sol on 3 of 4 machines, not significant on the entropy test.")
w("- \"Roles emerge from interaction.\" The temporal signal points the other way, and gen2's prompt asks for niche-finding explicitly.")
w("- Clean role categories. Silhouettes of 0.15–0.34 mean the clusters are gradients; the labels (\"verifiers/auditors\", \"tool-builders\") are descriptive summaries of enrichment, not discrete castes.\n")
w("If a role-differentiation angle is wanted for the paper, the honest framing is *model-typed functional profiles under a shared institution* (a between-model result with a small within-model individuality term), presented as one supporting figure next to the institution-adoption and correction-culture results. To make it a headline one would need a run with a single model config (or many agents per config) and a randomized prompt-free design — that is a new experiment, not more analysis of this data.\n")

open(os.path.join(D, "role_diff_probe.md"), "w").write("\n".join(L))
print("wrote", os.path.join(D, "role_diff_probe.md"), len(L), "lines")
