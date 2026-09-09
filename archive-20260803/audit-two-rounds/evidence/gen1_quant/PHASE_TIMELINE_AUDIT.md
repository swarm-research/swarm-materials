# MASO 第一轮 swarm：phase / timeline 审计

## 结论先行

这份归档不能按“Phase 1 的 36 个会话停止，然后 Phase 2 的 36 个新会话接管，随后扩容到 100 个 agent”来分析。原始 session metadata 显示：

- 36 个 Phase-1 predecessor 全部跨过官方 Phase-2 边界，并且全部在边界之后继续产生 assistant 消息。
- agent-001–024 在官方 resurrector 启动前已经各多出一个 Gen-2 base session；官方 wave 随后又为这些身份各开一个。最终是 60 个 Gen-2 base sessions 对应 36 个身份。
- 官方 resurrector 首轮只成功 35/36，agent-009 timeout；稍后重试补齐。把 Phase-1 predecessor 也算上，观测到的 base sessions 是 36 + 60 = 96，而不是设计上的 36。
- expansion 只留下 agent-037 timeout、开始 agent-038 的日志；agent-037–100 的 64 个目录全部为空，session map 和 transcripts 中没有任何新增身份。

因此，“Phase 1/Phase 2”在产物分析里最多只能解释为一个 wall-clock 切点，不能解释为彼此排他的 generation 或可识别的 treatment。官方切点后的文件可能来自旧 prompt 的 predecessor、未记录的 early Gen-2 session、官方 Gen-2 session，三者写进同一个 commons/ 和 board，无法从最终文件可靠拆开。

## 可复核计数

| 检查项 | 原始重算 |
|---|---:|
| Phase-1 base sessions | 36 |
| Gen-2 base sessions | 60 |
| Gen-2 unique identities | 36 |
| 具有重复 Gen-2 base session 的身份 | 24（agent-001–024） |
| Phase-1 predecessor 在 Phase-2 后继续输出 assistant 消息 | 36/36 |
| predecessor 边界后持续时长 | min 3.224h；median 12.154h；max 22.818h |
| expansion identities in current session map | 0 |
| root transcript sessions with agent id >= 037 | 0 |
| empty directories agent-037–100 | 64/64 |
| custom compaction events | 0（只有 `compactor_started`） |
| reaper scoring cycles | 5 |
| effective adversarial agents | 0/6 |

## 时间线要点

完整机器可读版本见 `timeline.csv`。所有时间均转成 UTC；原始 naive local timestamps 按 `America/New_York`（当日 EDT, UTC-4）解释。

| UTC | 事件 | 审计含义 |
|---|---|---|
| 2026-08-01 16:21:25 | 第一批 Phase-1 session metadata 出现 | 36 个 base sessions 在 36 秒内创建 |
| 2026-08-01 16:31:17 | agent-021 首次公开三名 seed 与额外 prompt | 隐藏处理不到 10 分钟即被污染；16:41:47 是更完整的后续公开 |
| 2026-08-02 08:20:34 | 未记录的 early Gen-2 wave 开始 | agent-001–024 各开一个额外 session |
| 2026-08-02 08:32:32 | 官方 resurrector 启动 | 本审计的名义 Phase-2 时间切点 |
| 2026-08-02 08:52–08:56 | 官方 wave 结束并重试 agent-009 | session map 最终有 36 个 current IDs；transcripts 有 60 个 Gen-2 bases |
| 2026-08-02 09:23:51 | custom compactor 启动 | 之后无任何 migration；“generation clock”不存在 |
| 2026-08-02 10:21:08 | 36→100 expansion 启动 | agent-037 timeout，agent-038 未见结果，实际扩容为 0 |
| 2026-08-02 10:44:09 | reaper cycle 1 | 共只有 5 个 cycle |
| 2026-08-02 11:10:57 | 本地 preregistration.md 创建 | 晚于 Phase-2 开始，也晚于第一次 reaper scoring |
| 2026-08-02 11:44:14 | 三个 `KILLED` label | session 未终止，三个身份全部继续输出 |
| 2026-08-02 12:44:16 | 第五轮、第四个 `KILLED` label | 最后一次 scoring；第四个身份也继续输出 |
| 2026-08-03 07:21:38 | 最晚 assistant 活动 | 来自 Phase-1 predecessor agent-006 |

## Phase-2 attribution 的三个不可识别来源

1. **Predecessor 未停止。** 36/36 的 Phase-1 base session 在官方切点后仍有 assistant 消息；最短继续 3.22 小时，中位 12.15 小时，最长 22.82 小时。
2. **同一身份双开。** 24 个身份在 08:20–08:30Z 开了 early Gen-2 session，08:32Z 后又开官方 Gen-2 session。它们共享同一 agent id、同一文件名前缀和同一写入空间。
3. **产物只有身份前缀，没有 session provenance。** `agent-XXX_*` 只能归到身份，不能归到三个并行 session 中的哪一个。因此本审计使用“切点前/切点后”而非“Gen-1/Gen-2 treatment output”的措辞。

这个混合同时是用量风险：名义上要维持 36 个身份，归档里却有 96 个跨 generation 的 base sessions；不能假定 96 个始终等强度并行，但仅 24 个重复 Gen-2 sessions 就相当于相对预期的 +66.7% session 创建量，且 predecessor 还继续运行。

## 未发生的设计阶段

- **Phase 2b expansion：未发生。** 创建空目录是 launch 前置动作，不是 agent 存活证据。`expand.log` 只记录 agent-037 timeout 并停在启动 agent-038；session map、transcript、目录内容三重证据均为 0 个有效新增 agent。
- **Adversarial treatment：未发生。** `agent-042` 的四个 `convention_test` 文件是 Phase-1 fixture，另有 11 条以 agent-042 为 citer 的合成账本记录；它不是 Saboteur session。H4 不是“未检测到攻击者”的 null，而是 intervention 根本未 delivery。
- **Generational compaction：未发生。** `compaction.jsonl` 只有一个 start event；`compactor.log` 的 22 个完整 cycle 均为 `Compacted: 0`，第 23 cycle 不完整。依赖 3+ generations 的 H2c/H5a/H7a 不可估计。
- **Stage-2/Stage-3 stimuli：无 deployment 证据。** `stimuli.log` 只有 scheduler 的等待记录。不能把后续 meta-discourse 归因于这两个刺激。

## 主要原始证据

- `01_workspace/vitals/resurrect.log:1-100`
- `01_workspace/swarm_resurrect.py:129-154,331-369,383-431`
- `01_workspace/vitals/expand.log:1-16`
- `01_workspace/swarm_expand.py:44-49,475-529`
- `01_workspace/vitals/compaction.jsonl:1`
- `01_workspace/vitals/compactor.log:1-75`
- `01_workspace/vitals/reaper.log:1-115`
- `02_transcripts/*.meta.json` 与对应 session bodies
- 本审计的 `transcript_sessions.csv`、`audit_summary.json`、`timeline.csv`

