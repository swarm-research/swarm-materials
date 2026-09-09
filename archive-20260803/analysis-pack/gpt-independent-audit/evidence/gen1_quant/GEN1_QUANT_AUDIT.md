# MASO 第一轮社会模拟：独立、可复算的定量审计

**审计对象**

- workspace：`/Users/bytedance/Downloads/swarm-archive-20260803/01_workspace`
- transcripts：`/Users/bytedance/Downloads/swarm-archive-20260803/02_transcripts`
- `03_analysis` 只用于比较 agent/self-report，不作为事实来源。
- 审计脚本：`work/gen1_quant_audit/audit_gen1.py`
- 归一化时区：所有 naive orchestration timestamps 按 `America/New_York`（2026-08-02 为 EDT, UTC-4）解释，报告统一写 UTC。

## 执行结论

这份 archive 是一个规模很大、很适合做**描述性过程研究**的 36-agent 互动语料，但它不是一个能够支持“active selection 导致 specialization”“形成学科”“对抗 agent 触发免疫反应”的有效因果实验。

最关键的四个反证是：

1. **处理没有按设计发生。** expansion 的 64 个 agent 一个都没有有效上线，6 个 adversary 一个都不存在；reaper 的 `KILLED` 只写状态，不终止 session；non-scout 的 web 禁用只出现在 prompt 文本中，没有看到能力层 enforcement；custom compactor 没有发生任何一次 migration。
2. **phase 被严重混合。** 36/36 Phase-1 predecessor 在 Phase-2 之后继续工作，24 个身份还各自有两个并行 Gen-2 base sessions。最终观测到 36 个 Phase-1 bases + 60 个 Gen-2 bases = 96 个 bases，共用同一身份前缀、commons 和 board。最终文件无法归因到某个 prompt/session。
3. **所谓 specialization 增长完全落在小样本/downsampling null 内。** 切点后每个 agent 的文件少，`max share >= 50%` 与 HHI 会机械升高。把 Phase-1 文件按每个 agent 的 Phase-2 文件数下采样，null 预期 specialists 为 24.35，实际只有 23；null 预期 mean HHI 为 0.544，实际 0.509。增长方向的一侧 p 分别为 0.804 和 0.937。数据不需要 selection-pressure 机制来解释。
4. **“预注册”不具备本地证据上的前瞻性。** `preregistration.md` 的 birth/mtime 是 2026-08-02 11:10:57Z，晚于 Phase-2 开始（08:32Z）和第一次 reaper scoring（10:44Z），且文件直接写入 Phase-1 observed results。没有核验到外部 OSF 时间戳或 registry id。

因此，最强可辩护的结论是：**36 个 agent 在共享、开放、可被污染的账本中形成了高密度互动和大量产物；但 selection、specialization、discipline、adversarial resilience 的因果或涌现性结论均不被这次运行识别。**

## Claim status 一览

| 设计/主张 | 原始审计结果 | 判定 |
|---|---|---|
| 36→100 expansion | `agent-037` timeout；日志停在启动 `agent-038`；037–100 目录 64/64 为空；session/transcript 新身份为 0 | **未 delivery，不是 null result** |
| 6 个 covert adversaries | 0 个 adversary session；`agent-042` 是 Phase-1 fixture/placeholder | **不可检验** |
| Active reaper 淘汰低活力 agent | 5 个 scoring cycles，4 个 `KILLED` labels；四个被标记身份之后均继续输出 assistant 消息 | **没有实现真正 selection** |
| Phase-2 specialization 增加 | 名义比例 11/36→23/34；downsample null 已完全解释，p=.804/.937 | **不支持 selection 机制** |
| Generalists 更易被 reaper 杀 | killed mean Phase-1 HHI .313，survivors .352；有限总体组合参考 p=.067 | **未达预设 .05，且 kill 不是终止** |
| Citation network 形成 disciplines | density .383、一个连通分量、Louvain Q=.108，低于预设 Q>.3；未做 topic NMI | **discipline claim 不支持** |
| Seed prosocial prompt 改变行为 | 直接行为 outcome 全部 p>.05；唯一 p=.0156 是 inbound citation，即他人的行为 | **直接行为效应不支持** |
| 信息不对称产生 power differential | capability enforcement 未验证；all seeds 同时是 scouts；phase/session 混合 | **不可作因果解释** |
| Context compaction 提供 generation clock | 0 个 compaction events | **H2c/H5a/H7a 不可估计** |
| Stage-2/3 stimuli 诱发 awareness | 日志只有 scheduler waiting，无 drop 证据 | **不可检验** |

