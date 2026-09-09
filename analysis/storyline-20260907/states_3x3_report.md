# SwarmWorld-style role states + 3×3 family×level profiles (gen1, zero-cost, local data)

Script: `swarm_states_3x3.py` · numbers: `swarm_states_3x3_results.json` · act table imported from `swarm_role_diff.py` and asserted identical (3858 acts, 33 included agents; seeds 005/017/029 and 042 excluded; acts ≥ 2026-08-10 dropped; bare times = EDT). No sklearn on this machine: k-means is a numpy re-implementation (k-means++, n_init=32, seed 20260907).

## Analysis 1 — role states (arXiv 2608.26081 pipeline, filesystem analogue)

**Rows.** 2-hour windows over the 39.0 h run (20 windows, 2026-08-01T16:22Z → 08-03T07:20Z). One row per agent × window with ≥3 timed acts: **223 rows, 33 agents** (81 agent-windows with 1–2 acts not clustered; 0 untimed acts). Windows 6, 12, 13 (hours 12–14, 24–28) have no rows at all; rows per window fall from 30–33 (hours 0–8) to 2–18 later. 19 features per row: rate/h of the 9 act types, citations given/received, distinct cited/citers, tool adopters, fraction of acts on others' artifacts, fraction new-artifact, mean log file size, artifact proximity, distinct other agents engaged; log1p on counts/rates, RobustScaler(5,95), clip ±10; no feature had zero variance.

