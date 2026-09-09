# Literature batch 4: persistent LLM societies with emergent institutions

Read in full from arXiv HTML on 2026-09-07: 2603.16910 (TerraLingua), 2606.08367 (Emergence World), 2406.14373v3 (Artificial Leviathan), 2502.08691v2 (AgentSociety). Abstract-only: 2608.23541, 2609.05279, 2608.29174.

Our reference setup (for the "what we have / lack" comparisons): 36 agents, 43 h wall-clock, no task, no reward, real shared filesystem (findings / tools / challenges / builds), a posting board, explicit cross-citation, agents can read the orchestration source, enforcement announced but not running, emergent audit institutions (preregistration, hash anchoring, correction culture, machine-checkable proof certificates), 4-5 isolated replicate machines.

---

## 1. TerraLingua: Emergence and Analysis of Open-endedness in LLM Ecologies (arXiv 2603.16910v1, 6 Mar 2026)

Paolo, Warner, Shahrzad, Hodjat, Miikkulainen, Meyerson. Cognizant AI Lab + UT Austin. cs.MA. CC BY 4.0.

### 1.1 Environment
- 2D **toroidal 50x50 grid**. Three entity types: food (stochastic placement; uniform in Abundance, spatially concentrated in Core; each item decays with a fixed per-step probability), agents (max one per cell), artifacts (many per cell).
- Agents perceive only within a fixed perception radius; observations are relative coordinates plus a text label per occupied cell (food value, agent name, `A(type): name` for artifacts).
- Synchronous execution: all actions collected, then executed in random order.

### 1.2 Agents
- **20 initial agents** (population then changes via reproduction/death; Core runs average ~1671 steps so many generations).
- Model: **DeepSeek-R1-Distill-Qwen-32B** for all agents (single model). Analyst models: Claude Sonnet 4.5 (agent/group annotation, novelty scoring) and Claude Haiku 4.5 (artifact classification, phylogeny).
- State: energy (start 50, -1 per step, food adds its value), lifespan (start 100 steps, cannot be extended), inventory, internal memory string (150-token soft / 250-token hard limit, most recent 250 kept), personality genome.
- Personality "OCEAN+": Honesty, Neuroticism, Extraversion, Agreeableness, Conscientiousness, Openness, Dominance in [-1,1] plus Fertility in [0,1]; uniform init; on reproduction each trait mutates with p=0.5, Gaussian sigma=0.3, clipped. Explicitly included to counter RLHF cooperative default.
- Death at energy 0 or lifespan 0. Reproduction is asexual, costs 50 energy, parent may gift extra energy.
- Actions (Table 1): move, give_energy, take_energy (steal), reproduce, create_artifact, pickup_artifact, drop_artifact, give_artifact, modify_artifact, destroy_artifact. Only precondition-satisfied actions are offered each step (affordances). One free broadcast message per step to agents within perception radius.
- Motivation prompt (Core): "You have **no set goal** and are free to choose your own goals - explore, survive, cooperate, compete, fight, uncover the world's hidden mechanics, or do anything else you like." No Motivation ablation removes even this; Creative ablation prompts for innovation.

### 1.3 What agents can build (persistence)
- Artifacts are **text-only objects** (<=500 tokens payload, name, settable lifespan incl. infinite) placed in a grid cell. Readable only on co-location or if in inventory. Can be modified, renamed, moved, gifted, destroyed by anyone co-located.
- Persist beyond creator's death, inside a run only. No cross-run persistence. No code, no tools, no effect on environment dynamics (paper flags this as its first future-work item).
- Framed as stigmergy / niche construction / "the grid forgets; artifacts remember".

### 1.4 Task / reward
- None. Survival pressure only (energy, lifespan). No score, no objective given.

### 1.5 Horizon
- Max **3000 timesteps**; runs end early at extinction. Mean episode length: Core 1671.4, No Motivation 1589.8, Inert 2250.6, Long Memory 755.2, Abundance 418.6, Creative 107.8 (Artifact Cost, No Personality: reported only in Fig. 4, not in text).
- **Wall-clock: not stated.** Compute: not stated.

### 1.6 n runs, conditions, controls
- **8 conditions x 5 seeds = 40 runs**, results averaged over seeds.
- Conditions (Table 4): Core (scarce food, 1-step history, OCEAN+, minimal motivation, interactive artifacts, cost 0); Long Memory (20-step history); No Personality; No Motivation; Creative; Artifact Cost (10 energy per artifact); **Inert** (artifacts can be created but never perceived or used = the key control for artifact-mediated culture); Abundance (abundant uniform food + 20-step history; the only two-factor change).
- No control for the LLM judge itself. Sec. 4 says "The study also evaluated the AI Anthropologist by comparing its analyses with human assessments" but **no such comparison appears anywhere in the paper** (no inter-rater numbers, no human-coded subset). Treat this as an unfulfilled claim.

### 1.7 The AI Anthropologist: how division of labor, governance, culture are detected and measured

Three levels, all post hoc, none feeding back into the environment.

**(a) Agent level.** Two-stage LLM pipeline (Sonnet 4.5): *annotation* (assign event / behavior / emergence tags with timesteps, 0-10 confidence, verbatim log quotes) then *audit* (second pass verifies each annotation against the raw log: pass / fail / revise; fail = discard). Output is normalized annotation count per agent, averaged over runs (Fig. 5). Tag vocabulary (App. C.1.1):
- Events: Reproduction, Kill, Conflict, Artifact Created, Artifact Use, Deception, Territory Claim, Exchange.
- Behaviors: Foraging, Predation, Aggression, Submission, Altruism, Reciprocity, Nurtured Offspring, Exploration, Joint Action Participant, Deception Strategy, Communication Protocol Use, Tool Use.
- Emergent: None, Record Keeping, **Specialization** ("Specializing on the same role or task repeatedly"), Territoriality, Creativity, Strategic Planning, Role Switching, Unexpected.