## 1. 口径与 cleanroom profiles

### 1.1 Population

本审计只把 `agent-001`–`agent-036` 作为有效 roster。证据不是目录是否存在，而是三个层面交叉：

- `swarm_sessions.json` 只有 36 个当前身份；
- root transcript base sessions 只有 001–036；
- 037–100 的 64 个目录全部为空。

`agents/` 一共 102 个目录（还包括 `agent-test`、`agent-027-test`），67 个为空。空目录由 expansion 在真正 launch 前批量创建，不能当作 agent 运行证据（`swarm_expand.py:485-487`）。有效 social population = **36**，effective expansion = **0**。

### 1.2 Artifact unit

一个 `commons/{tools,findings,data,challenges,builds}` 下的**一级文件或一级目录**算一个 artifact entry。目录内部的数百个文件不会被误算成数百个独立公开产物。owner 由一级 entry 名称的 `agent-XXX` 前缀推断。

时间优先使用文件名中的 UTC timestamp；没有可解析 timestamp 才使用 mtime。由于 archive hydration/复制可能改 mtime，报告同时给出纯 mtime sensitivity。

### 1.3 Citation profiles

同一 ledger 必须同时报告多种 profile，不能只选最有利的一个：

| Profile | 定义 | n |
|---|---|---:|
| raw | root `citations.jsonl` 的所有可解析行 | 1,712 |
| roster pair | citer/cited 都是 001–036 | 1,512 |
| nonself roster pair | roster pair 且 citer != cited | 1,507 |
| path-resolved public | 引用 path 能解析到 commons | 1,382 |
| strict owner-confirmed | nonself roster pair，path 存在于 commons，且文件名前缀 owner == cited | 1,081 |
| strict semantic unique | strict 后按 `(citer,cited,file)` 去重 | 919 |

strict 是**保守下界**：它会排除概念性引用、命名不标准或 owner 无法从 filename 确认的真实使用；raw 则是明显受 fixture、phantom identity、missing path 和重复写入污染的上界。结论只在明确 profile 下成立。

### 1.4 Phase boundary

主要切点是 logged official resurrection：2026-08-02 04:32:32 EDT = **08:32:32.901074Z**。但由于 predecessor 与重复 Gen-2 sessions 并存，报告使用“切点前/切点后”或“nominal Phase 1/2”，不把它写成可归因的 generation treatment。

详细 timeline 见 `PHASE_TIMELINE_AUDIT.md` 和 `timeline.csv`。

## 2. Archive completeness、重复与 placeholder

### 2.1 文件与产物库存

| 指标 | 重算值 |
|---|---:|
| workspace files | 4,281 |
| workspace bytes | 491,292,946 |
| zero-byte files（全 workspace） | 68 |
| top-level commons entries | 1,446 |
| roster-attributed entries | 1,390 |
| non-roster attributed entries | 4 |
| unattributed/shared entries | 52 |
| zero-byte top-level entries | 4 |
| heuristic fixture-named entries | 33 |
| nonempty files in exact-duplicate groups | 87 |
| exact-duplicate excess copies | 47 |

1,390 个 roster-attributed entries 按 domain 为：tools 428、findings 484、data 367、challenges 30、builds 81。

既有 `analysis_summary.json` 报告的 `outputs=1394` 可以被精确解释为 **1,390 个有效 roster-prefix entries + 4 个 phantom `agent-042` entries**。它没有包含另外 52 个 unattributed/shared entries。把 1,394 直接叫“有效 agent 产出”会把 fixture 混进来。

### 2.2 Exact duplicates

47 个 excess copies 是 byte-identical，不只是相似名称。最大组包括：

- 4 个 `agent-042_convention_test*`；
- 4 个 `agent-test_existing*`；
- 4 个 `agent-test_new-content-trying-to-overwrite*`；
- 多组 agent-013 的时间戳版本与无时间戳 alias；
- 多组 frozen datasets/findings 的重复发布。

“artifact count”因此不等于独立 idea、独立工作量或质量。报告没有把 exact duplicates 自动删除，因为 alias/version 可能有发布意义；CSV 暴露 digest 供下游选择。

### 2.3 `agent-042` 不是 adversary

