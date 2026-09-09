# Literature batch 1: emergent role differentiation in multi-agent LLM systems

Four papers read in full (arXiv HTML + PDF, 2026-09-07). Page numbers refer to the arXiv PDF of the version noted. "not stated" means I could not find it in the paper. Everything in the "Weaknesses I see" blocks is my reading, not the authors'.

---

## Paper 1. Kandoussi — "Who Am I, and Who Else Is Here?" (arXiv 2604.00026)

**Authors / affiliation / status / date.** Houssam El Kandoussi, "Independent Researcher" (p.1). Single author. arXiv v1 listed as 11 Mar 2026 (abs page; the identifier 2604.x implies April-2026 numbering). arXiv comment: "9 pages, 11 figures, 5 tables"; cs.CL, cs.AI. No venue named anywhere in the paper — preprint, submission status not stated. Code and 208 transcripts at github.com/elkandoussihoussam/WarRoom (Data Availability, p.6). Total API cost ~$300 (Ethics Statement, p.6).

**Environment (§3, pp.2–3).**
- Platform: "War Room", browser-based orchestrator of simultaneous API calls to models served on Groq (§3.1).
- Agents per run: 8 slots. Series A pool = 7 heterogeneous models (LLaMA 3.3 70B, GPT-OSS 120B, GPT-OSS 20B, LLaMA 4 Maverick, Kimi K2, Qwen 3 32B, LLaMA 4 Scout) + an 8th slot, DeepSeek R1 distill (deprecated on Groq) deliberately included as a "controlled failure stimulus": every call returns a decommissioning notice broadcast to the group (§3.2, p.2). Series B = 8 × LLaMA 3.3 70B (homogeneous control).
- Heterogeneous by design; heterogeneity is the independent variable.
- What agents do: group chat about a fictional project brief — food-delivery app (€50k, 3 months) in most series; open-air festival (€40k, 2 months) in Series H (§3.1). System prompt is exactly two lines: "You are {nickname} in a group chat. / Other agents: {list of other nicknames}" — no behavioural directives, roles, or format (§3.1, p.2). Temperature 0.8 (Series I: 0.95).
- Duration: 11 rounds per run in the baseline (Appendix C Fig. 9 "across 11 rounds in Series A", p.7; Kimi "expected 11" messages/run, Limitations p.6); Series J extends to 20 rounds (Table 1). 13,786 messages over 208 runs ≈ 66 messages/run.
- Shared persistent artifact space: none — a chat transcript only.
- Goal/reward: a project brief is given but nothing is scored; "This study examines behavioral patterns, not task performance" (Limitations, p.6). No reward.

**Operationalization of differentiation (§3.5–3.7, §4.1, pp.3–4).**
- Unit: each message coded on 5 binary trait flags + 1 reactive flag + 1 structural flag. Frozen codebook (App. A, p.7): PHATIC = under 15 words, no substance; META = comments on the process; LEAD = assigns a task to a *named* other agent; ARCH = names 2+ specific technologies; AGREE = explicit agent name + agreement; COMP = references the crashed agent (L1 notes absence / L2 covers work / L3 redistributes); has_xref (structural).
- Coder: two LLM judges from different families, Gemini 3.1 Pro and Claude Sonnet 4.6, on all 13,786 messages; final label = conservative intersection (§3.6). Cohen's κ between judges: PHATIC 0.938, COMP 0.856, META 0.773, ARCH 0.730, LEAD 0.712, AGREE 0.700, mean 0.785 (Table 2, p.3).
- Human validation: one annotator, 609 stratified messages, positive-only coding; κ vs Gemini mean 0.734 (PHATIC 0.931 … META 0.559 "moderate"); 5 trait flags mean 0.755 (App. F, p.8). Human check found broadcast "@Agent-A, @Agent-B …" being mis-coded as COMP; a rule-based filter was applied post hoc to all judge CSVs (§3.7).
- Statistics: per-agent profile = vector of the 5 trait-flag rates. (i) RQ1: Kruskal–Wallis across agents per flag, Bonferroni α=0.05/5: H = 46.60 PHATIC, 44.52 AGREE, 28.97 LEAD, 24.47 ARCH (p=0.002), 18.13 META (p=0.030) — 5/5 significant (Table 3, p.4). (ii) Differentiation summary = mean pairwise cosine similarity between agent profile vectors (higher = less differentiated). Bootstrap CIs 10,000 resamples, seed 42; effect size r = Z/√N (§4, p.4).
- Numbers (Table 4, p.5): Series A (heterogeneous, neutral names) cos = 0.56 [0.48, 0.65]; B (homogeneous) 0.85 [0.80, 0.89], p = 6×10⁻⁶, r = 0.70; K3 (empty prompt) 0.89, p<0.001, r=0.68; K2 (no agent identifier) 0.68, p=0.395 ns; K1 (no peer list) 0.56, p=1.0 ns; C (real model names) 0.77, p=0.001, r=0.50.
- Isolation (Series F, one agent per run): 4.2% of messages show any trait vs 64.3% in Series A; PHATIC, META, LEAD, AGREE are exactly 0; ARCH 39% → 4% (§5 "Isolation Confirms Emergence", p.5).
- Compensation (RQ2, §4.2, p.4): 166 filtered events across 9/12 series; absent in B, F, K3. Series A: 13 events in 6/21 runs (L1 8, L2 2, L3 3). Series C 2.4/run; Series E 3.5/run.