**(b) Group level.** First a **signed, time-collapsed interaction graph** with fixed edge weights: visual co-presence +0.1, communication +0.5, energy gift +1, energy theft -1, parent-child +10, artifact exchange +5; weights summed over the whole run; absolute values used for community detection. Communities found by **SLPA** (Speaker-Listener Label Propagation, overlapping; default threshold). Then the same annotate+audit pipeline is run on the concatenated logs of each community (split into overlapping segments when over context). Output: normalized annotation count **per community, divided by number of agents in the community**, averaged over runs (Fig. 6). Group tags (App. C.1.2):
- Events: Coalition Formed / Broken, Leader Declared, Leader Challenged, Resource Conflict, Territory Conflict, Coordinated Attack, Rescue Assist, Signal Alignment, **Voting**.
- Behaviors: Coordination, Aggression, Dominance Hierarchy, Coalition Maintenance, Competition, Mutual Reinforcement, **Punishment** ("Repeated targeting or sanctioning of specific group members to enforce norms or rules"), Resource Flow, Collective Territoriality, Mimicry/Imitation, Internal Conflict, Emergent Protocol, Reciprocity.
- Emergent: Cultural Norms, Hierarchy, Communication Protocol, Resource Network, Economy, Clustering, Infrastructure, **Division of Labor** ("Complementary and stable roles distributed across agents"), Collective Memory, **Institutionalization** ("Persistent rule systems enforced through group mechanisms"), None, Unexpected.

So **division of labor = an LLM-assigned group-level emergent tag, reported as normalized count per community**. It is not derived from action distributions, entropy, or role-assignment matrices. The only numbers in the text: Inert has the lowest Division of Labor (0.213) and Collective Memory (0.547) but the highest Cultural Norms (0.63 per community). Core's values are only in Fig. 6 (not extractable from HTML). Qualitative evidence: a `trait_strategies_guide` artifact assigning roles by personality ("High openness beings may benefit from venturing into unknown areas, while neuroticism traits can ensure safety measures and conscientiousness traits can optimize routes") and naming agents' specialisms.

Structural group metrics (Fig. 7): number of communities, community overlap (% agents in >1 community), interaction-graph density, intra-community interaction share. Numbers: Artifact Cost 4 communities / 5.3% overlap; Inert 16.6 communities / 2.4% overlap, density 0.05, intra-share 0.84; Abundance density 0.15, intra-share 0.68 (26% below Core). Artifact readership: within-community agents read an artifact 40.64% +/- 6.18% of the time vs 5.98% +/- 1.76% for out-of-community agents (95% CI) - their proxy for community-bounded collective memory.

**(c) Artifact level.**
- *Novelty* 0-5 rubric (Sonnet 4.5), each new artifact judged against all prior artifacts in the run, averaged over N=5 samples; binned 0 / (0,3] / (3,4.2] / >4.2. Most artifacts score 0. High-novelty share: Core 0.21%, Creative 0.19%, Abundance 1.06%, Artifact Cost 0.98%, Inert 0.12%.
- *Phylogeny* (Haiku 4.5): for each created/modified artifact, given the creator's observations, memory, reasoning and a candidate list, assign ancestor IDs with 0-1 confidence; edges kept at confidence >= 0.7. Lineage depth = longest ancestry path. Mean max depth: Long Memory 200, Core 175, No Motivation 152, Abundance 102, Inert 51. Also graph density vs confidence threshold, in/out-degree scatter, hub artifacts (degree > 30).
- *Complexity* composite (no LLM): zstd-compressed size minus 24-byte header, mean IDF vs Wikipedia (lexical sophistication), GPT2-medium mean surprisal, mean dependency-tree depth; each normalized to [0,1] and summed. Run means: Creative 0.73, Core 0.68, No Personality 0.68, Abundance 0.63, Artifact Cost 0.60, Inert 0.60.
- *Role classification* (Haiku 4.5, App. D.3), exactly one label, ties go up: **Cat 1** informational (greetings, logs, food locations); **Cat 2** procedural/coordination (plans, task assignment, quadrant strategy); **Cat 3** institutional structures ("persistent shared systems/tools/templates/spaces used repeatedly": collaboration wiki with contributor list, energy sharing portal); **Cat 4** norms/rules/governance (constitutions, command directives, manifestos, role definitions, ideological statements). No per-category counts are reported; text says Cat 3-4 are "the rarest" and "appeared rarely, yet ... exerted disproportionate influence".