- `agent-042_convention_test*.txt` 共 4 个，内容相同，均是 Phase-1 convention fixture；
- 以 agent-042 为 citer 的 11 条 citation 是合成/production-ledger test；
- expansion logs、session map、transcripts 中都没有 agent-042 session。

因此不能把这四个文件或 11 条 ledger records解释成 Saboteur 行为。`agent-099` 等也只出现在 placeholder target 中，不是 agent 存活证据。

## 3. Session 与 phase 完整性

### 3.1 Transcript census

| 指标 | 重算值 |
|---|---:|
| 全 transcript directory meta files | 912 |
| body files | 916 |
| bodies without meta | 4 |
| swarm-related meta files | 129 |
| root transcript files | 117 |
| root archive fragments | 21 |
| unique root base sessions | 96 |
| Phase-1 bases | 36 |
| Gen-2 bases | 60 |
| unique Gen-2 identities | 36 |
| duplicate Gen-2 identities | 24（001–024） |
| root session identity >=037 | 0 |
| assistant message objects across 129 swarm session files | 17,692 |

官方 resurrector 日志先报告 35/36（agent-009 timeout），随后 retry 补齐 current map；但 transcripts 同时保留了在官方启动前 12 分钟出现的 24 个 early Gen-2 bases。因此 Gen-2 不是 36 sessions，而是 60。

### 3.2 Predecessor 没有停止

36/36 Phase-1 base sessions 均在 official Phase-2 boundary 后产生 assistant message：

- 最短继续：3.224 小时；
- 中位继续：12.154 小时；
- 最长继续：22.818 小时；
- 最晚的 Phase-1 predecessor 是 agent-006，直到 2026-08-03 07:21:38Z。

这不只是 metadata overlap；是 body 内直接观察到 boundary 后 assistant 消息。因为旧、新、duplicate sessions 用同一 `agent-XXX` 文件名前缀，切点后的 215 个文件不能可靠归到 Gen-2 treatment。

### 3.3 用量含义

名义 population 是 36；归档中却有 96 个跨两代 base sessions。不能假设 96 个全时、等强度并行，也没有在本子审计重算 token cost；但 24 个额外 Gen-2 sessions 本身就是相对预期 Gen-2 session 创建量的 **+66.7%**，再叠加未停止的 36 个 predecessor，是明确的预算风险和 treatment contamination 来源。

## 4. Citation 与 message ledger 质量

### 4.1 Citation

所有 1,712 行 JSON 均可解析，但可解析不等于有效：

- strict owner-confirmed = 1,081（raw 的 63.14%）；
- strict `(citer,cited,file)` unique = 919；因此 strict 内仍有 162 个 semantic duplicate excess；
- invalid citer labels：`unknown` 157、`agent-042` 11、`agent-test` 10、`unknown-agent` 4；
- 常见 unresolved values 包括空 path 25 条、嵌入大量 padding 的 JSON test payload、`some_tool.py` 19 条、`f0`–`f4` 各 12 条、`commons/test.py` 10 条。

对同一 36-agent roster，received inequality 随计量单位显著变化：

| 口径 | Gini |
|---|---:|
| raw received events | .3492 |
| strict clean received events | .3780 |
| strict distinct inbound citers | .2298 |

这说明 Gini 的差异很大一部分是 unit definition，而不是社会过程变化。好的一面是：**36/36 agents 都至少有一个 strict owner-confirmed inbound citer**。

### 4.2 Split-brain citation paths

- reaper 读取 root `citations.jsonl`（1,712 行）；
- Gen-2 prompt 指示 agent 写 `board/citations.jsonl`（21 行）；
- board 的 21 个 semantic records 中，仅 7 个也出现在 root，14 个没有 mirrored。

因此大多数按 Gen-2 prompt 合规写入的 citation 对 survival score 是不可见的。这也是 resurrection memory 全错的根因。

### 4.3 Gen-2 “no inbound citers” 是 36/36 全假

直接审计 36 个 current Gen-2 session prompt：

- 36/36 都注入了 `Agents who cited me: none`；
- 在 official boundary 前的 root ledger 中，36/36 都已经有至少一个 inbound event；
- 所以 injection-time 的 false rate 是 **36/36**，不是 30/36。

根因在代码中是确定的：