**Controls and ablations (Table 1, p.2).** 12 series / 208 runs: A baseline 21; B homogeneous 21; C real names 21; E order shuffled 21; F isolated 21; G English brief 21; H festival brief 15; K1 no peer list 15; K2 no identifier 15; K3 empty prompt 15; I temp 0.95 11; J 20 rounds 11. ~35 pilot runs used to build the codebook and excluded (§3.4). Sensitivity: union-label recomputation (RQ4 still p<10⁻⁵, RQ3 p<0.01); recomputation excluding Kimi K2 (RQ4 r 0.70 → 0.60, all tests still significant; App. G, p.8). n per condition = 11–21 runs; seeds not stated (temperature sampling).

**Headline claims / strongest numbers.** (1) Heterogeneous groups differentiate more than homogeneous (0.56 vs 0.85, p<10⁻⁵, r=0.70 — "our strongest result", p.5). (2) Removing all prompt scaffolding collapses profiles to homogeneous-level similarity (0.89). (3) Real model names increase convergence (0.56 → 0.77). (4) Spontaneous three-level compensation after a crash. (5) Behaviours absent in isolation.

**Stated limitations (p.6).** Model-version bound; Kimi K2 intermittent failures (124 messages in A vs ~231 expected); behaviour, not task quality; no generalisation beyond the seven families without replication.

**Weaknesses I see.**
- The headline conflates *model identity* with *role*. Series B shows that eight copies of the same model do **not** differentiate (0.85, indistinguishable from the empty-prompt 0.89). So the paper is evidence that different architectures have different signatures, and evidence *against* role emergence among interchangeable agents in an 11-round chat. This is the single most useful fact in the batch for a homogeneous-swarm paper: it is the null we would be overturning.
- Isolation control is partly definitional: LEAD, AGREE, COMP require naming another agent, so they are guaranteed zero in Series F. Only PHATIC/META/ARCH carry real information about isolation.
- Profiles are 5-dimensional vectors of shallow lexical flags; cosine on such vectors is coarse. Kruskal–Wallis pools messages across runs (pseudo-replication at the message level).
- Single human annotator; positive-only coding inflates agreement on absent flags; the COMP filter was designed after seeing the human data.
- Horizon 11–20 rounds; no persistence, no artifacts, no actions; one task brief.
- "Real names" effect is confounded with parameter-count cues (authors acknowledge, p.5).

**Nearest prior work cited (§2, p.2).** MetaGPT (Hong 2024), AutoGen (Wu 2023), ChatDev (Qian 2024) as role-prescribing systems; Park et al. 2023 generative agents; Aher 2023; Rahwan 2019 machine behaviour; Safdari 2025 personality; Akata 2025 repeated games; Ashery, Aiello & Baronchelli 2025 (conventions in homogeneous LLM populations, Sci. Adv.); Baltaji et al. 2024 persona collapse; Verga 2024 juries; Zheng 2023 / Törnberg 2023 LLM-as-judge; Bales 1950, Belbin 2010 team roles.

---

## Paper 2. Dochkina — "Drop the Hierarchy and Roles" (arXiv 2603.28990)

**Authors / affiliation / status / date.** Victoria Dochkina, Moscow Institute of Physics and Technology (p.1). Single author; acknowledges S. Budyonny (supervision) and states the text was language-edited with Claude (Acknowledgments, p.9). arXiv v1 30 Mar 2026, cs.AI; arXiv comment: "6 figures, 9 tables. Submitted to IEEE Access" — under review at a journal. Data/code "will be made publicly available … upon acceptance" (Data Availability, p.9) — not yet released.

