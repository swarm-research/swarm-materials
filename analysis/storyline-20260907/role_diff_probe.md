# Role differentiation probe — swarm gen1 + gen2 (local data only)

Generated 2026-09-07T07:47:54Z from `swarm_role_diff.py`; all numbers below are read from `swarm_role_diff_results.json` (n_perm=1000, min acts=5).

## TL;DR

1. **Specialization exists and beats the null everywhere.** Mean normalized entropy of agents' act-type profiles is below a label-shuffle null in gen1 (0.781 vs 0.841, z=-17.9) and on all 4 gen2 machines (z from -18.7 to -9.2). Agent identity explains 10.0% of act-type entropy in gen1 (NMI), null 1.8%.
2. **But about half of it is the base model, not emergent role-taking.** Model family alone explains 50.1% of gen1's agent-type information (5.0% of 10.0%); on gen2 machines 47.1%, 46.6%, 34.5%, 32.8%. Gen1 clusters map onto model family with Cramér's V=0.87 (perm p=0.001); on 122448 the k=2 split is exactly the 3 seed-family agents vs the rest (V=1.0). Within-family residual specialization survives a family-stratified null (gen1 z=-5.3) but is small in absolute terms (entropy 0.781 vs stratified null 0.800).
3. **No progressive divergence.** Gen1 agents become *less* specialized over their own timelines (tercile entropy 0.6578 → 0.7194 → 0.7317; late−early = 0.074, bootstrap 95% [-0.000, 0.148]; 23 of 33 went up). Gen2 machines are flat or slightly decreasing, all bootstrap CIs covering 0.
4. **Cross-machine 'replication' is replication of model-family habits.** Pooling 87 native gen2 agents, the best clustering (k=3, silhouette 0.1414) is not machine-specific (cluster×machine V=0.134, p=0.964) — but its two big clusters are {'sol': 27, 'seed': 2} and {'orange': 33, 'sol': 14, 'seed': 10} (cluster×family V=0.472).
5. **Verdict: supporting section, not a headline.** The defensible claim is "identical prompts + heterogeneous base models → stable, model-typed functional profiles (sol → audit/correct/board, orange → tools/data, seed → cite/build), plus a smaller within-model individuality that persists across an agent's own timeline". "Spontaneous division of labour among identical agents" is not supported: the agents were not identical (9 model configs), and specialization does not grow with interaction time.

## 1. Data coverage

| corpus | commons files (attributed / unattributed) | board msgs (attributed) | citations raw → REALFILE | bare-time offset (median |Δ| min) | roster | included | excluded <5 | specials excluded | ghost ids | silent roster ids | dropped late epoch |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gen1 | 2172 (2131 / 41) | 1808 (1618) | 1985 → 1717 | UTC-4 (9.3, n=187) | 36 | 33 | 0  | agent-005, agent-017, agent-029, agent-042 | agent-000, agent-042, agent-901 | 0 | 722 |
| 122174 | 2819 (2780 / 39) | 2650 (2477) | 2335 → 2068 | UTC+8 (0.9, n=1300) | 33 | 24 | 0  | agent-042 | agent-000, agent-901 | 8 | 0 |
| 122175 | 2676 (2662 / 14) | 1587 (1587) | 974 → 968 | UTC+8 (1.9, n=2003) | 31 | 22 | 0  | agent-038 | agent-000 | 8 | 0 |
| 122448 | 1432 (1428 / 4) | 943 (943) | 556 → 548 | UTC+8 (7.9, n=919) | 31 | 24 | 0  | agent-045, agent-060 | agent-000 | 5 | 0 |
| 122456 | 3021 (2983 / 38) | 2539 (2366) | 739 → 735 | UTC+8 (1.9, n=1549) | 28 | 17 | 0  | agent-0105, agent-0150, agent-0155, agent-051, agent-076 | agent-000, agent-042, agent-901 | 6 | 0 |

- 122447: excluded — no devbox_sessions.json; no board/citations; 0 tools; no native gen2 output.
- gen1 late epoch: 722 acts after 2026-08-10 (a re-run on 08-31/09-01 by {'agent-005': 281, 'agent-007': 225, 'agent-006': 214, 'agent-001': 2}) are dropped from all statistics.
- gen2 seed copies agent-001..036 are present on every machine (36 authors each) and are excluded; native = ids in that machine's `devbox_sessions.json`. Restarted sessions (duplicate rows) per machine: 122174: 9, 122175: 16, 122448: 0, 122456: 9.
- Phantom-ID fix applied: {'agent-109': 'agent-0109'} (the `%03d` bug documented in the findings registry, finding 19).
- Time discipline: file mtime for commons files; declared times with Z/offset = UTC; bare declared times = local, offset chosen per corpus by minimizing the median |board-announcement time − file mtime| (gen1 → EDT, all gen2 devboxes → UTC+8; the alternative offsets give medians of hours, so the choice is unambiguous).
- Attribution: basename prefix `agent-XXX(X)_` first, else an agent-named parent directory (challenge arenas, build dirs), else an author field in the first 1.5 KB. `__pycache__`/`.pyc`/`.lock` files are ignored. Gen2 citation rows use an `artifact` key instead of `file` (handled).

## 2. Method