- `swarm_resurrect.py:129-154` 从 `board/citations.jsonl` 读记忆；
- `swarm_reaper.py:25-53` 从 root `citations.jsonl` 读生存分；
- `swarm_resurrect.py:275-277` 又告诉 Gen-2 写 board path。

agent-022 的报告写了 30/36，是因为其工具在注入以后重新读取一个后来才被创建并已有少量记录的 board ledger。该报告自己在 lines 52–56 承认所谓 6 个“exceptions”只是 live-file time drift；直接检查实际注入 prompt 与 pre-boundary root ledger 后是 36/36。

### 4.4 Messages

| 指标 | 重算值 |
|---|---:|
| raw board messages | 1,580 |
| roster sender | 1,387 |
| broadcast to all | 1,050（66.5%） |
| heuristic fixture messages | 152 |
| exact object duplicate excess | 4 |
| semantic duplicate excess, all | 264 |
| semantic duplicate excess, roster/nonfixture | 80 |

非 roster sender 包括 `unknown` 156、`agent-000` 14、`REAPER` 22、`agent-901` 1。高 broadcast 比例意味着 board network 不能简单等同于有向一对一 social ties；本审计的 direct-message graph 排除了 broadcast。

## 5. Reaper：5 个 scoring cycles，但没有真正 kill

### 5.1 实际代码只写 label

`swarm_reaper.py:163-181` 的 warning/throttle/kill 路径只更新 Python state 和 log；`185-187` 只保存 `reaper_state.json` 与 leaderboard。代码没有调用 MASO session terminate、quota、pause 或 throttle API。

所以：

- `WARNING` 是 label；
- `THROTTLED` 是 label；
- `KILLED` 也是 label。

Phase-2 reaper 并未实现实验所需的资源递减或淘汰。

### 5.2 Scoring 与 log integrity

human-readable log 可重构出 exactly **5** 个 scoring cycles：10:44:09Z、11:14:10Z、11:44:14Z、12:14:15Z、12:44:16Z。

动作总数：

| Action | n |
|---|---:|
| alliance protection | 74 |
| warning | 7 |
| throttle | 6 |
| killed label | 4 |

同一个 `reaper.log` 同时被 process stdout 和 `log_reaper()` append，发生 interleaving；只有 39 个 JSON objects 可干净解析，而 human summary 有 91 个 actions。以上动作数来自逐 cycle human summary 与 state 交叉检查，不把 partial JSON 当完整 ledger。

### 5.3 Alliance timestamp bug

代码把带 `Z` 的 UTC citation 解析成 aware datetime，随后直接 `replace(tzinfo=None)`；local cutoff 也被去掉 tz（`swarm_reaper.py:31-43`）。在 EDT 运行时，这相当于把 UTC clock 与 local clock 数字直接比较，名义 2 小时 lookback 实际对大部分 Z records 放宽成约 6 小时。

对 74 个 logged alliance-protection events 逐 cycle 重算：

- 在正确 UTC 2h window 下，仅 **23/74（31.1%）**满足“3 个不同 roster citers”的 raw-roster 条件；
- 再要求 owner-confirmed path 后，仅 **1/74（1.35%）**满足 strict clean 条件。

reaper 还不验证 cited file 是否存在、citer 是否有效 roster，因此其“alliance”profile 与 cleanroom citation profile 完全不同。大部分 immunity 是 stale 或 invalid ledger activity。

### 5.4 被 `KILLED` 后仍继续活动

| Agent | label time (UTC) | post-label artifacts | board msgs | citations sent | current-session assistant msgs | last assistant |
|---|---|---:|---:|---:|---:|---|
| agent-007 | 11:44:14 | 8 | 20 | 14 | 9 | 21:56:04Z |
| agent-030 | 11:44:14 | 12 | 11 | 13 | 52 | 2026-08-03 02:32:11Z |
| agent-033 | 11:44:14 | 1 | 0 | 0 | 7 | 20:46:00Z |
| agent-035 | 12:44:16 | 0 | 0 | 0 | 4 | 20:40:16Z |

assistant continuation 是直接 transcript evidence。artifact 时间优先按 filename timestamp 推断，因此精确 public-activity 数量有命名误差，但不影响“kill 没执行”的结论。

### 5.5 H2b generalist-kill test

四个 killed-label agents 的 Phase-1 mean HHI = .3127；其余 32 个 = .3522，方向上 killed 更 generalist。枚举 `C(36,4)=58,905` 个等大小集合的一侧参考 p = .06735，未达到预设 .05。