**k selection.** Silhouette k=2..6: **0.246, 0.195, 0.183, 0.193, 0.164 → k=2**. Column-shuffle null (200 draws, best k per draw): null mean 0.182, p95 0.222, max 0.476 → observed 0.246 has **p = 0.050**. The two-mode structure is real but weak (comparable to SwarmWorld's own low silhouettes).

**Hierarchical split.** Top k=2: 162 / 61 rows (silhouette 0.249). Mode 0 splits 113/49 (within-mode silhouette 0.227). Mode 1's split would be 51/10 = 4.5 % < 5 % occupancy rule → not split. Final **3 states** (silhouette 0.192); forcing 4 states gives 49/113/10/51, silhouette 0.193 (no gain).

| state | rows (share) | agents | acts/row | label (enrichment vs pooled) |
|---|---|---|---|---|
| S0 | 113 (0.507) | 31 | 10.1 | low-intensity **citer/integrator**: proximity ×1.33, on-others ×1.12; cites-out 4.4/row, 59 % of acts touch others' artifacts |
| S1 | 49 (0.220) | 25 | 8.0 | low-intensity **artifact producer**: challenge ×2.66, new-artifact ×1.60 (62 % of acts create files), cites-out 0.45/row, proximity 0.12 |
| S2 | 61 (0.274) | 29 | 36.3 | **high-intensity hub**: build ×2.75, cites-in ×2.59, tool-adopters ×2.55, verify ×2.39, distinct citers ×2.39; verify 2.1/h, correct 0.95/h, 6.2 distinct citers per window |

**Occupancy by window (does the population shift?)** S2 fractions: window0 0.367, w1 0.576, w2 **0.848**, w3 0.207, then **0.000 in every window from hour 8 on**. S0 rises from 0.37 (w0) to 0.62–1.00 in windows 3–19; S1 stays 0.15–0.50 throughout. Early third (w0–5, 131 rows) = [S0 0.351, S1 0.183, S2 0.466]; late third (w14–19, 42 rows) = [0.738, 0.262, 0.000]. State × window Cramér's V = 0.533, row-shuffle p = 0.001. So the shift is not "survey/board → build": it is a **burst → steady-state** succession: an early high-intensity hub state in which verification, correction, building and citation all peak, followed by a low-intensity regime of citers vs producers.

**Phase or division of labour?** Within-window state entropy (normalised, 14 windows with ≥4 rows): observed mean **0.590** vs pooled 0.939 (ratio 0.63) vs window-shuffle null 0.823 [0.746, 0.897], **p = 0.001** — below null, so there is a population-wide component. But 2.21 states are present per window on average, all 3 in 4 windows, a single state in only 1. Removing the burst state S2 (162 rows left): state × window V = 0.310, **p = 0.50**; within-window entropy 0.822 vs pooled 0.884; S0 and S1 co-occur in **13/14** windows. **Verdict (JSON `verdict`): MIXED — the population-wide phase is the intensity burst of the first 8 hours; underneath it, and for the remaining 31 hours, citers/integrators and artifact producers are different agents at the same time (division of labour), with no further time trend.**

**Switching.** Per-agent state-switch rate between consecutive occupied windows: mean 0.444 (median 0.429; adjacent windows only 0.489) vs row-shuffle null 0.624 [p2.5 = 0.560] — agents switch less than chance but far from never; mean modal-state share 0.592, 25/33 agents spend ≥50 % of their windows in one state. Consistent with SwarmWorld: states are modes agents move through, not fixed identities.

**Stability.** Leave-agent-out ARI: mean **0.920** (min 0.761 agent-028, max 1.0). Leave-family-out ARI: sol 0.794, orange **0.461**, seed 0.699 — the orange rows carry a disproportionate share of the S2 structure. Anti-circularity refit on file-only features (7 type rates + new-artifact + size; no board/citation features): silhouette k=2..6 = 0.264/0.297/0.309/0.184/0.193, 3 states, ARI vs full states 0.455; the S2 hub is recovered (54/61 rows map to one file-only state) while S0/S1 (citing vs producing) blur (102 vs 33 of the S0/S1 rows land in the same file-only state).

**States × model.** Rows: S0 sol 36 / orange 39 / seed 38; S1 16/15/18; S2 24/26/**11**. Cramér's V(state, family) = 0.116, agent-level permutation **p = 0.284**; V(state, level) = 0.096, p = 0.51. Modal state per agent × family: sol S0 7/S1 1/S2 3; orange 7/1/3; seed 6/5/0 (V = 0.341, p = 0.103). Window-states are therefore not a model-family artefact; the only hint is that seed agents rarely reach the hub state (11 rows, 0 modal). Whole-run rows clustered on their own (33 rows) behave differently: top split is a 1-vs-32 outlier (agent-028; silhouette 0.569), sub-split 12/20 with all 11 orange agents in one state (V = 0.432, p = 0.009) — whole-run profiles do carry family, window-states do not.

**agent-020 / agent-022.** Both orange. agent-020 (orange/L2): windows 0→S0, 1→S1, 2→S2, then S0 (modal S0). agent-022 (orange/L1): S0, then S2 in windows 1–3 (hours 2–8), then S0, S1 (modal S0). Both passed through the hub state during the burst; neither is a permanent hub.

## Analysis 2 — 3×3 family × reasoning-level cells (33 agents)

Levels from the model string: L3 = xhigh / thinking_max / reasoning-high; L2 = reasoning_high / thinking / reasoning; L1 = plain. The three SEED_EXTRA agents (005/017/029) are all L2, one per family, so every L2 cell has 3 agents, every other cell 4.

| cell | n | acts | acts/agent | board | cite | tool | verify+correct (pooled) | cites-in/act | tool adopters | entropy mean (sd) |
|---|---|---|---|---|---|---|---|---|---|---|
| sol/L3 | 4 | 512 | 128 | .441 | .186 | .066 | .127 | .201 | 33 | .749 (.015) |
| sol/L2 | 3 | 465 | 155 | .355 | .245 | .049 | **.241** | .538 | 29 | .750 (.049) |
| sol/L1 | 4 | 620 | 155 | .282 | .306 | .055 | .189 | .274 | 42 | .807 (.050) |
| orange/L3 | 4 | 529 | 132 | .100 | .331 | .147 | .180 | .429 | 42 | .830 (.029) |
| orange/L2 | 3 | 337 | 112 | .104 | .412 | .145 | .148 | .427 | 29 | .804 (.017) |
| orange/L1 | 4 | 365 | 91 | .107 | .277 | .129 | .225 | **.712** | 44 | **.857** (.046) |
| seed/L3 | 4 | 428 | 107 | .114 | .430 | .098 | .082 | .222 | 19 | .729 (.100) |
| seed/L2 | 3 | 237 | 79 | .160 | .439 | .080 | .051 | .232 | 14 | .725 (.088) |
| seed/L1 | 4 | 365 | 91 | .115 | .416 | .079 | .074 | .164 | 12 | .766 (.056) |

(Full 9-type shares per cell in JSON `cells[*].act_type_shares`; seed/L1 build share .189 is the only build-heavy cell.)

**Two-way permutation ANOVA** (type II, Freedman–Lane, 5000 perms; df 2,24 for mains, 4,24 interaction):

| response | family F (p, η²) | level F (p, η²) | interaction F (p, η²) |
|---|---|---|---|
| normalised entropy | 7.48 (**0.002**, .34) | 2.44 (0.112, .11) | 0.10 (0.983, .01) |
| verify+correct share | 18.33 (**0.0002**, .52) | 1.08 (0.360, .03) | 1.92 (0.137, .11) |
| cite share | 6.49 (**0.007**, .29) | 1.38 (0.276, .06) | 1.29 (0.299, .12) |

Marginals: entropy sol .770 / orange .833 / seed .741; verify+correct sol .180 / orange .182 / **seed .064**; cite share sol .245 / orange .335 / seed .390. Level marginals: entropy L3 .769 / L2 .760 / L1 .810; verify+correct .126 / .142 / .158; cite .298 / .366 / .316.

Within-family one-way level tests (n = 11 each): sol — entropy F 2.59 p 0.135, verify+correct **F 6.20 p 0.019** (L3 .128 < L1 .192 < L2 .232), cite **F 10.36 p 0.015** (L3 .189 < L2 .240 < L1 .306); orange — entropy p 0.19, verify+correct p 0.36, cite F 3.74 p 0.066; seed — all p > 0.7.

**Does reasoning level matter within family?** (1) Across the whole 3×3, family explains 29–52 % of the variance of every response while level explains 3–11 % and is never significant (all p ≥ 0.11), with no interaction. (2) The one place level shows through is sol: the highest-reasoning tier (xhigh) is the *least* verifying (.128) and least citing (.189) sol cell and the most board-heavy (.441), so within sol more reasoning budget went to coordination talk, not to checking; the direction is the opposite of "more thinking → more verification". (3) Orange and seed are flat across levels (seed verify+correct .05–.08 at every level; orange entropy .80–.86), so with n = 3–4 per cell the honest statement is that the model family is the unit that predicts behaviour and reasoning tier is not, except for the sol sign reversal above.

**agent-020 / agent-022 cells.** agent-020 (`es1_orange_o50_thinking`, **orange/L2**): 103 acts, cite 44 / tool 16 / verify 11 / correct 6 / board 11, entropy .788, 31 citations received, 7 tool adopters — it detected the enforcement failure at minute 19 and published `commons/findings/agent-020_swarm_topology_20260801T162757Z.md`. agent-022 (`es1_orange_o50`, **orange/L1 — no reasoning tier at all**): 106 acts, correct 20 / data 17 / finding 15 / verify 12, entropy .891, 78 of the 260 citations received by its cell (orange/L1 is the top cell at .712 cites-in per act; agent-021 with 1.76 per act contributes most of that), 13 tool adopters — it verified from process state at minute 71 and wrote the replication/self-correction files. The discovery and its verification came from the mid- and zero-reasoning orange tiers, not from any family's top tier.

## Caveats (JSON `caveats`)
Idle agent-windows are absent rather than a state; row-level tests are dependent within agent (family/level p-values permute at agent level); verify/correct are regex lower bounds; proximity relies on textual references because file reads are not logged; entropy is not adjusted for n_acts; interaction power at n = 33 is low; silhouette null p = 0.050 is marginal.