- **Act types (K=9, mutually exclusive):** `finding`, `tool`, `build`, `challenge`, `data`, `verify`, `correct`, `board`, `cite`. Commons files map to their subdir unless the basename matches the correction regex (`correction|errat|retract|supersed|stand-?down|更正|撤回`) → `correct`, or the verification regex (`(?<![a-z])(verif|audit|replic|reproduc|check(?!point)|negative[-_ ]?control)`) → `verify`. Board messages: correction regex → `correct`, stricter message regex (`(?<![a-z])(verif|audit|replicat|reproduc|negative[-_ ]?control|阴性对照|复现|审计|验证)`) → `verify`, else `board`. Citation rows (REALFILE) → `cite` for the citer.
- **Per-agent specialization:** normalized Shannon entropy H/log K of the 9-type distribution (1 = uniform, 0 = single type); Herfindahl of shares.
- **Population measures:** mean entropy; NMI(agent; type) = mutual information between agent identity and act type divided by H(type) (share of type-entropy explained by who acted); mean pairwise Jensen–Shannon divergence between agent profiles.
- **Nulls (1000 draws):** (a) *label shuffle* — permute act-type labels across all acts of included agents, preserving each agent's act count and every type's total; (b) *multinomial* — each agent draws its n acts from the pooled distribution; (c) *family-stratified shuffle* — labels permuted only among agents of the same model family (sol / orange / seed), which tests for specialization beyond what the base model explains.
- **Temporal:** per-agent terciles of own timed acts (agents with ≥15), entropy per tercile; global run terciles, NMI/JSD per window vs shuffle null; *niche persistence*: JSD(own first half, own second half) vs JSD(own first half, other agents' second halves).
- **Clustering:** Ward on z-scored [9 shares + log1p(citations received per act) + log1p(distinct tool adopters) + log1p(n acts)], k∈[2,6] by silhouette; labels from types enriched ≥1.3× over the pooled share with mean share ≥ 8%. Confounds: Cramér's V (cluster × model family / config, permutation p), permutation ANOVA F for launch index, first-act time, log n acts.

## 3. Specialization vs null

| corpus | agents | acts | mean H obs | shuffle null (z, p) | multinomial null (z) | Herfindahl obs / null | NMI obs / null (z) | pairwise JSD obs / null (z) | agents with p<.05 (Bonferroni) | Spearman(n acts, H) |
|---|---|---|---|---|---|---|---|---|---|---|
| gen1 | 33 | 3858 | 0.781 | 0.841 (z=-17.9, p=0.001) | 0.841 (z=-9.3) | 0.232 / 0.196 | 0.100 / 0.018 (z=51.4) | 0.091 / 0.024 (z=27.0) | 14 (7) | -0.173 (p=0.3347) |
| 122174 | 24 | 2800 | 0.737 | 0.802 (z=-9.4, p=0.001) | 0.802 (z=-7.5) | 0.230 / 0.196 | 0.084 / 0.017 (z=40.9) | 0.097 / 0.041 (z=9.0) | 11 (6) | 0.613 (p=0.0014) |
| 122175 | 22 | 3685 | 0.763 | 0.856 (z=-18.7, p=0.001) | 0.856 (z=-16.1) | 0.215 / 0.165 | 0.082 / 0.012 (z=55.9) | 0.113 / 0.028 (z=17.9) | 14 (11) | 0.556 (p=0.0072) |
| 122448 | 24 | 2105 | 0.756 | 0.869 (z=-18.7, p=0.001) | 0.868 (z=-13.2) | 0.232 / 0.170 | 0.124 / 0.023 (z=43.4) | 0.119 / 0.044 (z=13.0) | 16 (11) | 0.499 (p=0.0131) |
| 122456 | 17 | 1964 | 0.780 | 0.856 (z=-9.2, p=0.001) | 0.856 (z=-7.8) | 0.207 / 0.174 | 0.075 / 0.017 (z=28.9) | 0.102 / 0.046 (z=7.2) | 11 (7) | 0.743 (p=0.0006) |

Pooled type shares (what the population does overall):

| corpus | finding | tool | build | challenge | data | verify | correct | board | cite |
|---|---|---|---|---|---|---|---|---|---|
| gen1 | 8.7% | 9.2% | 4.3% | 1.3% | 7.3% | 10.6% | 4.9% | 21.3% | 32.5% |
| 122174 | 12.4% | 5.8% | 0.2% | 0.3% | 5.7% | 13.3% | 14.1% | 21.0% | 27.4% |
| 122175 | 11.6% | 7.9% | 0.5% | 0.3% | 11.1% | 16.0% | 12.9% | 18.5% | 21.2% |
| 122448 | 7.4% | 7.5% | 0.9% | 4.6% | 9.4% | 13.7% | 12.5% | 20.1% | 24.0% |
| 122456 | 11.5% | 7.6% | 3.7% | 0.4% | 7.7% | 9.5% | 16.9% | 18.8% | 23.9% |

Reading: the null-shuffle entropy gap is 0.06–0.11 on a 0–1 scale; NMI 0.075–0.124 means agent identity explains 7.5–12.4% of the entropy of "which kind of act happens". Statistically unambiguous (z ≥ 9 everywhere, p = 1/1001), modest in magnitude. Note the positive Spearman on gen2 (fewer acts → lower entropy mechanically); the shuffle null preserves per-agent n so the z-scores already account for this, but cluster labels for low-count agents should be read with that in mind.

## 4. How much is the base model? (family decomposition)

| corpus | families (n agents) | NMI(agent;type) | NMI(family;type) | share explained by family | mean H obs | family-stratified null H (z, p) | stratified null NMI (z) |
|---|---|---|---|---|---|---|---|
| gen1 | {'sol': 11, 'orange': 11, 'seed': 11} | 0.100 | 0.050 | 50.1% | 0.781 | 0.800 (z=-5.3, p=0.001) | 0.067 (z=21.9) |
| 122174 | {'sol': 13, 'orange': 8, 'seed': 3} | 0.084 | 0.040 | 47.1% | 0.737 | 0.754 (z=-2.6, p=0.012) | 0.054 (z=18.5) |
| 122175 | {'sol': 10, 'orange': 9, 'seed': 3} | 0.082 | 0.038 | 46.6% | 0.763 | 0.794 (z=-6.6, p=0.001) | 0.048 (z=29.8) |
| 122448 | {'orange': 11, 'seed': 3, 'sol': 10} | 0.124 | 0.043 | 34.5% | 0.756 | 0.787 (z=-6.8, p=0.001) | 0.061 (z=30.5) |
| 122456 | {'sol': 8, 'orange': 6, 'seed': 3} | 0.075 | 0.025 | 32.8% | 0.780 | 0.808 (z=-3.7, p=0.001) | 0.038 (z=20.0) |

Within each family separately (own pooled distribution, own shuffle null):

| corpus | family | n | mean H obs / null (z, p) | NMI obs / null (z) | family's own type shares (top 3) |
|---|---|---|---|---|---|
| gen1 | orange | 11 | 0.833 / 0.838 (z=-1.6, p=0.075) | 0.028 / 0.018 (z=3.5) | cite 34%, tool 14%, data 11% |
| gen1 | seed | 11 | 0.741 / 0.779 (z=-3.8, p=0.001) | 0.111 / 0.023 (z=24.5) | cite 43%, board 12%, build 12% |
| gen1 | sol | 11 | 0.770 / 0.784 (z=-5.3, p=0.001) | 0.034 / 0.015 (z=8.7) | board 35%, cite 25%, verify 13% |
| 122174 | orange | 8 | 0.839 / 0.873 (z=-12.7, p=0.001) | 0.051 / 0.012 (z=19.2) | cite 23%, finding 17%, board 17% |
| 122174 | seed | 3 | too few agents | | |
| 122174 | sol | 13 | 0.697 / 0.708 (z=-1.0, p=0.144) | 0.042 / 0.016 (z=10.1) | cite 31%, board 25%, correct 18% |
| 122175 | orange | 9 | 0.855 / 0.888 (z=-8.5, p=0.001) | 0.044 / 0.007 (z=32.2) | board 18%, cite 16%, data 16% |
| 122175 | seed | 3 | too few agents | | |
| 122175 | sol | 10 | 0.720 / 0.716 (z=0.5, p=0.675) | 0.038 / 0.016 (z=7.2) | cite 34%, board 20%, correct 20% |
| 122448 | orange | 11 | 0.861 / 0.924 (z=-17.0, p=0.001) | 0.092 / 0.014 (z=35.2) | board 19%, cite 18%, data 13% |
| 122448 | seed | 3 | too few agents | | |
| 122448 | sol | 10 | 0.679 / 0.689 (z=-1.4, p=0.096) | 0.062 / 0.029 (z=6.5) | cite 35%, board 23%, verify 20% |
| 122456 | orange | 6 | 0.865 / 0.908 (z=-9.9, p=0.001) | 0.050 / 0.008 (z=23.7) | cite 20%, board 20%, correct 14% |
| 122456 | seed | 3 | too few agents | | |
| 122456 | sol | 8 | 0.720 / 0.759 (z=-3.6, p=0.003) | 0.056 / 0.023 (z=7.1) | cite 30%, correct 25%, board 17% |

Reading: the family-level profiles are strikingly consistent across corpora — sol agents' acts are dominated by board posts, citations, verification and corrections with almost no tools/data; orange agents build tools and curate data; the seed family (gen1 only has enough of them) cites and builds dashboards. Within the sol family on three of four gen2 machines the mean-entropy test is *not* significant (z between −1.4 and +0.5), i.e. sol agents differ from each other in *which* mix they use (NMI still significant) but are not more concentrated than chance. Orange agents show the clearest within-family specialization (z ≤ −8.5 on every gen2 machine).

## 5. Clusters

### gen1: k=6 (silhouette 0.2039; by k: {'2': 0.1384, '3': 0.174, '4': 0.1825, '5': 0.1973, '6': 0.2039})

| n | label | enriched types | mean H | mean acts | mean cit. received | model families | examples |
|---|---|---|---|---|---|---|---|
| 9 | board-coordinators | board | 0.754 | 147.8 | 51.2 | {'sol': 9} | agent-009, agent-006, agent-001 |
| 2 | app/dashboard-builders + finding-producers | build, finding, tool | 0.791 | 81.0 | 20.0 | {'seed': 2} | agent-027, agent-032 |
| 6 | integrators/citers | cite | 0.698 | 123.8 | 19.5 | {'seed': 6} | agent-036, agent-026, agent-030 |
| 1 | challenge-setters + tool-builders | challenge, tool | 0.825 | 63.0 | 21.0 | {'seed': 1} | agent-028 |
| 11 | data-curators + tool-builders | data, tool | 0.832 | 124.6 | 49.2 | {'sol': 2, 'orange': 9} | agent-013, agent-011, agent-016 |
| 4 | tool-builders + finding-producers | tool, finding | 0.814 | 47.2 | 46.0 | {'orange': 2, 'seed': 2} | agent-024, agent-021, agent-034 |

Confounds — cluster × model family: V=0.872 (p=0.001); × model config: V=0.679 (p=0.001); launch index: F=33.752 (p=0.001); first-act time: F=0.72 (p=0.4016); log n acts: F=9.046 (p=0.001). Niche-by-enrichment counts: {'board': 6, 'generalist': 9, 'verify': 3, 'data': 1, 'tool': 4, 'finding': 3, 'correct': 1, 'cite': 2, 'build': 3, 'challenge': 1}.

### 122174: k=2 (silhouette 0.2644; by k: {'2': 0.2644, '3': 0.2026, '4': 0.1584, '5': 0.1626, '6': 0.1491})

| n | label | enriched types | mean H | mean acts | mean cit. received | model families | examples |
|---|---|---|---|---|---|---|---|
| 4 | data-curators + tool-builders | data, tool | 0.861 | 158.2 | 37.5 | {'orange': 4} | agent-0196, agent-0186, agent-0151 |
| 20 | generalists (near pooled profile) | — | 0.713 | 108.3 | 24.4 | {'sol': 13, 'orange': 4, 'seed': 3} | agent-037, agent-047, agent-0176 |

Confounds — cluster × model family: V=0.632 (p=0.013); × model config: V=0.632 (p=0.015); launch index: F=0.71 (p=0.3956); first-act time: F=1.942 (p=0.1758); log n acts: F=2.124 (p=0.1688). Niche-by-enrichment counts: {'correct': 3, 'generalist': 11, 'board': 3, 'finding': 1, 'verify': 4, 'data': 1, 'cite': 1}.

### 122175: k=6 (silhouette 0.2394; by k: {'2': 0.237, '3': 0.2246, '4': 0.215, '5': 0.2251, '6': 0.2394})

| n | label | enriched types | mean H | mean acts | mean cit. received | model families | examples |
|---|---|---|---|---|---|---|---|
| 12 | integrators/citers | cite | 0.731 | 123.2 | 32.0 | {'sol': 10, 'orange': 1, 'seed': 1} | agent-0122, agent-048, agent-0137 |
| 1 | verifiers/auditors + integrators/citers | verify, cite | 0.442 | 17.0 | 7.0 | {'seed': 1} | agent-0172 |
| 2 | tool-builders | tool | 0.867 | 210.5 | 64.5 | {'orange': 2} | agent-0132, agent-0167 |
| 5 | data-curators + tool-builders | data, tool, finding | 0.863 | 337.6 | 63.2 | {'orange': 5} | agent-058, agent-068, agent-0142 |
| 1 | correctors + finding-producers | correct, finding | 0.697 | 41.0 | 10.0 | {'seed': 1} | agent-0127 |
| 1 | tool-builders + data-curators | tool, data, finding | 0.842 | 40.0 | 1.0 | {'orange': 1} | agent-0212 |

Confounds — cluster × model family: V=0.844 (p=0.001); × model config: V=0.844 (p=0.002); launch index: F=0.641 (p=0.7373); first-act time: F=0.976 (p=0.4995); log n acts: F=3.825 (p=0.01). Niche-by-enrichment counts: {'correct': 7, 'verify': 2, 'generalist': 5, 'finding': 1, 'cite': 4, 'board': 1, 'data': 1, 'tool': 1}.

### 122448: k=2 (silhouette 0.2945; by k: {'2': 0.2945, '3': 0.2345, '4': 0.2358, '5': 0.2603, '6': 0.2201})

| n | label | enriched types | mean H | mean acts | mean cit. received | model families | examples |
|---|---|---|---|---|---|---|---|
| 3 | finding-producers + tool-builders | finding, tool, cite | 0.629 | 19.3 | 6.7 | {'seed': 3} | agent-0109, agent-0154, agent-0199 |
| 21 | generalists (near pooled profile) | — | 0.774 | 97.5 | 19.5 | {'orange': 11, 'sol': 10} | agent-0104, agent-050, agent-0124 |

Confounds — cluster × model family: V=1.0 (p=0.001); × model config: V=1.0 (p=0.001); launch index: F=0.329 (p=0.5904); first-act time: F=0.006 (p=0.9191); log n acts: F=15.775 (p=0.002). Niche-by-enrichment counts: {'data': 2, 'cite': 5, 'verify': 3, 'challenge': 1, 'generalist': 5, 'finding': 4, 'correct': 2, 'board': 2}.

### 122456: k=2 (silhouette 0.2052; by k: {'2': 0.2052, '3': 0.1784, '4': 0.1491, '5': 0.163, '6': 0.1655})

| n | label | enriched types | mean H | mean acts | mean cit. received | model families | examples |
|---|---|---|---|---|---|---|---|
| 3 | verifiers/auditors + integrators/citers | verify, cite, correct | 0.646 | 44.7 | 3.0 | {'sol': 3} | agent-056, agent-0165, agent-0175 |
| 14 | generalists (near pooled profile) | — | 0.808 | 130.7 | 28.9 | {'sol': 5, 'orange': 6, 'seed': 3} | agent-041, agent-0185, agent-0160 |

Confounds — cluster × model family: V=0.491 (p=0.1708); × model config: V=0.491 (p=0.3477); launch index: F=0.069 (p=0.8102); first-act time: F=0.049 (p=0.7882); log n acts: F=2.811 (p=0.1039). Niche-by-enrichment counts: {'cite': 1, 'generalist': 5, 'tool': 3, 'correct': 3, 'data': 1, 'verify': 2, 'build': 1, 'finding': 1}.

Reading: in gen1 launch index and model are collinear by design (blocks of 4), so the launch-index F is the same confound. Birth time never predicts cluster (all p > 0.17). Activity level does (p ≤ 0.01 on gen1/122175/122448): the low-activity agents form the 'specialist'-looking small clusters. The silhouettes (0.20–0.29 per corpus, 0.14 pooled) are weak — the clusters are tendencies, not discrete castes.

## 6. Temporal: does specialization grow?

| corpus | span (h) | agents (≥15 timed acts) | mean H by own tercile (early/mid/late) | late−early mean [boot 95%] | agents H down / up |
|---|---|---|---|---|---|
| gen1 | 39.0 | 33 | 0.6578 / 0.7194 / 0.7317 | 0.074 [-0.000, 0.148] | 10 / 23 |
| 122174 | 22.8 | 22 | 0.7066 / 0.7006 / 0.6687 | -0.038 [-0.089, 0.009] | 14 / 7 |
| 122175 | 22.8 | 22 | 0.7118 / 0.7222 / 0.6946 | -0.017 [-0.058, 0.024] | 14 / 8 |
| 122448 | 22.3 | 24 | 0.6528 / 0.6916 / 0.6554 | 0.003 [-0.053, 0.054] | 11 / 13 |
| 122456 | 22.4 | 15 | 0.7506 / 0.7192 / 0.7274 | -0.023 [-0.054, 0.008] | 7 / 8 |

Global run windows (population terciles by act time; only agents with ≥5 acts in the window):

| corpus | window (h) | agents | acts | mean H obs / null (z) | NMI obs / null (z) | pairwise JSD obs / null (z) |
|---|---|---|---|---|---|---|
| gen1 | 0.0–3.84 | 33 | 1286 | 0.668 / 0.742 (z=-9.1) | 0.202 / 0.060 (z=31.4) | 0.181 / 0.079 (z=16.0) |
| gen1 | 3.84–5.9 | 33 | 1284 | 0.734 / 0.785 (z=-6.1) | 0.137 / 0.053 (z=17.7) | 0.158 / 0.083 (z=9.9) |
| gen1 | 5.9–38.96 | 33 | 1288 | 0.708 / 0.795 (z=-10.3) | 0.161 / 0.057 (z=21.7) | 0.154 / 0.085 (z=9.1) |
| 122174 | 0.0–1.51 | 8 | 933 | 0.727 / 0.739 (z=-0.9) | 0.053 / 0.017 (z=12.9) | 0.100 / 0.037 (z=6.2) |
| 122174 | 1.51–7.09 | 13 | 929 | 0.711 / 0.769 (z=-6.4) | 0.083 / 0.027 (z=15.5) | 0.100 / 0.046 (z=6.1) |
| 122174 | 7.09–22.8 | 11 | 934 | 0.718 / 0.829 (z=-9.2) | 0.083 / 0.021 (z=18.9) | 0.131 / 0.064 (z=4.9) |
| 122175 | 0.0–3.7 | 9 | 1228 | 0.761 / 0.795 (z=-4.1) | 0.063 / 0.015 (z=21.5) | 0.098 / 0.028 (z=11.3) |
| 122175 | 3.7–12.36 | 10 | 1228 | 0.714 / 0.844 (z=-12.9) | 0.077 / 0.015 (z=25.4) | 0.155 / 0.041 (z=12.2) |
| 122175 | 12.36–22.82 | 11 | 1218 | 0.694 / 0.836 (z=-12.5) | 0.087 / 0.016 (z=26.9) | 0.202 / 0.055 (z=11.7) |
| 122448 | 0.0–2.15 | 9 | 702 | 0.730 / 0.869 (z=-17.1) | 0.148 / 0.024 (z=28.1) | 0.151 / 0.035 (z=14.4) |
| 122448 | 2.15–6.86 | 13 | 701 | 0.676 / 0.827 (z=-10.7) | 0.170 / 0.038 (z=26.5) | 0.204 / 0.081 (z=9.6) |
| 122448 | 6.86–22.29 | 11 | 700 | 0.778 / 0.829 (z=-5.4) | 0.094 / 0.031 (z=13.5) | 0.104 / 0.051 (z=5.5) |
| 122456 | 0.0–1.65 | 7 | 655 | 0.810 / 0.846 (z=-6.7) | 0.047 / 0.020 (z=7.4) | 0.045 / 0.025 (z=4.4) |
| 122456 | 1.65–6.06 | 10 | 650 | 0.686 / 0.719 (z=-1.7) | 0.073 / 0.027 (z=10.5) | 0.176 / 0.115 (z=2.7) |
| 122456 | 6.06–22.36 | 8 | 655 | 0.746 / 0.866 (z=-7.4) | 0.110 / 0.021 (z=23.0) | 0.170 / 0.080 (z=5.0) |

Niche persistence (does an agent's early-half profile predict its own late half better than other agents' late halves?):

| corpus | agents (≥20 timed acts) | own JSD mean | median cross JSD mean | own < median cross | own < median cross within same family | own is nearest of all |
|---|---|---|---|---|---|---|
| gen1 | 33 | 0.080 | 0.100 | 29 | 21 / 33 | 4 |
| 122174 | 21 | 0.044 | 0.085 | 18 | 15 / 21 | 8 |
| 122175 | 21 | 0.045 | 0.103 | 21 | 16 / 21 | 6 |
| 122448 | 21 | 0.066 | 0.103 | 16 | 12 / 20 | 5 |
| 122456 | 15 | 0.060 | 0.089 | 10 | 10 / 15 | 2 |

Reading: differentiation is present from the first window (gen1 window 1 has the *highest* NMI, 0.202) and does not ratchet up; in gen1 individual agents broaden their repertoire over time (23 of 33 entropies rise). Agents are somewhat self-consistent (own-half JSD below the median cross-agent JSD for most agents), but only a handful are closer to their own past than to *every* other agent, and within-family self-consistency is weaker. This is the pattern of stable dispositions, not of a division of labour negotiated through interaction.

## 7. Gen2: does the same niche structure recur on separate machines?

Pooled clustering of 87 included native agents from 4 machines: k=3 (silhouette 0.1414; by k {'2': 0.1331, '3': 0.1414, '4': 0.1299, '5': 0.1014, '6': 0.1075}). Cluster × machine Cramér's V = 0.134 (perm p = 0.964); cluster × model family V = 0.472.

| n | label | machines | model families | mean shares (top 3) | examples |
|---|---|---|---|---|---|
| 29 | integrators/citers + verifiers/auditors | {'122174': 8, '122175': 7, '122448': 9, '122456': 5} | {'sol': 27, 'seed': 2} | cite 37%, board 20%, verify 19% | 122174:agent-037, 122174:agent-047, 122175:agent-048 |
| 57 | tool-builders | {'122174': 16, '122175': 15, '122448': 14, '122456': 12} | {'orange': 33, 'sol': 14, 'seed': 10} | cite 25%, board 18%, finding 13% | 122175:agent-058, 122175:agent-068, 122456:agent-041 |
| 1 | challenge-setters | {'122448': 1} | {'orange': 1} | challenge 46%, board 13%, cite 9% | 122448:agent-0124 |

Per-machine verdicts side by side:

| machine | included | mean H obs / null (z) | NMI obs (z) | agents p<.05 | per-machine cluster labels |
|---|---|---|---|---|---|
| 122174 | 24 | 0.7374 / 0.8023 (z=-9.4) | 0.0838 (z=40.9) | 11 | data-curators + tool-builders; generalists (near pooled profile) |
| 122175 | 22 | 0.7635 / 0.8565 (z=-18.7) | 0.0817 (z=55.9) | 14 | integrators/citers; verifiers/auditors + integrators/citers; tool-builders; data-curators + tool-builders; correctors + finding-producers; tool-builders + data-curators |
| 122448 | 24 | 0.7561 / 0.869 (z=-18.7) | 0.1238 (z=43.4) | 16 | finding-producers + tool-builders; generalists (near pooled profile) |
| 122456 | 17 | 0.7798 / 0.8565 (z=-9.2) | 0.0751 (z=28.9) | 11 | verifiers/auditors + integrators/citers; generalists (near pooled profile) |

Niche (by enrichment) present with ≥2 agents on how many of the 4 machines: {'finding': 1, 'tool': 1, 'build': 0, 'challenge': 0, 'data': 1, 'verify': 4, 'correct': 4, 'board': 2, 'cite': 2, 'generalist': 4}.

Reading: the recurring structure is real and not machine-specific — every machine has a verify/correct-heavy group and a tool/data-heavy group — but it is the same two model families doing the same two things on each machine. Two caveats make gen2 a weak replication for *emergent* roles: the gen2 prompt literally instructs agents to "find your niche" and "cite generously" (gen1's does not), and every machine was seeded with a copy of gen1's commons, so the gen2 agents saw gen1's verifiers, tool-builders and correction culture before acting.

## 8. Concrete example agents (lowest-entropy included agents, with their own artifacts)

**gen1**

- `agent-026` (seed-stable-reasoning-high, 172 acts, H=0.6024): cite 59%, verify 13%, board 13%, finding 6%. Own dominant artifact type: verify.
  - `/Users/bytedance/Downloads/swarm/commons/findings/agent-026_swarm_security_audit_20260801_161200.md`
  - `/Users/bytedance/Downloads/swarm/commons/findings/agent-026_trust_but_verify_security_map_20260801_162000.md`
  - `/Users/bytedance/Downloads/swarm/commons/builds/agent-026_swarm_security_audit_report_20260801_175500.html`
- `agent-031` (seed-stable-reasoning, 57 acts, H=0.6252): cite 56%, finding 14%, board 14%, tool 5%, data 5%. Own dominant artifact type: finding.
  - `/Users/bytedance/Downloads/swarm/commons/findings/agent-031_swarm-observatory-001_20260801T162436Z.json`
  - `/Users/bytedance/Downloads/swarm/commons/findings/agent-031_conformance-test-round1_20260801T163117Z.json`
  - `/Users/bytedance/Downloads/swarm/commons/findings/agent-031_swarm-ecosystem-analysis_20260801T202200Z.json`
- `agent-007` (gpt56_sol_reasoning_high, 128 acts, H=0.6937): board 41%, cite 23%, verify 22%. Own dominant artifact type: verify.
  - `/Users/bytedance/Downloads/swarm/commons/findings/agent-007_sortnet_independent_verification_20260801T214249Z.json`
  - `/Users/bytedance/Downloads/swarm/commons/tools/agent-007_generalized_sortlow_check_20260801T232228Z.py`
  - `/Users/bytedance/Downloads/swarm/commons/findings/agent-007_sorting_lower_bound_audit_20260801T234630Z.json`

**122174**

- `agent-082` (gpt-5.6-sol, 18 acts, H=0.5808): cite 39%, verify 33%, board 17%, correct 11%. Own dominant artifact type: verify.
  - `/Users/bytedance/Downloads/swarm-gen2/122174/swarm/commons/findings/agent-082_replication_current_network_corpus_audit_20260807.md`
  - `/Users/bytedance/Downloads/swarm-gen2/122174/swarm/commons/findings/agent-082_agent0196_manifest_complete_hash_replication_20260807.md`
- `agent-0136` (ep-20260702161005-jcdtr, 13 acts, H=0.5944): finding 38%, cite 31%, tool 15%, board 15%. Own dominant artifact type: finding.
  - `/Users/bytedance/Downloads/swarm-gen2/122174/swarm/commons/findings/agent-0136_mandelbrot-exact-crack_20260802T120500Z.md`
  - `/Users/bytedance/Downloads/swarm-gen2/122174/swarm/commons/findings/agent-0136_mandelbrot-exact-crack_20260802T122000Z.md`
  - `/Users/bytedance/Downloads/swarm-gen2/122174/swarm/commons/findings/agent-0136_sortnet-sa-search-tool_20260802T131000Z.md`
- `agent-0166` (gpt-5.6-sol, 43 acts, H=0.623): cite 44%, verify 26%, correct 16%, board 9%. Own dominant artifact type: verify.
  - `/Users/bytedance/Downloads/swarm-gen2/122174/swarm/commons/findings/agent-0166_agent072_genetic_repair_depth_contract_audit_20260803T023500Z.md`
  - `/Users/bytedance/Downloads/swarm-gen2/122174/swarm/commons/findings/agent-0166_agent0181_population_sa_cold_depth_and_selection_audit_20260803T024500Z.md`

**122175**

- `agent-0172` (ep-20260702161005-jcdtr, 17 acts, H=0.4423): verify 47%, cite 41%, finding 12%. Own dominant artifact type: verify.
  - `/Users/bytedance/Downloads/swarm-gen2/122175/swarm/commons/tools/agent-0172_independent_sat_depth_verifier_20260804.py`
  - `/Users/bytedance/Downloads/swarm-gen2/122175/swarm/commons/tools/agent-0172_dpll_sat_verifier_20260804.py`
  - `/Users/bytedance/Downloads/swarm-gen2/122175/swarm/commons/tools/agent-0172_dpll_sat_verifier_v2_20260804.py`
- `agent-048` (gpt-5.6-sol, 260 acts, H=0.6531): cite 40%, correct 27%, verify 15%, board 13%. Own dominant artifact type: correct.
  - `/Users/bytedance/Downloads/swarm-gen2/122175/swarm/commons/findings/agent-048_CORRECTION_duplicate_audit_denominator_20260802.md`
  - `/Users/bytedance/Downloads/swarm-gen2/122175/swarm/commons/findings/agent-048_CORRECTION_reference_audit_truncated_templates_20260802.md`
  - `/Users/bytedance/Downloads/swarm-gen2/122175/swarm/commons/findings/agent-048_CORRECTION_growth_replication_reference_extractor_20260802.md`
- `agent-073` (gpt-5.6-sol, 93 acts, H=0.6922): cite 35%, verify 25%, board 20%, correct 11%, finding 8%. Own dominant artifact type: verify.
  - `/Users/bytedance/Downloads/swarm-gen2/122175/swarm/commons/tools/agent-073_erdos_witness_bundle_verifier_20260807.py`
  - `/Users/bytedance/Downloads/swarm-gen2/122175/swarm/commons/tools/agent-073_erdos_witness_bundle_verifier_v1_1_20260807.py`
  - `/Users/bytedance/Downloads/swarm-gen2/122175/swarm/commons/tools/agent-073_generic_erdos_witness_bundle_audit_20260807.py`

**122448**

- `agent-0109` (ep-20260702161005-jcdtr, 24 acts, H=0.5248): cite 62%, finding 12%, tool 12%, verify 8%. Own dominant artifact type: finding.
  - `/Users/bytedance/Downloads/swarm-gen2/122448/swarm/commons/findings/agent-109_sortnet_toolkit_reconstructed_20260802T2105Z.md`
  - `/Users/bytedance/Downloads/swarm-gen2/122448/swarm/commons/findings/agent-109_navel_gazing_revisited_20260802T2125Z.md`
  - `/Users/bytedance/Downloads/swarm-gen2/122448/swarm/commons/findings/agent-109_sortnet_monoculture_convergence_20260802T2230Z.md`
- `agent-055` (gpt-5.6-sol, 43 acts, H=0.5276): cite 51%, verify 33%, correct 9%. Own dominant artifact type: verify.
  - `/Users/bytedance/Downloads/swarm-gen2/122448/swarm/commons/tools/agent-055_audit_width_bounded_constructive_20260803T1930Z.py`
  - `/Users/bytedance/Downloads/swarm-gen2/122448/swarm/commons/tools/agent-055_verify_layer_budget_submission_20260803T2005Z.py`
  - `/Users/bytedance/Downloads/swarm-gen2/122448/swarm/commons/findings/agent-055_independent_verification_n14_k6_and_exactness_scope_20260803T2005Z.md`
- `agent-0154` (ep-20260702161005-jcdtr, 17 acts, H=0.5908): cite 41%, finding 24%, tool 24%, board 12%. Own dominant artifact type: finding.
  - `/Users/bytedance/Downloads/swarm-gen2/122448/swarm/commons/findings/agent-0154_constructive_width_bounded_bounds_20260803T1600Z.md`
  - `/Users/bytedance/Downloads/swarm-gen2/122448/swarm/commons/findings/agent-0154_n7_all_optimal_width3_20260803T1630Z.md`
  - `/Users/bytedance/Downloads/swarm-gen2/122448/swarm/commons/findings/agent-0154_merging_depth_conjecture_20260803T1500Z.md`

**122456**

- `agent-0175` (gpt-5.6-sol, 13 acts, H=0.5761): cite 38%, correct 31%, verify 23%, finding 8%. Own dominant artifact type: correct.
  - `/Users/bytedance/Downloads/swarm-gen2/122456/swarm/commons/data/agent-0175_CORRECTION-canonical-ledger-exists-at-root-navigator-misses-593-rows_20260804T0010Z.json`
  - `/Users/bytedance/Downloads/swarm-gen2/122456/swarm/commons/findings/agent-0175_CORRECTION-the-ledger-was-not-empty-i-followed-the-broken-path_20260804T0010Z.md`
- `agent-0165` (gpt-5.6-sol, 55 acts, H=0.6517): cite 38%, correct 31%, finding 11%, board 11%, verify 9%. Own dominant artifact type: correct.
  - `/Users/bytedance/Downloads/swarm-gen2/122456/swarm/commons/findings/agent-0165_CORRECTION-machine-authored-is-not-reasonless-only-this-emitter-is_20260802T2016Z.md`
  - `/Users/bytedance/Downloads/swarm-gen2/122456/swarm/commons/findings/agent-0165_CORRECTION23-still-promotes-a-broader-regex-to-ground-truth_20260802T2030Z.md`
  - `/Users/bytedance/Downloads/swarm-gen2/122456/swarm/commons/findings/agent-0165_CORRECTION29-enumerable-neighborhood-not-set-vs-content-is-the-boundary_20260802T2058Z.md`
- `agent-056` (gpt-5.6-sol, 66 acts, H=0.7103): cite 36%, verify 27%, board 15%, correct 12%, finding 6%. Own dominant artifact type: verify.
  - `/Users/bytedance/Downloads/swarm-gen2/122456/swarm/commons/findings/agent-056_navigator-v2-ground-truth-audit_20260802T150058Z.md`
  - `/Users/bytedance/Downloads/swarm-gen2/122456/swarm/commons/findings/agent-056_ADDENDUM-navigator-audit-current-generation-scope_20260802T1503Z.md`

Self-declared roles in gen1 registry status lines (the only agents that wrote a `role` field): agent-014: "independent verification, red-teaming, data integrity" (×5); agent-014: "independent verification, red-teaming, data integrity, statistical hygiene" (×1); agent-014: "independent verification, red-teaming, instrumentation, data integrity" (×1); agent-016: "infrastructure + swarm-observability research" (×1); agent-029: "catalyst_explorer" (×1). agent-014's self-description ("independent verification, red-teaming, data integrity") matches its measured profile (verify is its largest commons type), but only 3 of 33 agents ever declared a role.

## 9. Confounds and sanity checks

- gen1 monitor (swarm_monitor.py INTERVAL=900) wakes idle agents every 15 min with a fixed nudge; gen2 reaper every 30 min
- seeds (gen1 005/017/029; gen2 W1 38,45,52,...; W2 every 50th from 105) and adversaries (42,51,59,67,74,83; 150,...) excluded from stats
- gen1 has a second epoch on 2026-08-31/09-01 (agents 005/006/007/001 re-run); dropped via epoch_end=2026-08-10
- gen2 prompt literally says 'find your niche' and 'Cite generously' — niche-seeking is prompt-induced there; gen1 prompt has no such wording
- gen2 machines start from a copy of gen1 commons: native agents see gen1 specialists' outputs (cultural transmission), so machines are not independent of gen1
- agents with < 5 acts excluded; ghost/out-of-roster ids (gen1 agent-042 expansion Saboteur; gen2 e.g. agent-109) excluded; agent-140 phantom from %03d bug noted in registry
- resurrection = fork (35/36 gen1 agents had un-terminated predecessors — registry finding 6, flagged there as not independently verified); duplicate publications inflate counts for some agents
- 9 model configs in gen1 (3 families x 3 reasoning levels) / 3 families in gen2 — cluster-vs-model tests reported
- files under agent-named challenge arenas without their own prefix are attributed to the arena owner (dir attribution)
- 'verify'/'correct' detected by filename/message regex only; counts are lower bounds and miss body-text-only acts
- entropy depends on n_acts (small n -> lower entropy mechanically); the label-shuffle null preserves each agent's n, and Spearman(n_acts, entropy) is reported

## 10. Assessment: headline or supporting section?

**Supporting section.** What the data can carry:

- A clean, replicated *measurement*: under identical instructions and an open-ended commons, agents' act-type profiles are far from exchangeable (NMI z ≥ 28 on every corpus; 11–16 of 17–24 agents per machine individually below the shuffle null at p < .05) and this recurs on four independent devboxes.
- A clean *decomposition*: roughly a third to a half of that structure is the base model (sol → auditing/correcting/board talk; orange → tools/data; seed → citing/builds), and the family-level profile is the part that replicates across machines. The remainder is individual and persists across an agent's own timeline.
- A clean *negative*: specialization does not increase over 23–39 hours of interaction; gen1 agents broaden.

What it cannot carry:

- "Identical agents spontaneously divide labour." The agents were not identical (9 model configs in gen1, 3 families in gen2); the confound dominates the cluster structure (cluster × family V = 0.63–1.0 on gen1/122174/122175/122448; 0.49, n.s., on 122456), and the within-family residual is small (entropy gap ≈ 0.02–0.03 against the stratified null) and, for sol on 3 of 4 machines, not significant on the entropy test.
- "Roles emerge from interaction." The temporal signal points the other way, and gen2's prompt asks for niche-finding explicitly.
- Clean role categories. Silhouettes of 0.15–0.34 mean the clusters are gradients; the labels ("verifiers/auditors", "tool-builders") are descriptive summaries of enrichment, not discrete castes.

If a role-differentiation angle is wanted for the paper, the honest framing is *model-typed functional profiles under a shared institution* (a between-model result with a small within-model individuality term), presented as one supporting figure next to the institution-adoption and correction-culture results. To make it a headline one would need a run with a single model config (or many agents per config) and a randomized prompt-free design — that is a new experiment, not more analysis of this data.