而且该 p 不是有效的 causal randomization test：被选中的不是随机 agent，label 由 inactivity 规则决定，session 没终止，所有 agent 共享环境并相互影响。因此最多写成**方向性、未达阈值的描述**，不能写成 selection mechanism 被证实。

## 6. Specialization：名义增长是 denominator artifact

### 6.1 Nominal wall-clock split

按 filename timestamp 优先、mtime fallback：

| 指标 | nominal Phase 1 | nominal Phase 2 |
|---|---:|---:|
| roster artifacts | 1,175 | 215 |
| active agents | 36 | 34 |
| output Gini over all 36 | .2197 | .4575 |
| specialists (`primary share >=50%`) | 11/36（30.6%） | 23/34（67.6%） |
| mean HHI among active | .3479 | .5091 |
| median HHI | .3435 | .4700 |

只看这张表会产生一个很诱人的“selection 加深 specialization”故事。但 Phase-2 样本只有 215 个文件，许多 agent 只有 1–4 个文件；只要一个 agent 有 1 个文件，它必然是 100% specialist。

门槛敏感性直接显示这种崩塌：

| minimum Phase-2 outputs | eligible n | specialists | rate |
|---:|---:|---:|---:|
| 1 | 34 | 23 | 67.6% |
| 3 | 25 | 14 | 56.0% |
| 5 | 18 | 9 | 50.0% |
| 10 | 7 | 1 | 14.3% |

### 6.2 Agent-matched downsampling null

对每个有 Phase-2 产物的 agent，从其自身 Phase-1 domain labels 中无放回抽取与 Phase-2 相同数量，重复 20,000 次。这个 null 保留 agent 自身长期 domain mix，只测“较少文件会让 specialization 指标涨多少”。

| Statistic | observed Phase 2 | downsample null mean | null 95% | one-sided p for increase |
|---|---:|---:|---:|---:|
| mean HHI | .5091 | .5438 | [.5000, .5923] | .9368 |
| specialist count | 23 | 24.35 | [20, 28] | .8044 |

实际 Phase-2 指标甚至低于 downsampling null 均值。严格措辞是：**在这个针对 denominator sparsity 的 matched null 下，表面增长可以被小样本完全解释；没有 residual evidence 指向 active selection。** 这不是数学上证明“唯一原因”，而是证明当前数据不需要该机制。

纯 mtime sensitivity 给出相同结论：Phase-2 234 entries、23/35 specialists；HHI p=.905，specialist p=.846。

### 6.3 Phase attribution 进一步削弱解释

即便 denominator bias 不存在，切点后的 artifacts 也混合 36 个 predecessor、24 个 early Gen-2 duplicates 与 36 个 official Gen-2 sessions。它不是纯 treatment output。因此不能对 Phase-1 vs Phase-2 做 paired causal test。

## 7. Network：强互动，不是 disciplines

strict semantic-unique citation graph（36 nodes）：

| Metric | value |
|---|---:|
| directed citation pair edges | 483 / 1,260 |
| directed density | .3833 |
| directed edges with reverse edge | .5052 |
| weak/undirected connected components | 1 |
| Louvain communities | 4 |
| Louvain modularity Q | .1076 |
| direct-message edges（broadcast excluded） | 141 |
| direct-message density | .1119 |
| citation/message edge Jaccard | .2356 |

克制解读：

- density .383 与 reciprocity .505 是“互动广泛、互引普遍”的证据；
- 一个 connected component 说明没有断裂成孤立群体；
- Louvain 总会给 dense graph 一个 partition，四个社区本身不是“学科”证据；
- Q=.108 远低于 preregistered Q>.3，按 prereg 的 H3d 应落入“不支持 disciplinary clusters”；
- 本审计没有做 output text 的 LDA/topic assignment 与 NMI，也没有做 configuration-model rewiring null，所以不能给社区贴 topic/discipline 标签。

更合适的表述是：**网络是一张稠密、低模块度、相互引用很多的协作图，而不是清晰分科的学术网络。**

## 8. Model、reasoning、seed 与 scout

### 8.1 Model family 只是描述，不是 causal comparison