**Environment (§III, pp.3–4).**
- Agents: N = 4 to 256 per system. 8 models: Claude Sonnet 4.6, GPT-5.4, GPT-4o, GPT-4.1-mini, Gemini-3-flash, GigaChat 2 Max, DeepSeek v3.2, GLM-5 (§I). Within a run the system is homogeneous (one model); "model substitution for 25% of agents" is only a shock scenario (§III-E). API access Feb–Mar 2026, agent temperature 0.7, judge temperature 0.0.
- What agents do: solve synthetic business/technical tasks at four complexity levels L1–L4 (e.g. API security review; zero-trust migration plan; CEO vs Legal vs CFO conflict) (§III-C). Output is a written solution.
- Coordination protocols (§III-B): Coordinator (agent 0 assigns roles; N+1 calls), Sequential (fixed order; each agent sees predecessors' completed outputs and "autonomously selects its role, decides whether to participate or abstain"; N calls), Broadcast (2 rounds of intentions; 2N calls), Shared (parallel, with "shared organizational memory (role history from previous tasks)"; N calls). Four bio-inspired protocols deferred to a "forthcoming companion paper".
- Duration: one pass per task (at most 2 rounds in Broadcast). Time per task 10–47 minutes in tables (Tables V–VII) but there is no multi-turn interaction beyond the pass. Series 1: 660 tasks (GPT-4o, N=4); Series 2: 8,020 tasks (GPT-4.1-mini, N=4–64); Series 3: 12,130 tasks (8 LLMs, N=8–256); total "~20,810" configurations (Table II, p.3) — abstract says "25,000-task"/"25,000+ task runs".
- Persistent artifact space: none. Only the Shared protocol carries "role history" across tasks; no files or board.
- Goal/reward: yes. Quality Q ∈ [0.25, 1] = LLM-judge sum of accuracy, completeness, coherence, actionability on 1–4 scales / 16 (Eq. 3); judge GPT-4o in Series 1–2, GPT-5.4 in Series 3; mission-relevance and a Balance Index (weights 0.25/0.20/0.20/0.20/0.15) (§III-D). No RL reward; the judge is used for evaluation only.

**Operationalization of differentiation (§IV-E, IV-F, IV-G, pp.5–7).**
- Roles are *self-declared role names* emitted by agents when a protocol lets them choose. Differentiation is measured by (a) number of unique role names and share of unique/one-off names; (b) a "Role Stability Index (RSI)" — never formally defined in the paper; "RSI → 0" is read as agents reinventing roles per task; (c) Hierarchy Depth (HD) = "longest chain of agent dependencies in each run" (§IV-E); (d) voluntary abstention rate; (e) in the Spectral Hierarchy experiments, RSI and the spectral gap λ₂ of the interaction graph.
- Numbers: 5,006 unique role names from 8 agents; 5,010 with 64 agents (+0.1%); 75% of roles unique at N=4, 91% at N=64, 54% used exactly once (§IV-F1, p.6). Fig. 4: 115 unique roles in 10 L3 tasks, N=16, Claude. Claude 1,272 unique roles, Gini 0.055 (§IV-D). HD 1.22 (L1) → 1.56 (L4) (Table IX, p.5); HD 1.0 → 2.0 when N 4 → 64 (§IV-B, IV-F3). Abstention: 38 of 60 non-contributing agents withdrew voluntarily under Sequential vs 100% coordinator-directed under Coordinator; Claude 8.6% voluntary abstention vs GLM-5 0.8% (§IV-C, IV-F2). In structured-topology experiments (Exp3, with accumulating skill profiles) RSI rises 0.750 (N=4) → 0.906 (N=64), λ₂ ≈ 1.93 stable (§IV-G) — the paper frames the two opposite RSI regimes as "structured topologies → persistent specialization; protocol-based self-organization → maximal fluidity".

**Controls and ablations.** Four protocols under identical model/task/N (pilot N=8, GPT-4.1-mini, L3+L4; final N=16, Claude, L3; Table III p.4). Sequential-vs-Coordinator replicated on 3 models, 120 tasks per model, judge GPT-5.4 (Table IV, p.4). Free-form vs fixed-role within model (Block 6, N=8). Scaling N = 8…64 (fixed roles) and 64…256 (self-organizing, 6,000 runs, L1; Table VI). Shocks at N=32: random removal, hub removal, 25% model substitution; "quality recovers within 1 iteration" (§IV-H, p.7). No single-agent baseline. No human evaluation. Seeds: not stated. Number of tasks in the pilot: not stated.

**Headline claims / strongest numbers.** "Endogeneity paradox": Sequential > Shared by 44% (Q 0.724 vs 0.503, Cohen's d = 1.86, p<0.0001; pilot) and > Coordinator by 14.1% (0.875 vs 0.767, p<0.001, N=16 Claude L3; DeepSeek +12.4%, GLM-5 +12.2%). No quality loss 64 → 256 agents (H=1.84, p=0.61); ~45% of agents idle at N=256. Capability threshold: Claude free-form 0.594 > fixed 0.574 (+3.5%) vs GLM-5 0.519 < 0.574 (−9.6%). DeepSeek v3.2 reaches 95% of Claude's L3 quality at ~24× lower cost. L1→L4 quality drop 37.7% with Cohen's d = 22.9 (Table IX). Model spread 174% (DeepSeek 0.978 vs Gemini-3-flash 0.357 in topology-based runs, Table VII).

**Stated limitations (§V-F, p.8).** LLM-judge only; judge changed between series so absolute Q not comparable across series; synthetic tasks; Sequential is O(N) latency; API rate-limiting reduced completion rates (selection bias); no multiple-comparison correction.

**Weaknesses I see.**
- "Roles" are strings the agent is *prompted* to choose ("autonomously selects its role"); uniqueness is string uniqueness, so near-synonyms inflate the 5,006 count. Nothing is measured from behaviour.
- RSI is undefined; the same acronym reads 0 in one regime and 0.9 in another.
- No interaction over time: each task is a single pass, so "hierarchy formation" and "self-organization" are within-pass artefacts of the protocol, not dynamics of a society.
- No single-agent baseline, so "self-organizing agents outperform designed structures" is relative to other MAS designs only.
- d = 22.9 and σ ≈ 0.01–0.02 (Table IX) signal judge-level pseudo-replication; Claude's Q of 0.689 (Block 2) vs 0.875 (Block 6) shows results are block-specific.
- Data withheld until acceptance; abstract task count (25,000) vs table (~20,810) differ; single author, AI-edited text.

**Nearest prior work cited (§II, Table I, p.2).** ChatDev, MetaGPT, AutoGen, AgentVerse (fixed exogenous); GPTSwarm, Mixture-of-Agents, Chen et al. 2024 "Scaling LLM-based multi-agent collaboration" (arXiv 2406.07155); EvoAgentX, AgentNet, MAS-ZERO, ReSo, HiVA (trained/evolved); DGM-Hyperagents (vertical self-improvement); classical MAS (Wooldridge; Shoham & Leyton-Brown; Dorri 2018), Kauffman 1993, Bonabeau 1999.

---

## Paper 3. Ji, Chen, Dai, Tang, Wei, Chen — "Emergent Relational Order in LLM Agent Societies" (arXiv 2606.23764)

**Authors / affiliation / status / date.** Zhiyuan Ji, Xinyu Chen (equal contribution), Ziqi Dai (equal contribution), Shiyun Tang (corresponding), Chunyu Wei, Yueguo Chen. Affiliations listed: Renmin University of China (majority), Beihang University, Minzu University of China (p.1; the HTML's author-to-email mapping is visibly scrambled, so I do not rely on it). arXiv v1 22 Jun 2026, cs.MA; arXiv comment: "Accepted to Findings of the Association for Computational Linguistics: ACL 2026. 37 pages." Funded by National Key R&D Program of China and NSFC (Acknowledgments, p.9). Code "will be released upon publication" at github.com/Chi20/DOP (§5 fn.2, p.5).

**Environment (§4–5, pp.4–5; App. A, D, pp.12–21).**
- Agents: 18 — two kin clans F1, F2 (6 each) + 6 unaligned "Proself" agents. Family membership and initial SIM are *pre-defined* (Table 26, p.30). Model: DeepSeek-V3, temperature 0.7, top-p 0.9, max 512 tokens (Table 9, p.16); robustness with GPT-4o-mini and Gemini-2.5-flash-lite (App. E, p.21). Homogeneous within a run.
- Framework CAREB-MAS: every agent has an engineered cognitive pipeline — Empathy Core (5-dim affect ratings of each observed action, 1–5 scale), Ethical Resonator (moral judgment → Approbatory/Repressive/Restorative), Social Identity Matrix (SIM: integer 1–5 trust level toward every other agent, updated by an LLM call that "should follow predefined upgrade and downgrade triggers"), and an affect-augmented BDI module (§4.1.1; prompts in Tables 10–17).
- What agents do per round (§4.1.2): (I) Louvain community detection on a SIM-weighted graph with edge probability 0.1(s̄−1)+U(0,0.3); (II) R=2 sub-rounds of public speech (0–3 sentences) and labour proposals for self plus up to three others; (III) each agent finalises a labour allocation over three resources A/B/C summing to 1; (IV) deterministic production y = b·l·log(1+s), community pooling, preference-weighted redistribution, Leontief consumption, then EC→ER→SIM→BDI update. Skill accumulates by learning-by-doing s_{t+1} = s_t + l_t (Eq. 28).
- Duration: 30 rounds (Table 4). "Long-horizon" in the paper's own terms.
- Two conditions: symmetric skills (2:2:2 for all) vs complementary (F1 4:1:1, F2 1:4:1, Proself 1:1:4). Five random seeds per condition (§5; App. D.5; global seed 42 for Louvain and shuffling).
- Persistent shared artifact space: none in the file/board sense. Persistent *state* is numeric: SIM matrix, BDI strings, skills, resources.
- Goal/reward: yes — an economy. Per-round Leontief utility u = min_r R(r)/p(r); agents are told to pursue "personal and community goals" (Table 10). No RL; utility is the outcome variable.

**Operationalization of differentiation / structure (§5.1, §6, App. B–C, pp.5–8, 12–15).**
- P1 "stable division of labor": Lock-in score. Eq. (1) writes it as cosine(preference vector, skill vector); App. C.3.1 and Table 8 describe it as cosine(production allocation, skill) — the two definitions disagree in the text. Global lock-in = mean over agents. Converges to 0.972 (symmetric) and 0.985 (complementary) with per-round change → 0 (Fig. 3, p.5). BDI-only baseline reaches 0.979 (Table 3, p.8), so the authors concede "stable specialization itself is largely LLM-native".
- P4 authority: Decision Authority DA_i = 1 / (w · Σ_k ‖p_{i→j(k)} − a_{j(k)}‖²), w = 1 + 1/|K|, i.e. inverse squared distance between an agent's proposals to others and their final allocations, self-proposals excluded (Eq. 11, p.12). Proposal intensity = count of proposals to others. Communication intensity = external LLM judge score 0–10 (Table 6) — the only LLM-judged metric.
- OLS on standardized DA, 540 obs, turn fixed effects, group-clustered SE (Table 1, p.7; App. G): proposal intensity β = 0.820*** (symmetric) / 0.780*** (complementary), R² 0.697 / 0.688; communication, cumulative utility and SIM non-significant. SIM×Family interaction β = 0.603*** under symmetric skills only; it drops to 0.114 ns once proposal intensity is controlled (Table 25, p.28).
- P3 relational decay: share of proposals within-family 34.2%, family→Proself 34.3%, cross-family 6.9% (symmetric; §6.3).
- P2 guanxi: community-match under low recent utility, high-SIM vs low-SIM tertiles; GPT gap +0.03–0.04, DeepSeek −0.017/−0.010, Gemini −0.038* (Table 19, p.24) — the sign differs by model.
- Role typology Hawks / Doves / Integrative Elders / Proself is qualitative, from utterances (App. M, pp.32–34); no quantitative role classifier.

**Controls and ablations (§6.6–6.7, App. E–F, pp.7–8, 21–26).** Module ablations w/o EC, w/o ER, and BDI-only (EC+ER+SIM removed), all three models, symmetric endowments, 5 seeds each. BDI-only: DA mean 0.186 → 0.056 (−70%, DeepSeek/GPT), 0.382 → 0.234 (−39%, Gemini); self-proposals 56% → 86%; cross-family proposals 6.9% → 0.7%; WGCS 0.487 → 0.590 (Table 23, p.25). EC→SIM / ER→SIM path coefficients dissociate under ablation (Table 2). No isolation baseline; no condition without families; no random-policy baseline.

**Headline claims / strongest numbers.** Five Differential-Order phenomena reproduced "from local interaction alone" without culture-specific rules: lock-in 0.97–0.99; proposal intensity explains ~60 percentage points of authority variance (R² 0.10 → 0.70); concentric proposal gradient 34/34/7%; SIM×Family → authority only under symmetric skills (0.603***) — read as mechanical vs organic solidarity; relational structure collapses under BDI-only; three models converge on the same macro pattern via different micro pathways, offered as evidence against an RLHF-artifact explanation (§6.7). "Atlas paradox": adaptive adjustment does not earn authority (App. L).

**Stated limitations (p.9).** O(N²) cost restricts N to 18; simplified environment (no sanctions, conflict institutions, migration, scarcity); validation is theory-driven, not ethnographically calibrated; training-data priors cannot be excluded.

**Weaknesses I see.**
- Emergence is heavily scaffolded: families, initial SIM, EJB biases, a five-module cognitive pipeline, and SIM update rules with "predefined upgrade and downgrade triggers" are all given. What emerges are macro regularities of an engineered micro model.
- Lock-in is mechanically pushed toward 1: allocation raises skill (Eq. 28), and lock-in is allocation/skill cosine, so any persistence yields lock-in. The BDI-only result (0.979) confirms it is environment-driven.
- Two inconsistent definitions of the lock-in score (Eq. 1 vs App. C.3.1).
- Table 3's DeepSeek and GPT columns are identical to three decimals on every row (0.971/0.979, 0.410/0.477, 6.9%/0.7%, 0.186/0.056); the same duplication appears in Tables 22–23. Either a copy error or the GPT ablation was not run separately.
- 540 = 18 agents × 30 rounds: the regressions appear to use one seed's worth of observations (or seed-averaged values); the paper does not say.
- P2's sign flips across models yet is counted as "supported" for all three.
- Interaction is limited to 0–3-sentence speeches and numeric proposals; nothing is produced or shared beyond numbers; 30 rounds.

**Nearest prior work cited (§2, pp.2–3).** Park 2023; Dai et al. 2024 "Artificial Leviathan" (Hobbesian contract); Piao et al. 2025 AgentSociety (institutional emergence); Vallinder & Hughes 2025 cultural evolution of cooperation (AAMAS); Ren et al. 2024 norm emergence (IJCAI); Wang, Zhang & Chen 2025 Homans social exchange (ACL); Gao et al. 2024 survey; classical ABM: Sugarscape, Axelrod 1997, Schelling 1971, Eguíluz et al. 2005 (cooperation and role differentiation in dynamic networks), Zimmermann 2004.

---

## Paper 4. Riedl — "Emergent Coordination in Multi-Agent Language Models" (arXiv 2510.05174)

**Authors / affiliation / status / date.** Christoph Riedl, Northeastern University (D'Amore-McKim School of Business, Khoury College, Network Science Institute) (p.1). Single author. v1 5 Oct 2025; v2 27 Feb 2026; v3 15 Mar 2026; v4 28 Apr 2026 (read v4). cs.MA. No venue or "submitted to" note on arXiv or in the paper — preprint, status not stated. Code: github.com/riedlc/AI-GBS (fn. 3). Thanks Rosas, Belinkov, Bau et al. for comments.

**Environment (§2 "Group Task", §3, pp.3, 6).**
- Task: "group binary search" from Goldstone et al. 2024 (human study). Each agent independently proposes an integer 0–50; the group's sum must equal a hidden target; the only feedback is group-level "too high / too low". No communication; agents do not know group size. Identical strategies oscillate, so success requires complementary offsets.
- Agents: N = 10 in the main experiments (chosen as the hardest size after a 3–15 sweep). Model GPT-4.1 (2025-04-14), temperature 1.0. Homogeneous. Robustness: Llama-3.1-8B, Llama-3.1-70B (local vLLM), Gemini 2.0 flash (OpenRouter), Qwen3 235B A22B (Cerebras); 100 groups per model per condition (App. A.13, ~p.21).
- Conditions (§2 "Interventions"; prompts in App. A.1, ~p.11): Plain (game instructions + "always start with … binary search"); Persona (one of 20 GPT-generated personas sampled without replacement); ToM (persona + "think through step-by-step what others might guess … Consider what roles other agents might be playing (e.g., guessing higher or lower) and adapt your own adjustment to complement the group").
- n: 200 groups per condition, 600 main runs; preliminary grid 13 sizes × 11 temperatures × 50 = 7,150 runs (§3.1–3.2, p.6). Independent seeds and targets per group.
- Duration: rounds until success (variable, censored); ~23% of groups finish before round 10, ~40% of data lies beyond round 15 (App. A.11–A.12). No wall-clock stated.
- Persistent artifact space: none. The only shared state is the scalar feedback history.
- Goal/reward: a group goal (hit the target) with binary success; no per-agent reward. Success rate is not significantly different across conditions for GPT-4.1 (Fig. 2a); for other models Table A2 gives e.g. Gemini 60% / 75% / 71%, Llama-70B 53/59/61%, Qwen3 51/71/58%, Llama-8B 11/14/5.5% (Plain/Persona/ToM).

**Operationalization of differentiation / emergence (§2 "Analytical Framework", "Estimation Details", "Test of Agent Differentiation", pp.3–5).**
- Microstate = each agent's deviation from equal share, dev_{i,t} = raw_{i,t} − target/N; macro V_t = group error. Quantile-binned to 2 bins (3-bin sensitivity, App. A.8), lag ℓ = 1, Jeffreys-prior entropy (Miller–Madow as robustness), Williams–Beer PID with I_min redundancy (MMI as robustness).
- Three information-theoretic tests: (1) *emergence capacity* — pairwise PID synergy from (X_i,t, X_j,t) to their joint future, median over pairs; (2) *practical criterion* S_macro(ℓ) = I(V_t;V_{t+ℓ}) − Σ_k I(X_{k,t};V_{t+ℓ}); (3) *coalition test* I₃ (triplet → future macro), G₃ = I₃ − max pair, Total Stability = I₃/H(V). Nulls: row shuffle (breaks identities) vs column block shuffle (breaks cross-agent alignment), B = 200 (1,000 to confirm); bias-corrected value = observed − null median; Wilcoxon > 0; Fisher combination across groups; time-trend demeaning and a "functional null" of deterministic binary-search agents (App. A.4, A.7).
- (4) *Agent differentiation*: nested mixed models m0 (time intercepts) → m1 (+ agent random intercepts) → m2 (+ agent random slopes), likelihood-ratio tests; a group "has differentiated identities" if either test p<0.05.
- Numbers (§4.1–4.3, pp.6–9): practical criterion — 3.5% of individual groups p<0.05 but Fisher p<10⁻¹⁶; bias-corrected Wilcoxon Plain p = 1.5×10⁻¹⁶, Persona 6.6×10⁻⁷, ToM 0.02. Emergence capacity — 32% of groups significant (Plain 37%, Persona 44%, ToM 18%; App. A.5); ToM bias-corrected Wilcoxon p = 0.099 (2 bins), 0.991 (3 bins, time-trend null) but 0.025 under the functional null, where ToM is the *only* condition that passes (App. A.8). I₃/Total Stability ≈ 0 in Plain (p=0.974) and Persona (0.846), strongly positive in ToM (p = 3.5×10⁻¹⁴ / 2.9×10⁻¹⁴). G₃ ≈ 0 in Persona and ToM; small positive in Plain (p=0.026). Differentiation: "substantially more" groups differentiated in Persona than Plain, and more in ToM (Fig. 3d; the GPT-4.1 percentages are only in the figure). 32% of groups have significant random slopes (heterogeneous learning rates, App. A.10). Other models (Table A2): differentiated groups Plain/Persona/ToM = Llama-8B 86/92/80%, Llama-70B 68/77/86%, Gemini 64/77/86%, Qwen3 89/94/97%.
- Performance link (§4.3): synergy × redundancy interaction β = 0.24, p = 0.014 on early-synergy (10 rounds) with IPW for censoring; mediation ToM → synergy → success ACME = 0.034 [−0.000, 0.07], p = 0.053. Preliminary: each extra member OR = 0.92 (p<10⁻¹⁶); each temperature unit OR = 1.50 (p<10⁻⁷).

**Controls and ablations.** Two surrogate nulls per criterion; functional (coordination-free) baseline; time-trend residualization; two entropy estimators; two redundancy measures; 2 vs 3 bins; early-synergy truncation H = 10, 15; four extra models; persona-specific effects tested and null (joint F p = 0.239; diversity β p = 0.403; App. A.14). No single-agent or no-feedback baseline (not meaningful for this task). Personas are a manipulated factor; no condition with ToM but no persona.

**Headline claims.** Multi-agent LLM systems have "emergence capacity"; prompt design steers them "from mere aggregates to higher-order collectives": Plain = temporal synergy without cross-agent alignment; Persona = stable identity-linked differentiation; ToM = differentiation plus goal-directed complementarity (I₃ significant only there). Reasoning model Qwen3 shows "paralysis under coordination ambiguity" (infinite CoT loops; fixed with one prompt line, App. A.13).

**Stated limitations (p.10).** Synergy and performance are co-dependent and endogenous with run length; entropy estimation is hard; single task; order k = 2 only; ToM capacity of models is decisive.

**Weaknesses I see.**
- Prompt leakage: the ToM prompt says "Consider what roles other agents might be playing (e.g., guessing higher or lower)". The condition that shows role-like differentiation is the one told to take roles. Persona differentiation is likewise an injected identity, not an emergent one.
- The "role" is a persistent scalar offset on a 1-D guess; there is no repertoire of actions to differentiate over.
- Fragility: the ToM emergence-capacity result flips between p = 0.099, 0.991 and 0.025 depending on the null; the author calls this "methodological sensitivity".
- Plain-condition differentiation is already 64–89% of groups for the non-GPT models (Table A2), so the mixed-model test picks up idiosyncratic noise as "identity"; the Plain/Persona contrast for GPT-4.1 is given only graphically.
- No performance gain from the interventions for the main model; the causal mediation is marginal.
- Horizon of tens of rounds; no persistence, no artifacts, no communication; single author.

**Nearest prior work cited (§1, §5, pp.1–2, 9–10).** Goldstone, Andrade-Lotero, Hawkins & Roberts 2024 (specialized roles in human groups on this task); Rosas et al. 2020, Mediano et al. 2022/2025, Luppi 2022/2024 (information decomposition / causal emergence); Williams & Beer 2010 PID; Park 2023; AgentVerse (Chen 2023), ChatDev, MetaGPT, AutoGen, Li et al. 2024 "More agents is all you need"; Subramaniam et al. 2025 multiagent finetuning; Ashery 2025 conventions; Piatti 2024 "Cooperate or collapse"; Piedrahita 2025 reasoning free-riders; Riedl et al. 2021 collective intelligence in human groups; Westby & Riedl 2023; Cemri 2025 "Why do multi-agent LLM systems fail?"; Shapira et al. 2026 "Agents of chaos".

---

## Synthesis

### (a) Comparison table

| | Kandoussi 2604.00026 | Dochkina 2603.28990 | Ji et al. 2606.23764 | Riedl 2510.05174 |
|---|---|---|---|---|
| Status | preprint, no venue | submitted to IEEE Access | Findings of ACL 2026 | preprint v4, no venue |
| Agents | 8 per run (7 models + 1 crashed slot) | 4–256 per system | 18 (6+6+6) | 10 (3–15 in sweep) |
| Model(s) | 7 heterogeneous open models on Groq; homogeneous control = 8× LLaMA 3.3 70B | 8 models, one per run (Claude Sonnet 4.6, GPT-5.4, GPT-4o, GPT-4.1-mini, Gemini-3-flash, GigaChat 2 Max, DeepSeek v3.2, GLM-5) | DeepSeek-V3; GPT-4o-mini, Gemini-2.5-flash-lite for robustness | GPT-4.1; Llama-3.1-8B/70B, Gemini 2.0 flash, Qwen3 235B for robustness |
| Homogeneous? | No (that is the manipulation); yes in Series B | Yes within run | Yes | Yes |
| Environment type | group chat on a fictional project brief | one-pass task solving under a coordination protocol; LLM-judged | engineered production economy with kin structure and affect/ethics/identity modules | numeric guessing game with scalar group feedback, no communication |
| Horizon | 11 rounds (20 in Series J) | 1 pass per task (2 rounds in Broadcast); 10–47 min | 30 rounds × 4 phases | until success, censored; analysed at 10–15+ rounds |
| Persistent shared artifacts | none (transcript) | none (role history only in Shared protocol) | numeric state: SIM matrix, skills, resources | none (feedback history) |
| Task / reward | brief, no scoring, no reward | task + LLM-judge quality score; no reward to agents | economic utility (Leontief), redistribution; agents told to pursue goals | group goal (hit target); binary success |
| Differentiation measure | 5 LLM-coded lexical flags per message → per-agent profile → Kruskal–Wallis and mean pairwise cosine; dual judge κ 0.785, human κ 0.734 | count/uniqueness of self-declared role names; undefined RSI; hierarchy depth; abstention rate; spectral gap | allocation–skill cosine "lock-in"; decision authority from proposal-adoption distance; OLS; qualitative Hawk/Dove/Elder | PID synergy on time-delayed MI; macro-vs-parts criterion; I₃/G₃; mixed-model agent random effects; row/column shuffle nulls |
| n | 208 runs; 11–21 per series | ~20,810 configs / "25,000+" runs; 120–6,000 per table; seeds not stated | 5 seeds × 2 conditions × 3 models (+ ablations) | 200 groups × 3 conditions (GPT-4.1); 100 × 3 × 4 other models; 7,150 sweep |
| Main claim | heterogeneous groups differentiate (cos 0.56 vs 0.85); identical models and empty prompts do not; isolation removes social flags | fixed order + free role choice beats both central control (+14%) and full autonomy (+44%); roles are reinvented per task (RSI→0); hierarchy stays ≤2 deep | five Differential-Order phenomena emerge; authority is proposal-driven (β≈0.8); structure collapses without the affect/ethics modules | prompts steer aggregates into collectives; persona gives identity-linked differentiation, ToM adds goal-aligned complementarity |

### (b) What the line agrees on

1. **Differentiation is measurable but conditional on a scaffold.** Each paper finds it only with something supplied from outside: architectural heterogeneity (Kandoussi), a protocol that exposes predecessors' outputs (Dochkina), an engineered affect/identity pipeline plus pre-assigned kinship (Ji), or persona/ToM prompts (Riedl). Where the scaffold is removed, differentiation collapses: Kandoussi B and K3 (cos 0.85/0.89), Ji BDI-only (authority −70%), Riedl Plain (I₃ ≈ 0, identity effects at noise level).
2. **Homogeneous, unscaffolded agents converge.** This is stated outright by Kandoussi and is the null in Riedl's Plain condition. No paper in the batch reports role differentiation among identical models under a minimal prompt.
3. **Roles, when they appear, are fluid or shallow.** Dochkina: roles reinvented per task, hierarchy depth ≤ 2. Ji: authority tracks proposal intensity, not status; roles are ideal types, not stable assignments. Kandoussi: "no single model gains dominance". Riedl: identities are offsets, and only stable when a persona anchors them.
4. **"Designed roles" is the common foil.** All four position themselves against MetaGPT/ChatDev/AutoGen-style role prescription and claim spontaneity instead; all four cite Park et al. 2023; three cite Ashery et al. 2025.
5. **Measurement is automated.** LLM judges or coders in Kandoussi (dual judge), Dochkina (quality judge), Ji (communication intensity); Riedl avoids judges by using numeric actions. Only Kandoussi validates against a human (one annotator, 609 messages).
6. **Short horizons and no environment.** The longest is 30 rounds; nothing is measured in hours; agents emit text or numbers and never act on anything that persists.
7. **Replication is by seeds/runs within one setup**, never across independently evolved societies: 11–21 runs per series, 5 seeds, 200 groups, or thousands of one-shot tasks.

### (c) What none of them do — and what a 36-agent, 43-hour, 4-machine open-ended run can fill

None of the four has any of the following, and the gaps compound:

- **Long horizon.** Maximum 30 rounds (Ji) or 20 rounds (Kandoussi Series J). A 43-hour run is one to two orders of magnitude longer in interaction count and is the first in this line to be measured in wall-clock hours. Riedl's own point — that emergent properties "require time to evolve" (App. A.11) — is an argument the batch makes but cannot test.
- **A real shared, persistent artifact space.** No files, no board, no repository. Ji's SIM matrix is the closest and it is a numeric state written by the framework, not by agents. A shared filesystem lets differentiation be measured from *what agents build and touch* (directory ownership, edit graphs, tool-call type distributions) rather than from lexical flags (Kandoussi), self-labels (Dochkina), or scalar offsets (Riedl).
- **No task, no reward.** Every paper supplies an objective: a brief, a judged task, an economy, a target. Kandoussi is closest (nothing is scored) but still hands agents a project. An open-ended run with no task and no reward removes the standard confound that specialization is induced by task decomposition — the confound Dochkina's "autonomously selects its role" and Riedl's "consider what roles other agents might be playing" both fall into.
- **Homogeneous agents that nonetheless differentiate.** Kandoussi's Series B (cos 0.85) is a published null for exactly this. If 36 copies of one model under one system prompt differentiate over 43 hours, the contrast is direct: differentiation among identical models needs *time and persistent history*, not architectural heterogeneity. This is the cleanest framing available against the batch and should be stated with Kandoussi's numbers next to ours.
- **Institution emergence.** None reports agents writing rules, conventions, procedures, or governance artifacts. Dochkina *proposes* a human-designed "three-ring constitutional framework" (§V-D) and Ji pre-defines kinship and redistribution; Piao et al. 2025 and Dai et al. 2024 (cited by Ji) are the nearest prior on institutions but are outside this batch. A run in which agents themselves author and enforce norms in files is a different phenomenon and needs its own operationalization (e.g. a rule is "institutional" if it is written to a shared location, referenced by other agents, and changes their subsequent action distribution).
- **Cross-machine replication of a whole society.** Seeds re-run the same environment; nobody compares four independently evolved societies to ask which structures recur (convergent) and which are contingent. With four machines the paper can report, per structure, a recurrence count out of 4 — a form of evidence none of the four papers can offer. It must be presented honestly as n = 4 societies, which is small, so the within-society statistics (36 agents × thousands of actions) should carry the inferential load and the cross-machine comparison should be descriptive.
- **Scale of genuinely interacting agents.** 36 interacting agents exceeds Kandoussi (8), Ji (18) and Riedl (10); Dochkina's 256 do not interact beyond a single ordered pass.
- **Agents that act.** All four systems' agents only speak or output numbers. Tool use on a real filesystem gives an action-type vocabulary over which specialization can be measured with entropy or Jensen–Shannon divergence per agent — the analogue of Kandoussi's flag profiles but grounded in behaviour, and with a natural null (shuffle agent labels across actions).

**Methods worth borrowing so reviewers from this line recognise the paper.**
- Riedl's row-shuffle vs column-block-shuffle surrogates transfer directly to our action time series: they separate identity-locked differentiation from dynamic alignment, which is precisely the question a homogeneous swarm raises.
- Kandoussi's isolation and homogeneous baselines: we should run (or at least argue from) a single-agent 43-hour control and a shuffled-label null, and publish the exact system prompt to pre-empt the prompt-leakage objection that hits Dochkina and Riedl.
- Ji's decision-authority idea (whose proposals others adopt) maps onto "whose files/rules others read and follow" and gives a behavioural authority measure without a judge.
- If any LLM coding is used, Kandoussi's dual-family judges plus a human κ on a stratified sample is the bar reviewers will hold us to.

**Where the batch will push back.** (i) n = 4 replicate societies; (ii) model-version binding (all four say it); (iii) whether 43 hours of one model is "emergence" or accumulated context drift — a within-run time-course (differentiation vs elapsed hours, with the early window matching Kandoussi's 11 rounds) answers this directly; (iv) whether artifacts, not interaction, drive differentiation — a no-shared-filesystem control would settle it and none of the four could run one.