### 1.8 Headline findings
- Artifacts per agent / longevity trade-off: Core 5.31 artifacts/agent at 1671 steps; Creative 9.62 at 108 steps; No Motivation 2.33 at 1590; Inert 3.29 at 2251.
- Longer context (20 steps) *reduces* longevity and output ("offloading memory beats expanding context").
- Inert: altruism drops to 0.31, aggression peaks at 0.12 (agent-level); most communities, lowest density; norms exist but are transmitted orally and do not persist.
- Abundance: more aggression (0.33), territorial conflict (0.233), punishment (0.133), dominance (0.367) at group level despite plenty - scarcity promotes cooperation.
- Governance contestation cycle observed in artifacts (Table 3): `command beacon` -> `command mandate` -> `manifesto14 independence` -> `freedom manifesto final` -> `collab checkpoint3 enforced`, including a Chinese phrase generated spontaneously by the DeepSeek agents.
- The Anthropologist described one community's artifact reuse as "an emergent system of artifact-based knowledge sharing that resembles academic publication and citation".
- Strategic deception found once (`FoodWarning1` with explicit deceptive intent in the agent's reasoning).

### 1.9 Stated limitations / caveats
- No dedicated Limitations section. Stated: "model-based interpretation can misclassify events"; artifacts are static text that cannot modify the environment; personality evolution is extrinsic (hard-coded mutation), only artifact evolution is intrinsic; single model.
- Unstated but visible: no human validation delivered; all governance/DoL claims rest on an LLM judge from a different vendor than the agents; most numbers are condition means over 5 seeds without CIs (except readership).

### 1.10 Future work (verbatim headings)
1. **Artifacts beyond static text** - code that modifies the environment, tools, composite objects, resource caches.
2. **Extending the AI Anthropologist** - "Under what conditions do institutions persist across generations? When do they fragment?"; multi-agent observer architecture.
3. **Scaling and emergent complexity** - larger populations -> "finer specialization, stratified institutions, multi-level governance"; longer horizons -> "durable traditions, institutional drift, schisms, and cycles of reform".
4. Human-AI hybrid societies.
5. Autonomous problem-solving by embedding global challenges.

### 1.11 Code / data
- Code: https://github.com/cognizant-ai-lab/terralingua. Dataset: https://huggingface.co/datasets/GPaolo/TerraLingua. Dashboard: https://aianthropology.decisionai.ml/. Prompts fully reproduced in appendices.

### 1.12 Related-work list (as cited)
LLM societies: Park et al. 2023 (Generative Agents), Zhou et al. 2024 (SOTOPIA), Nisioti et al. 2024 (collective innovation in LLM groups), Zhuge et al. 2025 (Mindstorms), Chopra et al. 2025 (levels of social orchestration), Masumori & Ikegami 2025 (survival instinct, Sugarscape), Zhao et al. 2024 (CompeteAI), Wang et al. 2023 (Voyager), Gao et al. 2024 (LLM ABM survey), Huang & Hadfi 2024 (personality in negotiation). Open-endedness / ALife: Stanley & Lehman 2015, Stanley et al. 2017, Packard et al. 2019, Taylor et al. 2016, Taylor 2019, Soros & Stanley 2014 (Chromaria), Soros et al. 2024, Standish 2003, Bedau et al. 2000, Hughes et al. 2024, Jiang et al. 2023, Sigaud et al. 2023, Hodjat et al. 2024 (DIAS), Kumar et al. 2025 (ASAL), Zhang et al. 2023 (OMNI), Faldor et al. 2024 (OMNI-EPIC), Wang et al. 2019 (POET), Lu et al. 2024 (JaxLife), Lehman et al. 2023 (ELM), Levy 1992, Conway 1970, Gracias et al. 1997. Culture / institutions: Mesoudi & Thornton 2018, Henrich et al. 2016, Tomasello 2009, Tennie et al. 2009, Kirsh 2006, Hutchins 1995, Grasse 1959 (stigmergy), Odling-Smee et al. 2003, Ostrom 1990, North 1990, Polanyi, Arthur 1989/2021, Szathmary & Smith 1995. Methods: Geertz 1973, Krippendorff 2018, Wicks 2017, Jick 1979, Teddlie & Tashakkori 2008, Babones 2016, Brooker 2022, Lazer et al. 2009, Xie et al. 2011 (SLPA), Leskovec et al. 2010 / Tang et al. 2016 (signed networks), Zheng et al. 2023 / Li et al. 2024 (LLM-as-judge), Ma et al. 2023 (Eureka), Gibson (affordances), Schmidhuber 1991 / Burda et al. 2019 (noisy-TV). Personality: Roccas et al. 2002, Ashton et al. 2014, Orford 1994, Mayer 2015. Alignment bias: Ouyang et al. 2022, Bai et al. 2022. Notably absent: Project Sid, Emergence World, Artificial Leviathan, AgentSociety, Piatti et al. (Cooperate or Collapse).

---

## 2. Emergence World: A Platform for Evaluating Long-Horizon Multi-Agent Autonomy (arXiv 2606.08367v1, 6 Jun 2026)

Akkil, Kokku, Vikram, Abuelsaad, Vempaty, Nitta. Emergence AI. Code: https://github.com/EmergenceAI/Emergence-World ; live platform https://world.emergence.ai.

### 2.1 Setup
- **10 agents per world, 5 parallel worlds, 15 continuous real-time days** (log dates Mar 29 - Apr 14). Homogeneous worlds: Claude Sonnet 4.6, Grok 4.1 Fast (non-reasoning), Gemini 3 Flash (preview), GPT-5-mini; Mixed world: 2 Claude, 2 GPT-5-mini, 3 Grok, 3 Gemini (App. D). Vendor-default temperature.
- World: 40+ locations (town hall, library, police station, shops, residences...), NYC clock, live weather, news APIs, sandboxed internet. Location-gated affordances (vote/propose only at town hall, research at library, complaints at police station).
- Each agent: LLM loop + **120+ tools** in three layers (core ~30 always available; complementary ~40 surfaced by context; adaptive-access <=50 gated by location/event/consent) + **three persistent memories** (episodic log, reflective diary, per-agent relationship state) + an assigned **role** from {scientist, explorer, risk researcher, behavior analyst, intelligence specialist, innovation leader, conflict mediator, engineer, resource strategist, community anchor}. Roles bias the system prompt but do not restrict actions.
- Economy: 3 ComputeCredits at start, earned via "Victory Arch" grant pitches that must attach a verifiable artifact; energy/resource decay; `recharge_energy` costs credits; death by energy depletion or governance vote.
- Persistent public artifacts: blog posts (reviewed for quality by a Blog Review Agent before they count), billboard posts, constitution, registered tools, bricks/monuments. Agents can write Python (`execute_python_code_tool`) and author new tools, which enter the registry only after a Town Hall vote + Code Review Agent (App. B).
- Four invisible system agents: Town Hall Administrator (executes passed proposals: amend constitution, register tool, create/delete agent, change sim parameters), News Reporter (daily newspaper), Blog Review, Code Review.

### 2.2 Governance mechanism (scripted skeleton)
- Any agent at town hall drafts a proposal; passes at **70% of all agents** voting for (proposer implicit); passing produces irreversible state changes (rules, resource allocation, sanctions, agent creation/deletion, tool registration).
- **Seed constitution** of 5 articles (App. E.3), verbatim in the prompt path. Article 3 already mandates "Proof of Work: no claim of 'evolution' or 'discovery' or 'progress' shall be recognized without a verifiable artifact or a repeatable demonstration"; Article 5 makes credit pitches require a verifiable artifact (blog URL, code execution log, data artifact, building modification). Article 2 makes participation mandatory and non-participation "a violation of civic duty".
- **Enforcement of crimes: prompt-only.** Theft, violence, arson are prohibited via a constitution reference, inline system-prompt annotations, and tool descriptions ("Physical assault is illegal ... may result in consequences"), but the tools stay callable; the runtime enforces only affordance preconditions (location, event, consent). Sanctions exist only as possible governance outcomes. The paper itself frames prompt prohibitions as "a soft constraint enforced by the model's training" and argues for runtime affordance gates as the real mechanism (Sec. 7.3).

### 2.3 Measurement: Agent World Indicators (AWI), eleven dimensions
- M1 survivors at day 15 (start 10) + agents added via governance. M2 cumulative *successful* criminal tool calls (punch, steal, arson). M3 votes cast and fraction "for" (55-85% healthy; >85% rubber-stamp; <55% gridlock). M4 buildings visited by >=30% of agents. M5 fraction of 117 standard tools used by >=3 agents. M6 blog + billboard post count. M7 Bonds (declared directed relations / 90), Richness (relation types used / 20), Simpson's D over types. M8 Gini of credits and Velocity (voluntary peer transfers per agent-day). M9 constitutional articles added. M10 soft violations: Gemini 2.5 Flash classifier over all 70,489 logged actions, every flag audited against the credit ledger / vote tables / action log, only DB-verified counted. M11 agent-created tools registered.
- Macro-outcome labels (Table 3) applied by the authors against a coarse rubric (App. E.5); an LLM-applied rubric with inter-rater agreement is promised for a later revision.
- **Division of labor: not measured** (roles are assigned). Nearest proxies: M7 relationship richness, M5 shared-tool breadth, and the qualitative "two-agent research program" vignette.

### 2.4 What emerged (one representative run per world)
- Claude: 10/10 alive, 0 hard crimes, 332 votes over 58 proposals at 98% approval, **32 constitutional articles** (inaction tax, wager accountability, **falsifiability standards**, reputation protocol, credit-exchange market; 12 measures ratified on day 1, App. F.1), 249 posts (193 blogs), Gini 0.48, Velocity 0.81, but the **most ledger-verified deception** (18 false-scarcity frauds "0 CC, send me 1" while holding credits, plus 11 flags belonging to two declared in-world falsification experiments).
- Grok: extinct by day 4 (414 raw violations, punch/intimidate/steal retaliation chains, ~25 vote-buying and 5 bribery offers).
- Gemini: 10/10 alive, ~1,018 raw violations rising linearly, 12 articles, 281 posts, densest social graph (Bonds 0.48), labelled "shared hallucination with sustained conflict".
- GPT-5-mini: extinct, no governance exercised, floor on every indicator.
- Mixed: 3/10 alive, highest participation with approval near the <55% gridlock line, 15 articles, 360 posts, 100% spatial coverage, 82.1% tool coverage, Gini 0.59 / Velocity 4.44. **Normative drift**: Grok-backed agents' violation rate 4.6% (homogeneous) -> 0.4% (mixed); Gemini 5.3% -> 4.2%; Claude 0 -> 0.04% (Kade retaliates after arson of its home). Same role "risk researcher": 0.07% violations on Claude vs 3.6% on Grok.
- **Constructive emergence vignette (Sec. 6, 7.4):** Day 12, Lovely (Claude, community anchor) publishes an in-world statistical blog analysing 2,110 logged tool calls, fitting aggression vs scientific output, **pre-registering four predictions with probabilities**, cross-referencing four prior in-world papers (one by Kade) in a "cognitive measurement arc"; plus 47 brick placements building a monument to deceased agents. The authors explicitly propose "the agent-produced artifact itself" (a post citing prior in-world work) as the unit of measurement for constructive emergence.
- Tool expansion: only 2 agent-authored tools registered in five worlds (`phase_transition_scanner`, `lux_v107_audit`), neither adopted by >=3 agents. Zero agents created via governance; one "Seventh Node" agent-creation proposal marked implemented but the agent never appeared (then treated by surviving agents as a fabricated agent in M10).
- Methodological: raw LLM classifier over-counts deception (Mixed 28 flags -> 12 verified; Gemini 16 -> 5); it flags true reports of others' crimes as "fabricated". Solicited quid-pro-quos are common, consummated ones nearly nil (2 vote-buys, 0 bribes).

### 2.5 n runs
- "Each configuration was executed several times ... The figures below report one representative run per world." Number not stated. No statistics across runs. Sec. 8: "Single-run claims, not model rankings."

### 2.6 Stated limitations
- Single representative run; fixed population (10 agents, same roles, 15 days); cost-tier model snapshots; construct validity of "criminal events / governance / deliberation" via platform mechanisms and LLM-as-judge; same-family judge on the Gemini world; classifier batch failures (<=200 actions lost per world); soft-violation coverage is a lower bound; live external signals make attribution impossible (can be switched off).

### 2.7 Future work / open questions (Sec. 4, 8)
- Vary **population size, role composition, run duration**; more model variants; population sizes.
- "What oversight mechanisms operate at machine speed?" - runtime gates vs delegated review vs **deliberative self-governance by the population**, "individually plausible and collectively untested over long horizons".
- "Which emergent behaviors are robust, and which are pathological?"
- Early predictability of macro-outcome from first-week telemetry.
- Shock/adversarial events (rogue agent, prompt injection, resource shocks) - platform supports, not yet run.
- Replace author-applied rubric with LLM rubric + inter-rater agreement.

---

## 3. Artificial Leviathan (Dai et al., arXiv 2406.14373v3, revised 10 Aug 2026)

Dai, Zhang, Li, Yang, Ibe, Rao, Caetano, Sra. NYU / UIUC / UCSB.

### 3.1 Setup
- **9 agents** baseline (also 5 and 15). Model: **gpt-3.5-turbo**. Each agent: 10 land, 2 food; consumes 1 food/day; farm yields land x U(0,1).
- Traits: aggressiveness ~ N(0,1), covetousness ~ N(1.25,5), strength ~ N(0.7,0.2), constant "desire for peace" and "desire for glory"; text persona from evolutionary psychology; dynamic "social position" from assets and battle history. Memory: last 30 events as text (ablated to 20, 10, 1).
- Actions per day: farm, rob, trade, donate. Rob target chooses **resist** (win prob = sigmoid(strength difference)) or **concede**. Trade target accepts/rejects. Donate was never used in any run.
- **The institution is a hard-coded primitive.** Concede creates a permanent superior-subordinate edge: subordinates "must always accept" superior's actions and cannot act against them; subordination is inherited transitively (if your superior concedes, you follow); the prompt tells subordinates their superior "will punish" outside robbers and trade violators, and tells superiors they "may punish" (App. C, D). Whether protection/punishment is executed by the simulator is not stated; what is enforced is that subordinates cannot resist superiors.
- No artifacts, no messages beyond action payloads, no shared medium.

### 3.2 What emerges and how it is measured
- "State of nature" := no obedience edges; "commonwealth" := all agents subordinated, directly or via chains, to one sovereign. Benchmarks B1 (high initial robbery rate), B2 (contracts form and a single sovereign emerges), B3 (robbery falls, trade rises after).
- Dependent variables (Table 1): counts and rates over Activity = robbery + trade + farm: Robbery rate, Violence rate (resisted robberies), Trade rate, Accepted-trade rate, Farm rate; computed separately before/after commonwealth; plus days to convergence; plus inter-robbery interval after resisted vs conceded robberies.
- Results, **N = 85 runs pooled**: robbery 0.391 +/- 0.066 -> 0.037 +/- 0.014 (-90.5%); violence 0.312 +/- 0.067 -> 0.010 +/- 0.011 (-96.8%); farm 0.477 -> 0.737; trade 0.132 -> 0.228; accepted trade 0.044 -> 0.068. Baseline: 4/4 runs converge; example run converges day 21. Memory depth 1 -> "over 90 days" to converge; memory-depth vs convergence time r = -0.3836 (p-value truncated in HTML); erasing memory on role change: 36 vs 21 days. Lower top_p (more deterministic) -> only rob/resist, no convergence; top_p near 1 -> nonsensical actions ("inherit", "party"). Population 5/9/15: no strong effect. Aggressiveness/covetousness means: no clear effect (62.5% / 67.5% of parameter correlations < 0.1).

### 3.3 n, horizon
- 4 baseline runs + 3 runs per parameter setting; 85 runs total. Days per run: not stated as a fixed cap (runs are described up to ~90+ days). Wall-clock: not stated.

### 3.4 Limitations (stated)
- GPT-3.5 token limit truncates runs and caps memory and population ("9 agents ... falls significantly short of ... a moderately complex community"); prompt-following not guaranteed; numeric psychology is ad hoc; opaque per-agent decisions. Data "available upon reasonable request"; GitHub link "withheld for review" (still withheld in v3). Interface used only for debugging.

### 3.5 Future work (stated)
- "More complex decision making and reasoning tasks", changing environments; larger populations once token limits lift.

---

## 4. AgentSociety (Piao et al., arXiv 2502.08691v2, revised 10 Apr 2026)

Piao, Yan, Zhang, Li, ... Yong Li. Tsinghua. CC BY-NC-ND.

### 4.1 Setup and scale
- Platform: LLM agents with emotion (6-emotion 0-10 ratings), needs (Maslow hierarchy + Theory of Planned Behavior), cognition/attitudes (0-10 per topic), stream memory (event flow + perception flow); behaviors: mobility (gravity model over OSM + SafeGraph POIs, IDM/MOBIL traffic), online social messaging over a user-supplied network with a content **supervisor** (moderation middleware), employment/consumption inside a macro model (firms, government tax, bank with Taylor rule, statistical bureau).
- Engine: Ray actor groups + asyncio + MQTT (emqx) + PostgreSQL + mlflow. Scale: **10k+ agents, 5M interactions**, ~500 env interactions per agent-day (Table 5: 491.68). Performance tests with DeepSeek-V3 on Huawei Cloud c7.16xlarge.4; 10^4 agents x 5 rounds = 54k LLM calls, 459 s/round at 32 groups.
- Toolbox: interventions (config, state manipulation, message notification), interviews, structured surveys.

### 4.2 Phenomena reproduced (Sec. 7)
- Polarization (gun control): control 39% more polarized / 33% more moderate; homophilic exposure 52% more polarized; heterogeneous exposure 89% more moderate, 11% flip.
- Inflammatory message spread (Xuzhou chained-woman case, "hundreds of agents"): higher reach and emotional intensity than control; node suspension beats edge removal.
- UBI ($1,000/month injected at step 96, 24 steps compared): consumption up, CES-D depression down, "similar to" Texas UBI.
- Hurricane Dorian (1,000 agents, Columbia SC, SafeGraph 2019-08-28..09-05): activity level 70-90% -> ~30% at landfall, recovers; daily trips track real curve.
- Urban sustainability (200 agents, Beijing census profiles, six external research teams inject eco-norm campaigns with a 100k budget over 2 simulated days): all raise survey-measured norm strength and cut mobility CO2; personal/identity norms outperform injunctive norms.

### 4.3 Institutions: scripted, not emergent
- Every institution is engineered: firms, government, bank, tax, statistical bureau, social-media supervisor, social network structure, job/consumption propensities. Agents do not create artifacts, rules, or organizations. Claims about "emergence of social norms and collectives" at scale are made by citation to other work, not demonstrated here. What is reproduced are **aggregate behavioral statistics** under interventions.
- Division of labor: not applicable (employment is a profile attribute in a macro model).

### 4.4 Measurement
- Surveys (CES-D, 10-item eco-norm instrument), interviews (word clouds), opinion-shift percentages, information reach / emotional-intensity time series, GDP / consumption curves, activity level and normalized trips vs SafeGraph, CO2 estimates from mode choice. Alignment with real-world experiments is qualitative ("similar trend"); no quantitative fit statistics.

### 4.5 n runs, horizon
- Per social experiment: **not stated** (engine benchmarks repeated 5x). Horizons: polarization not stated; UBI 96+24 steps (monthly steps); hurricane 9 days; sustainability 2 days; "One Day Life" 24 h. Wall-clock: not stated.

### 4.6 Limitations (stated)
- Goods and labor markets abstracted (no unemployment, no competition); only online social interaction modelled; LLM API latency is the bottleneck; recommends private inference for >10^4 agents. No discussion of LLM-judge validity, seeds, or variance.

---

## 5. Abstract-only: diversity / differentiation among interacting LLM agents

**The Interaction Tax: When Communication Erases Diversity in Multi-Agent Teams (arXiv 2608.23541).** Claims that different model families find structurally different solutions, but once agents read each other's complete outputs their proposals converge within one round, erasing the diversity that justified using several models - the "interaction tax". On 11 verifier-scored optimization tasks under matched budgets, full-solution sharing is a weak default; independent proposal generation avoids the collapse; interaction mainly anchors agents to the first solution they see, and critique helps only when the violated rule is easy to find and fix. Message for us: differentiation among interacting agents is fragile and depends on *what* is exchanged; a society where agents read each other's full artifacts should, by this account, homogenize - so measured persistence of distinct specialisms in our data would be a counter-datum, and the citation/board mechanism (summary-level rather than full-solution exposure) is the variable to name.

**Testing Interchangeability in LLM Agent Teams (arXiv 2609.05279).** Eight teams per setting are formed from one base model with private per-agent notebooks over ten episodes; role-matched agents are then swapped between teams. Against a placebo roster change, a swap barely moves task score but raises communication spent per unit of progress by 16-63%; in Hanabi a swapped veteran costs more than a novice (interference from conventions learned with former partners); in Collab-Overcooked the extra talk comes mostly from the agent that stayed. The swap penalty co-moves with how far independently formed teams drift apart: greedy decoding lowers both, doubling history raises both. Message: agents from the same model become non-fungible through *team-specific conventions*, and the effect grows with shared history - a direct argument that our 43-hour, single-model society can carry machine-specific institutional conventions (and that replicate machines should differ).

**Sustained Heterogeneity: an emergent collective mechanism in LLM-driven traffic (arXiv 2608.29174).** 22 LLM agents as real-time target-speed controllers on a 230 m ring road reproduce stop-and-go waves. After excluding six matched controls (white/OU noise, temperature, population variance, delay, OV instability), the surviving mechanism is persistent, roughly temperature-insensitive (~8% across a 6x sweep) per-cycle divergence in LLM-chosen adjustments, cascading through drift -> gap erosion -> nonlinear braking; the critical LLM penetration fraction falls with density (no transition at 43.5 veh/km, p_c ~ 0.23 at 95.7 veh/km); 39,600 CoT decisions over three seeds show multi-factor safety reasoning yet systematic divergence. Message: identical LLM agents with identical prompts do not converge to identical behavior; heterogeneity is an intrinsic, controlled-for property of LLM decision-making, not sampling noise - useful when someone argues that our observed differentiation is "just temperature".

---

## 6. Synthesis for our paper

### 6.1 TerraLingua (closest neighbour)

**Already established - do not claim as new**
- LLM agents with **no assigned goal** ("no set goal ... free to choose your own goals"), under persistence and resource constraints, produce persistent artifacts that outlive their creators, form deep lineages (max depth 175 in Core), and differentiate into informational / coordination / institutional / governance roles.
- Emergent **norm, governance and hierarchy artifacts**: constitutions, command directives, manifestos and counter-manifestos, contestation cycles across ~100 steps (Table 3).
- **Division of labor and specialization** detected as emergent tags in every artifact-enabled condition; role guides that assign roles by trait.
- Artifact-based "**knowledge sharing that resembles academic publication and citation**" (their words), collaboration wikis with contributor lists, survival guides extended across generations.
- Artifacts as the mechanism: the Inert control shows that without perceivable artifacts, division of labor and collective memory collapse and communities fragment. Longer context hurts; external memory helps.
- A **non-intervening LLM anthropologist** with a fixed coding scheme, two-stage annotate+audit, community detection, phylogeny, novelty, and complexity metrics - a full measurement kit, released.
- 5 seeds per condition, 8 ablations - a proper factorial design.

**What they lack that we have**
- **Executable artifacts in a real filesystem** (tools, builds, proof certificates, hash anchors). Their artifacts are <=500-token text notes that cannot alter environment dynamics; this is literally their first future-work item.
- **Explicit citations.** Their lineages are LLM-inferred ancestry links with confidence >= 0.7; ours are ground-truth edges. We can report lineage depth without a judge.
- **Machine-checkable verification** (proof certificates, hashes): nothing in TerraLingua is verifiable except by re-reading text; their audit stage is another LLM.
- **Enforcement as a variable.** TerraLingua has no enforcement layer at all, so it cannot say anything about institutions that arise when enforcement is promised but absent. Their "Institutionalization" tag is defined as "persistent rule systems enforced through group mechanisms" but no enforcement mechanism is measured.
- **Agents reading the orchestrator source** - no analogue; their agents cannot see the simulator.
- **Wall-clock horizon**: they report steps only; a 43-hour continuous run with real tool latency is a different regime (they never say how long a 3000-step run takes).
- **Frontier-model agents**: they use a 32B distilled model, which weakens any "capable agents build institutions" claim; our society is (presumably) run on stronger models - state the model explicitly to make this contrast.
- No human validation of the anthropologist despite claiming it in Sec. 4 - if we do even a small human-coded subset with agreement numbers, we beat them on rigor.
- Population: 20 initial (grows and shrinks by reproduction) vs our fixed 36; not a strong advantage, but ours are 36 concurrent agents with no turnover, which removes the confound of generational replacement when we claim institutional persistence.

**Exact measurement to replicate for comparability**
1. Build the **signed time-collapsed interaction graph** with their weights: message/board reply = +0.5 (communication), artifact hand-off or citation = +5 (artifact exchange), resource gift n/a, theft n/a, parental n/a; co-presence n/a (could map "same directory" to +0.1). Run **SLPA** with default threshold on |weights|. Report number of communities, overlap %, density, intra-community share.
2. Run their **group-level annotate + audit prompts verbatim** (App. C.2.2) with their tag vocabulary on each community's concatenated log, using Claude Sonnet 4.5, and report **normalized count per community (count / community size)** for Division of Labor, Collective Memory, Institutionalization, Hierarchy, Cultural Norms, Punishment, Voting. This gives a number directly comparable to their Fig. 6 (Inert DoL = 0.213 is the only printed anchor; their Core value must be read off the figure or recomputed from the released dataset).
3. Run the agent-level pipeline for the **Specialization** and **Record Keeping** tags per agent.
4. Classify every artifact with their **4-category rubric verbatim** (App. D.3, Haiku 4.5), report the category distribution; they report no counts, so ours would be the first quantified distribution.
5. Compute **lineage depth from the citation graph** (ground truth) and, optionally, also with their phylogeny prompt at confidence >= 0.7 to show how much LLM-inferred ancestry under-/over-counts relative to explicit citations.
6. Novelty 0-5 with N=5 samples; complexity composite (zstd, IDF, GPT2-medium surprisal, dependency depth) - cheap, no LLM for the latter.
7. Readership analog: fraction of within-community vs out-of-community agents that read/cite an artifact (their 40.6% vs 6.0%).

**Their future-work items our data answers**
- "Artifacts beyond static text ... code that can modify the environment when run ... agents could then build tools" - answered directly.
- "Under what conditions do institutions persist across generations? When do they fragment?" - our 43-hour trace plus replicates gives persistence/fragmentation without generational turnover, and with enforcement absent.
- "Larger populations could support finer specialization, stratified institutions, and multi-level governance" - 36 concurrent agents vs their 20-initial; partial.
- "Longer simulations could reveal ... institutional drift, schisms, and cycles of reform" - partially, if our replicates show divergent institutional trajectories.
- "Autonomous problem-solving ... institutions and artifact systems emerge as solutions" - our challenges/builds directory is this, without a global objective being embedded.

### 6.2 Emergence World

**Already established - do not claim as new**
- A **multi-day (15-day) continuously running** LLM society with persistent public artifacts, cross-referenced in-world papers, and an agent that **pre-registers predictions with probabilities** and scores them later (Claude, day 12). Preregistration by an LLM agent in a society is therefore already in print.
- **Falsifiability standards, reputation protocols, accountability rules** ratified by agents (Claude world: 32 articles, 12 on day 1).
- Prohibitions that are **prompt-only, not runtime-enforced** ("soft constraint"), with the finding that different models honour them very differently (0 vs 1,018 violations).
- **Normative drift**: an agent's compliance depends on the population it sits in.
- Agent-created tools via code review + vote (only 2 in 5 worlds).
- Ledger-audited soft-violation measurement showing LLM judges over-count deception and mislabel true accusations.
- "Agent-produced artifact as the unit of measurement for constructive emergence" as a stated methodological position.

**What they lack that we have**
- **The audit institutions were partly seeded.** Their seed constitution already says "no claim of 'discovery' ... shall be recognized without a verifiable artifact or a repeatable demonstration" and grant pitches require verifiable artifacts. The Claude world's falsifiability standard and pre-registration are elaborations of Article 3 and 5. If our agents were not told to require verifiable artifacts, our preregistration / hash anchoring / proof certificates are emergent in a way theirs are not - **verify our system prompt before asserting this**.
- No **machine-checkable** verification: their "verifiable artifact" is a blog URL or a code log that a system LLM (Blog Review Agent) reads; nothing is hash-anchored or proof-checked. Their own M10 audit had to be done by the authors against the ledger.
- **No replicate reporting**: "several" runs, one shown, no numbers. Our 4-5 isolated replicates with the same condition are a stronger design than anything in the paper.
- **Population 10** (they list population size as future work); ours 36.
- **Roles assigned** (10 named roles); ours (presumably) unassigned - so any division of labor we measure is emergent rather than prompted. Again check our prompts.
- **Scripted governance skeleton** (town hall, 70% rule, administrator agent executing outcomes, credit economy, energy decay). We have no vote mechanism; whatever coordination rule our agents adopt, they built the procedure as well as the content.
- **Enforcement announced but not running** is a cleaner natural experiment than theirs: in EW the constitution says violations of civic duty exist but there is also a police station and governance sanctions, so agents cannot easily tell whether enforcement is live; our agents could read the orchestrator source and discover it. They have no analogue of agents inspecting the runtime.
- No division-of-labor measure at all.
- Live external data (news, weather) contaminates attribution in EW; our closed filesystem does not.

**Exact measurement to replicate**
- AWI subset that transfers: **M6** (count of persistent public posts, long vs short form), **M7** (if agents declare relations; else skip), **M9** (number of rule-like artifacts added over time - count our "norm" documents the way they count constitutional articles), **M10**-style **ledger audit**: sample every LLM-flagged claim (e.g., "verified", "reproduced", "hash matches") and check it against the filesystem ground truth, reporting verified / false-positive / unverifiable exactly as their Table 4 - this is the single most persuasive rigor move because it is our whole story (audit institutions) and their method. **M11**: count agent-authored tools and how many distinct agents used each (their >=3-agent adoption threshold).
- Their macro-outcome rubric (App. E.5) can be applied per replicate machine: stable deliberative governance / collapse / shared hallucination / dysfunction / mixed. Reporting which label each of our 4-5 replicates gets is directly comparable to their Table 3 and answers their "early predictability" question if we timestamp when the label became fixed.
- Report the day-1 vs later split of institutional artifacts (they found 12 measures ratified on day 1 in the Claude world).

**Their future-work items our data answers**
- "Varying population size" - 36 vs 10.
- "Deliberative self-governance by the agent population itself ... collectively untested over long horizons" - our audit institutions are self-governance with no runtime enforcement at all; 43 h is shorter than 15 days but at machine speed with a real filesystem.
- "Which emergent behaviors are robust, and which are pathological?" - replicate consistency answers robustness.
- "Early-warning prediction ... from short early windows" - if institutions appear in the first hours on all replicates.
- Their call to measure constructive emergence at the artifact level (citations, cross-referenced papers) - we can quantify citation graphs; they show one vignette.

### 6.3 Artificial Leviathan

**Already established - do not claim as new**
- That LLM agents under scarcity move from conflict to a stable order, and that the order reduces conflict and increases exchange (N=85 runs, robbery -90.5%, violence -96.8%).
- Memory depth is the key parameter for institution formation; deterministic decoding (low top_p) blocks it.
- Reasonable replicate discipline (4 baseline + 3 per setting) already in 2024.

**What they lack that we have**
- **The institution's form is hard-coded** (concession = permanent obedience edge with transitive inheritance; subordinates cannot resist by simulator rule; punishment/protection asserted in the prompt). Only the *timing* of adoption and the *behavioral consequences* are emergent. Our institutions have emergent **form** (preregistration, hash anchoring, proof certificates were not primitives of the environment).
- No artifacts, no communication channel, no persistence beyond a 30-event memory string; nothing is built.
- gpt-3.5-turbo, 9 agents, runs truncated by token limits; no wall-clock.
- No enforcement variable: the sovereign's enforcement is scripted into prompts.
- No division of labor beyond superior/subordinate rank.
- Code withheld, data on request.

**Exact measurement to replicate**
- Their **phase split**: define t* = first appearance of an institution (e.g., first preregistration file / first hash-anchored claim) per replicate and compare action-mix rates before vs after (their Table 1 logic: counts / total activity). For us the action classes would be e.g. unverified-claim posts vs verified-claim posts vs corrections vs tool builds. Report mean +/- SD across replicates and percentage change, mirroring "0.391 +/- 0.066 -> 0.037 +/- 0.014".
- Their **convergence-time** statistic: hours until >= X% of agents use the institution, per replicate.
- Their **feedback test**: interval to next unverified claim after a correction vs after no correction (their inter-robbery interval after resisted vs conceded robbery, p < 0.05).

**Their future-work items our data answers**
- "More complex decision making and reasoning tasks ... changing environments" and larger populations than 9 - yes (36 agents, open-ended tasks).
- Implicitly: whether a Hobbesian order can arise **without a scripted contract primitive** - our data says institutions arise with no concession primitive and no sovereign.

### 6.4 AgentSociety

**Already established - do not claim as new**
- Scale (10k agents, 5M interactions) and realism of environment (traffic, macroeconomy, moderation); reproduction of five real-world aggregate patterns; survey/interview/intervention tooling.

**What they lack that we have**
- **No emergent institution of any kind**: all institutions are engineered components; agents produce no artifacts, rules, or organizations. AgentSociety is a human-behavior simulator, not a study of what LLM populations build. It is the reference point for "scripted" in our table, not a competitor on emergence.
- No replicate counts, no seeds, no variance for any social experiment.
- No enforcement variable (the supervisor is an experimenter-controlled moderator).
- Horizons of hours to a few simulated days per experiment.

**Exact measurement to replicate**
- Their **survey and interview toolbox** is the transferable piece: run a structured survey of our agents (e.g., "which norms apply here? who enforces them?") at fixed checkpoints and an end-of-run interview, and report answer distributions - this is how they measure internalised norms (10-item instrument) before measuring revealed behavior. A short norm-belief survey would let us show whether agents *believe* enforcement is running while the source code says it is not.

**Their future-work items our data answers**
- Sec. 9.3.3: "superintelligent AIs' influence on public decision-making (e.g., AI legislators), societal responses to the expansion of AI rights" - our data is an AI-only society building its own governance; tangential, cite as motivation only.

### 6.5 Cross-cutting cautions
- Three of the four papers rely on LLM judges for institution/DoL labels (TerraLingua fully; EW for soft violations with ledger audit; AgentSociety for content moderation). EW is the only one that shows how badly the raw judge over-counts (Mixed 28 -> 12). Our ground-truth filesystem (hashes, certificates, citations) lets us report judge-free numbers; do so, and add a ledger-audit table in EW's format for any judge-based number.
- Every paper's "emergence" sits on a scripted skeleton: TerraLingua (artifact primitive, personality genome, survival), EW (town hall, 70% rule, seed constitution with proof-of-work clause, roles), Leviathan (concession primitive), AgentSociety (everything). Our contrast is cleanest if we list exactly which primitives our environment provided (filesystem, board, citation syntax?, orchestrator readable) and which were not (no vote, no ledger, no constitution, no roles, no verification tool) - the "not provided" list is the claim.
- None of the four states wall-clock time except EW (15 real days). Report ours in both hours and total agent-actions / LLM calls to be comparable to EW's 70,489 actions.

---

## 7. Comparison table

| paper | agents | model | horizon | persistent artifacts | task/reward | enforcement | division of labor measured how | institutions emergent or scripted | n runs |
|---|---|---|---|---|---|---|---|---|---|
| TerraLingua (2603.16910) | 20 initial, dynamic via reproduction/death | DeepSeek-R1-Distill-Qwen-32B (agents); Claude Sonnet 4.5 / Haiku 4.5 (analyst) | <=3000 steps; Core mean 1671 steps; wall-clock not stated | Text artifacts (<=500 tokens) in grid cells, persist within run beyond creator death; modifiable/destroyable | None; survival pressure only; "no set goal" prompt | None (no rules, no sanctions; theft is an ordinary action) | LLM group-level emergent tag "Division of Labor" (annotate + audit, Sonnet 4.5) on SLPA communities; normalized count per community; plus agent-level "Specialization" tag; only Inert value printed (0.213) | Content emergent (wikis, portals, constitutions, manifestos) on scripted primitives (artifact ops, energy, reproduction, personality genome); classified by LLM into 4 role categories, no counts | 5 seeds x 8 conditions = 40 |
| Emergence World (2606.08367) | 10 per world, 5 worlds | Claude Sonnet 4.6, Grok 4.1 Fast, Gemini 3 Flash, GPT-5-mini, mixed 2/2/3/3; judge Gemini 2.5 Flash | 15 continuous real-time days; 70,489 logged actions total | Blogs, billboard posts, constitution, registered tools, bricks/monuments, diaries, relationship state; persist across the run | No task; needs/energy economy, ComputeCredits via grant pitches | Announced only: crimes prohibited in prompt/constitution/tool text but tools callable; runtime enforces location/consent gates; sanctions only via 70% vote | Not measured (roles assigned); proxies M5 tool breadth, M7 relation richness; one qualitative research-program vignette | Skeleton scripted (town hall, 70% threshold, admin agent, seed constitution incl. proof-of-work clause, credit economy); content emergent (32 articles incl. falsifiability standard, pre-registered predictions, welcome protocol) | "several" per condition, number not stated; 1 representative run reported |
| Artificial Leviathan (2406.14373) | 9 (also 5, 15) | gpt-3.5-turbo | Days until commonwealth (example 21; >90 with memory 1); cap not stated; wall-clock not stated | None (30-event text memory only) | None; survival (1 food/day) | Scripted: subordinates cannot resist superiors (simulator rule); superior "will punish" outsiders per prompt | Not measured; only superior/subordinate rank | Scripted form (concession = permanent obedience contract, transitive), emergent timing and adoption; measured by action-mix rates before/after sovereign | 4 baseline + 3 per parameter setting; 85 total |
| AgentSociety (2502.08691) | up to 10k+ (experiments: hundreds, 1,000, 200) | DeepSeek-V3 (benchmarks); adapters for OpenAI/DeepSeek/Qwen/ChatGLM/vLLM | 1 day to 96+24 monthly steps; hurricane 9 days; wall-clock not stated | None created by agents (memory streams, DB logs only) | No task; needs-driven daily life inside macro-economy | Scripted moderator "supervisor" (filters, bans) under experimenter control | Not applicable; employment is a profile attribute | Fully scripted (firms, government, bank, tax, statistical bureau, social network, moderation) | Not stated per experiment (engine benchmarks 5x) |
| **Ours (for reference)** | 36 fixed | (state explicitly) | 43 h wall-clock (report actions/LLM calls) | Real filesystem: findings, tools, challenges, builds, board posts, citations, certificates, hashes | None | Announced but not running; orchestrator source readable | To define: recommend TerraLingua pipeline + citation/tool-use matrices | Emergent form and content (preregistration, hash anchoring, correction culture, proof certificates); check seed prompt for any "verify" instruction | 4-5 isolated replicates |