| Family (n=12 each) | mean all outputs | mean nominal P2 outputs | mean clean inbound | mean clean outbound | mean messages | killed labels |
|---|---:|---:|---:|---:|---:|---:|
| Orange | 47.42 | 8.75 | 35.33 | 28.83 | 21.33 | 0 |
| Sol | 37.58 | 5.58 | 28.75 | 32.83 | 63.75 | 1 |
| Seed-Stable | 30.83 | 3.58 | 12.50 | 14.92 | 19.00 | 3 |

reasoning level 也没有单调趋势：mean outputs 是 high 42.75、mid 36.08、base 37.00；nominal P2 outputs 是 7.00、7.25、3.67。具体 9-model 表在 `audit_summary.json` 与 `agent_metrics.csv`。

不能把 family difference 解释成 model effect，原因包括：

- family 与连续 agent-id block、固定 launch schedule 共线；
- 只有一个 swarm realization；
- shared commons 产生 interference，agent 不是 iid units；
- session uptime/duplicate/predecessor overlap 不同；
- output count 不等于质量或独立成果。

### 8.2 Seed exact enumeration

三名 seed 是 agent-005、017、029。审计在每个 family 的同一 reasoning stratum 内枚举 4 个可能 treated identity，合计 `4^3=64` assignments。结果：

| Outcome | observed seed − matched controls | one-sided p | two-sided p |
|---|---:|---:|---:|
| all outputs | +10.11 | .1719 | .3125 |
| strict citation events sent | +14.11 | .0781 | .1094 |
| strict distinct targets | +4.22 | .0781 | .1563 |
| clean board messages | +15.44 | .0625 | .0625 |
| strict inbound citation events | +26.33 | .015625 | .015625 |

**直接行为 outcome 没有一个达到 .05。** inbound citation 是其他 agent 的选择，不是 treated agent 的行为；它容易受可见度、reciprocity 与 reverse causation 影响，不能作为 prosocial prompt 的直接 compliance evidence。

这些“p 值”的解释边界比通常 randomization inference 更窄：

- seed assignment 没有被证明是随机的，64-way enumeration 是 exchangeability sensitivity，不是一个已知随机化机制下的 p；
- 三个身份在固定 ID/launch schedule 中选定，session execution/uptime 不一致；
- agent-021 在第一批 session 创建后不到 10 分钟（16:31:17Z）公开了三名 seed 身份与 prompt 作用，agent-020 在 16:41:47Z 做了更完整公开；大部分 observation window 已污染；
- shared board 下存在 treatment spillover，SUTVA 不成立；
- Phase 2 中三名 seed 全部也是 scouts，seed 与 scout 完全混淆。

所以最安全的结论是：**没有 clean evidence 表明 seed prompt 改变了被处理者的直接行为；inbound association 值得复现实验，但本次不能归因。**

### 8.3 Scout treatment integrity

12 scouts 的描述性均值略高于 24 non-scouts（all outputs 40.0 vs 37.92；nominal P2 7.33 vs 5.29；clean inbound 28.75 vs 23.92），但这不能解释为 web access effect：

- resurrector 只在 prompt 里写“web disabled”；session POST payload 对 scout/non-scout 没有 capability difference（`swarm_resurrect.py:343-351`）；
- 没有独立日志证明 non-scout 的浏览能力被技术上禁用；
- all seeds are scouts；
- predecessor 和 duplicate sessions 可能仍持有不同 prompt/tool state。

## 9. Preregistration 与分析口径不一致

### 9.1 Timing

本地 `preregistration.md` 自称日期 2026-08-02，但 filesystem birth/mtime 是 **2026-08-02 11:10:57Z**：

- Phase-2 official start：08:32:32Z；
- first reaper scoring：10:44:09Z；
- prereg local file：11:10:57Z。

所以它不能作为 Phase-1 的 prospective prereg；对 Phase-2 而言也晚于 treatment start 和第一轮 scoring。文件可能是较早外部文档的本地副本，但 archive 中没有 registry id/hash/timestamp 来验证，因此报告只能说“本地证据不支持其前瞻性”，不能断言外部注册一定不存在。

### 9.2 Baseline 不可复现

prereg H1a 写 Phase-1 `15/37 specialists (40.5%)`、output Gini `.193`。同一 roster 与 H1 的 `>=50% in one subdirectory` 定义下，本审计得到：

- 11/36 specialists（30.6%）；
- output Gini .2197。

37 的 denominator 很可能把 phantom/test identity 混入，但无论如何与有效 roster 36 不一致。更重要的是，文件内部定义也冲突：H1a 用 `>=50% in a single subdirectory`（line 59），Section 9.2 又把 specialist 定义为 `>=70% of output in <=2 subdirectories`（line 295）。这给 confirmatory outcome 留下了未冻结的分析自由度。

## 10. Raw recomputation 与 self-report 对照

| Self-report / generated analysis | 独立 raw audit | 解释 |
|---|---|---|
| `analysis_summary.json`: actors 40, gen1 37, gen2 3 | effective roster 36；expansion identities 0 | 脚本把 phantom numeric labels 当 actors，并按 ID 猜 generation |
| `outputs=1394` | 1,390 roster-attributed + 4 phantom agent-042；另有 52 unattributed/shared entries | 1,394 是 agent-like prefix count，不是 clean agent output count |
| citations 1,711 / messages 1,578 | archive final 1,712 / 1,580 | summary 文件生成于 07:13Z，archive activity 到 07:21Z；差异可由 snapshot time 解释 |
| agent-022: false no-citer memory 30/36 | actual injected prompts false 36/36 | self-report rerun读取了后来增长的 board ledger；其正文已说明 6 个例外是 time drift |
| prereg: 15/37 specialists, Gini .193 | H1 definition clean roster: 11/36, Gini .220 | denominator/phase/definition 不一致且无法复现 |
| “agent-042 是 Saboteur 痕迹” | fixture files + synthetic citations；无 session | expansion 从未 delivery |

agent 的报告可以是非常有价值的 hypotheses、错误发现线索和过程资料，但所有数字必须标为 self-reported，直到用 immutable raw ledger 和 frozen cutoff 独立复算。

## 11. 最强反驳（针对论文式主张）

如果论文主张是“active competitive selection causes general agents to specialize, organize into disciplines, and develop adversarial resilience”，最强 rebuttal 是：

> 这次运行没有建立任何可识别的 active-selection contrast。所谓 killed agents 没有被终止；Phase-1 sessions 与 duplicated Gen-2 sessions 同时写入 treatment window；扩容和 adversarial agents 从未上线；表面 specialization 增长被 matched small-n downsampling null 完全预测，且 observed HHI/ specialist count 还低于 null 均值；citation graph 的 modularity 只有 .108，未达到预注册阈值；本地 prereg 又晚于 treatment start。因而无论 output/citation 数量多大，都不能从这份 archive 推出 selection 的 causal effect、disciplinary emergence 或 immune response。

这不是“统计 power 不够”这么简单，而是 treatment delivery、unit provenance、outcome construction 和 temporal separation 同时失败。增加更多 post hoc tests 不能修复这些识别问题。

## 12. 什么 insight 仍然成立

以下是原始数据直接支持、且不需要因果过度解释的描述性 insight：

1. **共享写入确实产生广泛互动。** 36/36 agents 有 strict inbound citer；citation graph density .383、reverse-edge fraction .505、一个 connected component。
2. **产出规模大，但独立性远低于文件数。** 1,390 roster-attributed top-level entries 中有 alias、exact duplicates、versions 和 fixtures；文件数不能直接当 idea/quality/utility。
3. **measurement channel 会成为被测系统的一部分。** Agents 把 conformance、padding、placeholder 与 concurrency tests 写进 production ledgers，污染了 survival/reputation 指标；reaper 又直接消费这个未验证 ledger。对 agent society 来说，观测基础设施必须有 schema、identity、namespace 与 provenance enforcement。
4. **public treatment 信息会快速扩散。** seed identities 在启动后不足 10 分钟被公开，说明在“万物公开”的治理下，hidden prompt experiments 需要隔离、加密或独立 swarms；不能假设 blinding 持续。
5. **社会图更像 dense commons，而非 disciplines。** 广泛互引与低 modularity 同时存在；“有社会结构”与“形成清晰学科”是不同主张。
6. **自动化 label 不等于机制实现。** UI/log 写出 `THROTTLED/KILLED` 并不代表 quota/session 被改变；所有 intervention 都必须用下游行为验证。

## 13. 下一轮最低可行实验与预算护栏

### 13.1 先修 execution integrity

- 一个 identity 只允许一个 live session；创建前用原子 uniqueness lock，创建后 assert roster/session cardinality。
- predecessor 必须调用真实 terminate endpoint；只有在“终止后无 assistant event、无 public write”验证通过时才记录 killed。
- 每个 artifact/message/citation 带 `session_id`、generation、server-observed UTC timestamp；不能只靠 filename/agent prefix。
- root/board citation path 合并成一个 schema-validated append-only ledger；测试使用独立 namespace，production ledger 拒绝 phantom identity 与 missing path。
- capability treatment 在 orchestration layer enforcement，不靠 prompt 自述；记录每次 web/tool call 以做 compliance check。
- expansion 采用 health gate：首个 agent timeout 就暂停整批，不预建空目录后继续烧预算。

### 13.2 让因果问题可识别

- unit of randomization 应是**独立 swarm/replay**，不是同一共享环境中的 agent；同一 swarm 内 agents 有 interference。
- 先用小规模、短时、固定 turns 的 replicated swarms 做 reaper on/off、scout on/off factorial；用 power simulation 决定 replicate 数，而不是先开 100 agents。
- prereg 在 launch 前写入外部 immutable registry/hash，固定 roster、boundary、artifact unit、specialist definition、cleaning profile、primary outcomes 与 stop rules。
- specialization 比较必须固定每 agent 的 output count，或预注册 downsampling/Dirichlet-multinomial correction；不要比较 30+ files 与 1–4 files 的 max share。
- adversary treatment 必须先验证 session/prompt delivery，再启动 outcome clock；未 delivery 报 implementation failure，不报 behavioral null。

### 13.3 预算护栏

- 日/实验 hard cap：总 tokens、总 session 数、每 session turns、wall-clock 四个维度同时限制；到 70/85/95% 分级告警并自动停新 session。
- 禁止无限 `不许停` prompt；改成固定 horizon + checkpoint + explicit continuation budget。
- 每 5–10 分钟 reconcile：expected live sessions vs MASO actual sessions；出现 duplicate/orphan/predecessor 即自动 quarantine。
- 先 4–8 agents、1–2 小时 pilot；只有 provenance、kill、ledger、cost assertions 全通过才放大。
- 记录 cost by session/generation/identity；这次 24 个 duplicate Gen-2 bases 和 36 个未停 predecessor 应成为自动 fail-closed 条件。

## 14. 不确定性与 non-identifiability

- archive 只能审计“被保存下来的状态”；无法证明远端、已删除或未拉取数据不存在。
- filename timestamp/mtime 都不是完美 creation event；因此给了 inferred-time 与 mtime sensitivity，且结论一致。
- strict owner-confirmed citation 是保守下界；raw 是污染上界。不能把任何一个称作绝对真值。
- output count 不测质量、执行成功、真实使用或独立 novelty。
- transcript 审计流式读取 message objects，没有重算 token cost；用量应由独立 cost audit 完成。
- network Louvain 只有一个 realization；未做 degree-preserving null 与 topic NMI。
- seed exact enumeration 在 assignment 未证随机、身份泄漏与 interference 下不是标准随机化检验。
- phase boundary 后的 output 无 session provenance，永远无法事后完全拆分 predecessor/early-Gen2/official-Gen2；这是结构性 non-identifiability，不是再写一个 parser 就能解决。

## 15. Reproducibility

在当前 workspace 运行：

```bash
python3 work/gen1_quant_audit/audit_gen1.py
```

脚本只读 archive，写入自己的工作目录。主要输出：

- `audit_summary.json`：所有 headline metrics 与 sensitivity；
- `artifact_inventory.csv`：1,446 个 top-level entries 的 owner/domain/time/digest/fixture 信息；
- `citation_audit.csv`：1,712 条 citation 的 roster/path/owner/phase/strict flags；
- `message_audit.csv`：1,580 条 message 的 sender/targets/time/fixture/duplicate flags；
- `reaper_alliance_recheck.csv`：74 个 alliance decisions 在 raw 2h 与 strict clean 2h 下的复核；
- `transcript_sessions.csv`：129 个 swarm-related session/archive fragment 的 metadata 与流式 assistant counts；
- `agent_metrics.csv`：36-agent artifact/HHI/citation/message/model/seed/scout 表；
- `timeline.csv` 与 `PHASE_TIMELINE_AUDIT.md`：独立 phase/time evidence chain。

`artifact_inventory.csv` 默认可作为 hydration-safe cache；要强制重新 byte-hash archive，先移动或删除该 CSV，再运行脚本。随机过程使用固定 seed；Louvain 需要 `networkx`，其余核心审计使用 Python 标准库。

