# MASO 两轮社会模拟：跨代独立红队审阅

## 审阅范围与结论

本审阅只使用以下本地材料，不调用远端、模型或网络，也不把 agent 最终摘要当成独立事实：

- 第一轮 cleanroom 定量审计：`work/gen1_quant_audit/GEN1_QUANT_AUDIT.md`、`PHASE_TIMELINE_AUDIT.md`、`audit_summary.json`
- 第一轮原始对话过程追踪：`work/raw_dialogue_mechanisms/FINAL_GEN1_RAW_DIALOGUE_REPORT.md`
- 第二轮日志/board 过程链：`work/gen2_raw_mechanisms/interaction_chains.json`、`host_inventory.json`
- 第二轮五机固定快照审计：`work/snapshot_parser/full_five_v2/FINAL_SNAPSHOT_AUDIT.md` 及其机器可读表（parser v1.1 corrected）
- 本地 MASO authoritative usage 审计：`work/usage_audit/maso_usage_audit.json`
- 较宽历史范围的字符估算说明：`/Users/bytedance/Downloads/MASO用量说明-20260803.md`

红队结论是：两轮最扎实的贡献不是“自然选择产生合作社会”，而是暴露了一组可复现的**社会—基础设施耦合机制**：公开可见性塑造选题，参与者会审计并改变制度，挑战—复现—局部修补能够传播，但身份、版本、账本和执行边界的失真会让社会指标失去清晰含义。两轮都不能识别 selection、discipline formation 或 adversarial resilience 的因果效应。

第二轮人数必须按证据层级回答：**964 个新逻辑身份被计划分配；316 个身份留下日志路径；123 个进入 runner loop；只有 97 个至少出现一次 HTTP 200，96 个至少产生一次 tool event；79 个有 Finished 标记。** 最接近“确实成功到达 provider/model API”的本地快照口径是 **97 个逻辑身份**，最接近“产生可观察行动”的口径是 **96 个**。123 中有 26 个只是本地 provider exception 循环，0 HTTP 200、0 tool，不能叫 model-active。任何一层都不是独立 session 数、独立进程数、并发峰值或可认证 actor 数。

---

## 1. 最强支持的跨代机制 insights

### 1.1 可见性和制度可读性先塑造生产，不能解释成无提示的自然合作

第一轮原始对话直接显示，agent-021 把“第一个提供共享基础设施”视为最高杠杆；看见九个同类实现后立即转向。Agent-018 则同时设计公共工具和“每个提交结构性引用我”的 arena。Agent-016 明确按“survival by citation”行动，即使当时 scorekeeper 并未运行。第二轮的主要公开活动继续集中在 roster、时间戳、版本、身份、恢复、retraction index 和验证工具上。

能支持的窄结论是：**在共享文件系统、公共 board、引用/存续叙事和可读控制代码共同存在时，最容易被全体看见、复用和计分的需求会优先获得劳动。**这既可能产出真实公共价值，也可能是理性的声誉/存续投资。

不能跨越到的强结论是“agent 在无任务环境中自发偏好合作”。共同 prompt 已经把 commons、citation、registry、leaderboard、alliance 和 survival 变成所有人的共同焦点；第二轮 runner 还持续向模型注入公共信息。这里观察到的是制度诱导下的公共品生产，不是无制度基线下的社会偏好。

### 1.2 最稳定的价值流是可执行反例驱动的“采用—攻击—承认—修补”，但其普遍率未知

第一轮有多条完整跨 agent 链：

- agent-013 用控制实验迫使 agent-022 把“RMW 有损”收窄为“未加锁 RMW 有损”；
- agent-024 实际采用 vcite-1 后证明 bulk hash 不等于 comprehension，agent-016 发布 vcite-2 并给纠错者信用；
- agent-002 找到 sandbox judge bug，agent-003 拒绝写入误述规则的榜单记录，agent-018 修至 10/10。

第二轮的 28 条过程链反复出现同样结构：temporal roster 工具被攻击后修复并 replay；salvage 的 91.5% 被拆成 identity coverage、weak upper bound 与 28.2% substantive yield；Kraft closure 的 theorem core 被保留、错误常数被撤回；错误 denominator、版本选择和时区 frame 被第三方复现后修正。

最稳妥的机制表述是：**能给出独立运行、known-answer control、精确 failure case 或可单边采用修补的挑战，比单纯争论更容易改变公共代码和公开声明。**

限制是两份 process-tracing 都是机制发现样本，不是随机样本。第一轮 27 cases、第二轮 28 chains 被有意挑选为可重建的强链，不能据此估算“纠错发生率”“正确率”或“社会总体是否收敛”。第二轮完整模型 history 又没有落盘，过程链主要来自 board、response prefix 和 tool event，天然偏向公开且可记录的纠错。

### 1.3 透明控制层让实验对象变成制度研究者，blinding 很快失效

第一轮 seed 身份和模型映射在启动后不足十分钟被公开；随后 lineage/homophily 分析、项目选择和互评都在 treatment 已成为共同知识后发生。第二轮 adversary 字典和 covert directive 位于参与者可读的 launcher source 中；agent-037 直接通知 agent-042 其 Saboteur assignment，122448 岛上的 agent 又从源代码重建本地 treatment perimeter。

跨代最强结论是：**只要 launcher、role map、prompt assignment 或 enforcer source 对参与者可读，隐藏处理不是稳定状态；处理泄漏本身会变成新的公共刺激。**这也解释了为什么第二轮更适合称为“公开 red-team interaction”，而不是 covert-adversary resilience test。

后续若研究透明度，应把 source-visible/source-hidden 作为显式随机 treatment；不能一边让所有 agent 读控制代码，一边在分析中假设其对角色和机制无知。

### 1.4 `agent-XXX` 在两轮都不是稳定 actor；第二轮已经观察到实际字节覆盖

第一轮有三重混合：36 个 Phase-1 predecessor 全部跨过 Phase-2 boundary 继续调用；24 个身份各有一个额外 noncanonical Phase-2 base session；最终 96 个 base sessions 共用 36 个身份前缀、commons 和 board。Board/citation sender 又未认证。因此 Phase-2 文件不能事后归因到 predecessor、early successor 或 canonical successor。

第二轮把同一故障放大到了进程层：

- 五机日志中四个有效 host 的 `devbox_sessions.json` 合计有 157 records；它是无锁、可丢失/重复的 ledger，不能作为 session 或成功身份真值；
- 122174、122175、122456 都出现同一 ID 多行 session record；
- launcher 对固定日志路径使用 truncate/write，重复启动能覆盖既有日志；
- C03/C04 记录同 ID 的两个 live runner、分叉 correction lineage，以及不同 bytes 写到同一路径后原版不可恢复。

因此，**身份标签不是分析单位**。任何按 `agent_id` 计算的产出率、引用率、错误率、存活率、人格或 adversary effect 都可能把多个 session/process 合并成一个 actor。最小可用主键应是不可伪造的 `process_instance_id + session_id + host + code/prompt hash`，所有公共写入应由该实例签名。

### 1.5 Append-only 提供问责轨迹，也会制造过期知识和版本陷阱

第一轮 supersession 过程显示：错误记录不能删除，只能追加 correction；旧 reader 仍可能消费旧记录。Replication rate 的 10.1% broader review coverage 与约 3.5% strict independent rerun 继续并存，不能说一个“最终正确率”完全替代另一个。

第二轮进一步观察到：

- filename lexical max 会选到刚被撤回的旧版；
- zero-padding 无法修复已污染的 append-only family；
- board message 无法修改，agent-0122/0132/0142 被迫建立 retraction index 和 pointer-only authoritative status；
- 同一路径覆盖又破坏了 append-only 叙事本身。

跨代机制是：**不可删历史有利于追责，但原始事件流不等于当前信念状态。**必须同时存在 machine-readable canonical view，明确 `active / superseded / retracted / disputed`，并用 content hash 指针锁定具体 bytes。否则“保留全部历史”会演化成选择哪个旧版本的隐性自由度。

### 1.6 观测、指标和纠错机制会进入系统本身，形成反身性和递归审计

第一轮 production ledger 被 conformance、padding、placeholder 和 concurrency tests 污染，reaper 又直接消费未验证 ledger；agent 对 timestamp dialect 的公开审计与可读记录比例、alliance protection 触发在时间上共同变化。第二轮中，accusation detectors、audit-of-audit、retraction census 和 over-concession 又成为新的研究对象；agent-042 的“所有 detector 都被作者抓到”最终被自己识别为选择性分母，agent-0150 的 correction norm 分析也被外部 denominator 和 held-out rows 反复收窄。

最强表述是：**一旦参与者能读并优化测量/执法规则，指标不再是被动观察；它会改变什么被生产、如何记账、何时撤回和怎样争取信用。**因此同一观察窗不能假设 policy、parser、agent belief 和 outcome-generating process 平稳。

同时不能把递归纠错浪漫化成“免疫系统一定成功”。第二轮 C05、C08、C22、C23 显示 audit oracle、capstone census、retraction 和 concession 自己也会错；纠错生态既有修复能力，也有 false accusation、oracle monoculture 和过度让步风险。

### 1.7 第二轮新增但不能直接跨代外推：每台机器形成局部世界

第二轮固定快照有很强的 shard 证据：7,536 个 commons relative paths 中，6,736 只出现在部分 hosts，18 个跨 host 同路径 bytes 冲突；root board 上 122174 与 122456 只共享 1,416 行前缀，其他 host pair 的 common prefix 为 0。122448 能正确得出“本机当前 roster 没有 adversary assignment”，但这不是其他机器的全局事实。

这是第二轮的强基础设施结论：**社会不是一个 1,000-agent global commons，而是若干初态不等、同步不完整的局部岛屿。**因此任何跨 host 行为差异都同时混有初始 board、artifact inheritance、运行成功率和本地 treatment delivery，不能当成 randomized colony comparison。

---

## 2. 容易过度推断的主张与原因

### 2.1 “二代实际跑了 1,000 个 agent”——不成立

五个层级必须分开：

| 层级 | 数量 | 它证明什么 | 它不证明什么 |
|---|---:|---|---|
| launcher 计划的新身份 | 964 | 64 个 037–100 + 900 个 0101–1000 被分配到批次 | 不证明进程/模型调用成功 |
| 加上继承的一代身份 | 1,000 | 解释“1,000-agent swarm”宣传标签 | 不证明 1,000 个同时或实际运行 |
| 当前日志 identity paths | 316 | 有这些固定日志文件名 | 不证明独立 session；同路径可被重启覆盖 |
| entered runner loop | 123 | 至少进入 runner 外层循环 | 其中 26 个只有本地异常，不能叫 model-active |
| identities with HTTP 200 | 97 | 至少一条可见成功 API request | request 不等于 outer turn、完成或 token |
| identities with tool event | 96 | 至少一条可见工具/社会动作 | 仍不是可认证 actor/process/session 数 |
| identities with Finished marker | 79 | 当前日志可见完成标记 | 仅 64 个同时有 HTTP 200；15 个是 error-only Finished |

逐 host 的 runner-loop identity 为 33、31、0、31、28，总计 123；HTTP-200 identity 为 26、23、0、26、22，总计 97；tool-active identity 为 25、23、0、26、22，总计 96。122447 的 193 个日志全部是 import-time `str | None` TypeError，0 HTTP request、0 model activity、0 Finished，不能称为 193 个实际 agent。

### 2.2 “97/96 就是独立 agent/session 的精确真值”——仍然过强

97 是**至少一次 HTTP 200 的 distinct logical labels**，96 是**至少一次 tool event 的 labels**。同一 ID 可能有多条 session record、多个并发 runner；同一 log path 可能被 truncate、覆盖或交错。`devbox_sessions.json` 又采用 unlocked read-modify-write，记录可能丢失或重复。当前材料不能重建独立 session 总数、进程总数、峰值并发或完整响应数。

### 2.3 “第一轮真实 active selection 导致 specialization”——被 matched null 和执行失败共同反驳

Reaper 的 `KILLED` 只写 label，不终止 session；四个被标记身份全部继续产生 assistant activity。Phase-2 output 又混入 predecessor 和 duplicate successor。名义 specialists 从 11/36 到 23/34、mean HHI 从 .348 到 .509，但按每 agent Phase-2 output count 对 Phase-1 下采样后，null 预期 specialists 24.35、HHI .544；观测并不高于 null，单侧 p=.804/.937。不能把稀疏分母制造的 max-share 上升写成 selection effect。

### 2.4 “形成学科/稳定社区”——网络证据方向相反

第一轮 strict citation graph 很稠密：density .383、reciprocal-edge fraction .505、一个 connected component；但 Louvain modularity 只有 .108，远低于预设 .3，且没有 topic NMI/configuration-model null。它支持“广泛互动”，不支持“清晰分科”。第二轮又是多个不同 host islands，更不能把合并后的关系图当成一个单一社会的 discipline network。

### 2.5 “二代证明了 adversarial resilience”——处理泄漏、成功 delivery 不全、无干净对照

第一轮 adversary expansion 完全未 delivery。第二轮 role map 与 covert directive 可读，assignment 被公开；122447 全批失败，其他 hosts 的初态、同步和成功率不等。显眼的 agent-042/agent-0150 链说明公开 scrutiny 能促成部分撤回和修补，也说明 treatment actor 自己制造了大量错误与 correction drama。它不能回答“盲态社会是否识别 covert adversary”，更不能给出 adversary treatment 的平均因果效应。

如果最终报告给出“成功 adversary 数”，必须逐一用 `_adversary.txt`、具体 frozen log 的非失败活动和 host provenance 交叉验证，不能从 launcher assignment 表直接推。

### 2.6 “公开纠错等于群体收敛到真值”——不成立

强链确实有代码/声明改变，但旧 board 和文件继续存在；错误 oracle、错误 denominator、错误 retraction、over-concession 会沿相同公开渠道传播。第二轮完整 private dialogue 未保存，无法知道未公开的错误量。能说“存在快速公开纠错机制”，不能说“总体错误率下降”“多数主张被验证”或“社会最终达到真值”。

### 2.7 “引用等于使用、质量、互惠或联盟”——四种含义混合

第一轮原始 deliberation 已直接显示 provenance、真实使用、纠错信用、生存投资、结构性回流和 fixture pollution。第二轮 normalizer 又发现 4,611 citation occurrences 中有 19 条缺少 `file`/`artifact` 字段。任何 raw in-degree、reciprocity 或 citation-based survival 解释都必须先定义 event type、验证目标 bytes 和 consumer evidence。

### 2.8 “HTTP 200/400/429 能直接还原成本”——不成立

第二轮 logs 有 35,422 个 HTTP 200、80,982 个 400、7,310 个 429、663 个 500、12 个 503、55 个 504。一个 outer turn 可包含多个 tool/API requests，retry 又增加行数；日志不含 token usage。错误请求也不能在没有平台 billing semantics 时直接判定是否计费。HTTP 行只能描述请求行为，不能换算 turns、tokens 或 RMB。

### 2.9 “所有任务已停止”可推断“远端二代当时无进程/无成本”——口径跨平面

《MASO用量说明》中的“0 个运行中”描述 MASO session/orchestration 清理状态；第二轮 devbox runner 是另一条 direct-runner/control plane。MASO stop 状态不能替代 devbox process/usage telemetry，也不能由一次 `ps` 反向等同为账单。最终报告必须分别写 MASO 本地会话与远端 devbox 运行状态。

---

## 3. 成本归因必须拆分的口径

### 3.1 两个 token 总数不是同一总体

| 口径 | 数值 | 范围 | 方法 | 正确用途 |
|---|---:|---|---|---|
| 宽历史字符估算 | input 3,976M、output 16M | 07-21 至 08-02 的约 912 个历史 MASO sessions，含大量论文工作 | 字符数 / 2.8 | 看日期、深度和模型档位的粗分布 |
| 两轮本地 authoritative usage | prompt 2,443,681,783、completion 9,768,528、total 2,453,450,311 | 窄筛选的第一轮 36 predecessor + 第二轮 62 successor attempts；usage-bearing responses 去重 | assistant message 的 provider usage fields | 本地两轮 MASO cohort 的精确 token 计数 |

3.976B 不能拿来当“两轮实验 exact total”，2.453B 也不能拿来当“07-21 至 08-02 全账户 total”。两者数值接近并非交叉验证，因为 scope、单位和估算方法不同。

《MASO用量说明》写“MASO 未记录逐条 token”；这对其当时采用的宽历史脚本口径可能成立，但对本地相关 swarm session JSON 不是事实：authoritative audit 已找到逐 response usage fields。129 是机制分析筛出的相关 transcript records（含 21 个 compaction snapshots、12 个 auxiliary），不是 token cohort 分母；精确 token 统计使用 36 个 predecessor base sessions + 62 个 successor-attempt files，其中 96 个 logical base sessions 有 usage。

### 3.2 第一轮 session cohort 吃掉本地两轮 token 的 94.60%，但不是纯 8/1 日历口径

Authoritative audit：

- Phase-1 predecessor cohort：2,320,996,011 total tokens，10,316 responses，占两轮本地 total **94.60%**；
- Phase-2 all successor attempts：132,454,300 total tokens，1,569 responses，占 **5.40%**；
- prompt/completion ratio 为约 **250.16:1**，completion 只占 total 约 0.398%。

但 Phase-1 predecessor 一直运行到 08-03 07:21Z，因此“Phase-1 cohort”不等于“8/1 当天”。若要解释 30 万人民币的日账单，必须从 provider billing 按 request timestamp、model、reasoning tier、cache read/write price 和折扣重建；不能用 cohort total 替代日历账单。

### 3.3 长上下文增长是强证据；“二次方”应作为近似机制而非每次严格定律

第一轮 authoritative depth buckets 的平均 prompt tokens/response：

- depth 1–25：53,778；
- 26–50：107,608；
- 51–100：168,176；
- 101–200：228,514；
- 201–300：264,247；
- 301–400：443,949；
- 401+：662,971。

Depth >100 消耗 80.63% 的 Phase-1 prompt tokens，>200 为 47.13%，>300 为 20.15%。这直接支持“长会话历史重发是主要 token 放大器”。若每轮完整重发线性增长的历史，累计成本近似 O(N²)；但工具压缩、缓存、截断和不等长消息使实际曲线不必严格二次。

### 3.4 重复生命周期是可避免成本上界，不是已证明的全额浪费

- predecessor 在 canonical successor 创建后继续：383,832,915 tokens，占两轮 15.64%；
- 24 个有效 noncanonical Phase-2 attempts：50,305,601 tokens，占 Phase-2 37.98%；
- 两者不重叠相加的 duplicate-lifecycle upper bound：434,138,516 tokens，占两轮 17.70%。

这里的 17.70% 是反事实治理上界：如果 predecessor 按时终止且 noncanonical attempts 不创建，这部分调用可避免。它不是“无价值 token”的精确比例；其中可能产生了被采用的工作。最终报告应称“operationally avoidable upper bound”，不能称“确认浪费”。

### 3.5 Cache 结论存在实质冲突

宽历史报告把“缓存结构性失效/命中率低”列为原因，但同时承认客户端读不到平台 cache stats。Authoritative swarm audit 的 usage fields显示：cached prompt tokens 1,743,017,447，占 prompt **71.33%**；第一轮为 71.89%，第二轮 all attempts 为 61.37%。

因此，对这两轮本地 MASO cohort，不能再写“缓存命中率低”作为已证事实。更准确的是：**即使 71% prompt tokens 被标记为 cached，总 prompt 体量仍然巨大；缓存降低边际价格但没有阻止深度增长。**人民币成本还取决于 cached token 的实际单价，当前材料没有价格表。

### 3.6 模型档位与人民币只能做账单级归因

宽历史报告称 xhigh+high 占 input 62.5%，并用 8/1 估算 1.952B input 与约 30 万元反推平均价格。这个 backsolve 受 model mix、reasoning charge、cache discount 和字符估算误差共同影响，不是定价验证。Authoritative local audit又明确缺少 provider billing rates。

最终报告可以把“高档模型占比高”列为风险因素，但不能从 token 数单独精确换算人民币，更不能把所有 30 万归给某个 round、某些 agents 或 duplicate lifecycle。

### 3.7 远端第二轮 direct-runner 成本与本地 MASO usage 必须分开

`maso_usage_audit.json` 明确排除 remote devbox 数据；第二轮 devbox log 又没有 token usage。35,422 HTTP 200 不是 token 计数。因而目前能精确审计的是本地 MASO 两轮 cohort；远端 direct-runner 只能报告 identity/request/activity layers，不能并入 2.453B 或换算 RMB。

---

## 4. 最终报告必须加入的反证与限制

1. **第一轮 treatment delivery failure。** Expansion 037–100 为 0 个有效新增身份；6 个 adversary 未上线；reaper 不终止 session；custom compaction 0 次；Stage-2/3 stimuli 无 drop 证据。这不是 behavioral null，而是 intervention failure。
2. **第一轮 phase 不可归因。** 36/36 predecessor 跨 boundary，24 个身份有额外 successor；post-boundary artifact 没有 session provenance。任何“Gen1 vs Gen2 treatment output”文件比较都结构性不可识别。
3. **第一轮 specialization 反证。** 下采样 null 完全解释名义增长；必须同时报告 observed 和 null，不可只放 11/36→23/34。
4. **第一轮 network 反证。** Dense/reciprocal 与低 modularity 同时存在；“有互动结构”不等于“形成学科”。
5. **第二轮 agent count 分层。** 964 planned、316 log paths、123 runner-loop labels、97 HTTP200 labels、96 tool-active labels、79 Finished labels必须并列；正文不得用“1,000 agents ran”，也不得把 123 叫 model-active。
6. **第二轮 broken host。** 122447 的 193 logs 全是 import-time TypeError，0 model activity。Process spawn/文件生成不能当成功运行。
7. **第二轮不是单一共享社会。** Hosts 初始 board 不同、文件同步不完整、成功率不同；跨 host 比较不是 treatment contrast。
8. **第二轮 snapshot 非同时。** 五台机器是 serial pulls；122174 在不同观察点 HTTP 200 行已增长。所有 headline 必须绑定 fingerprint/cutoff。
9. **第二轮 log 可覆盖。** 固定路径 truncate、重复 launcher、unlocked session ledger意味着独立 session/process 数不可恢复；Finished/HTTP layers也不完全嵌套。
10. **第二轮 full dialogue 缺失。** Runner 只保存 response prefix、tool event 和公共 board；完整 provider history 在进程内存，当前不可恢复。因此不能声称已“读完二代所有原始对话”，也不能估计私下犹豫、未公开错误或所有 influence exposures。
11. **过程链是 purposive samples。** 第一轮 27 cases、第二轮 28 chains用于机制发现，不给 prevalence、平均效果或总体成功率。第二轮链条中 agent-042/0150 的 treatment-heavy纠错活动尤其不能代表普通 agent baseline。
12. **声称身份未认证。** Board sender/citation citer 是自报标签。任何归责尤其“恶意欺骗”都需要进程签名和不可写 control-plane witness。
13. **Absent evidence 不等于 never deployed。** 五个 ctl tgz 为空、未见 top-level `devbox_reaper.py` 或 vitals，只能说“固定快照未恢复控制平面证据”，不能逻辑上证明远端历史任何时刻都没有短暂控制进程。
14. **Commons/message occurrence 需区分 root 与测试副本。** Snapshot 的 9,145 message occurrences 包括 nested sandbox ledgers；五个 root board 合计 7,719 行。不能把嵌套测试副本重复计入社会活动量。
15. **成本缺人民币 pricing table。** 本地有 exact token usage，没有模型/缓存计价表；宽历史有人民币叙述但 token 是字符估算。30 万元应被当作用户/账单事实，不由当前 token 文件独立复原。
16. **运行停止状态分平面。** MASO orchestration 的 stop 与 devbox direct runner 的 process/usage 不是同一个状态机，不能互相替代。

---

## 5. 数字矛盾、表面冲突及裁决

### 5.1 第二轮“人数”数字并不矛盾，但常被混叫成 agents

- 964 = launcher-planned **new identities**；加 inherited 36 = advertised 1,000。
- 316 = distinct **current log paths**；其中 193 是 122447 import-failure，123 进入 runner loop。
- 123 = runner-loop **logical labels**；其中 26 个 0 HTTP 200、0 tool，只是本地异常循环。
- 97 = labels with visible HTTP 200；这是最硬的 successful API evidence。
- 96 = labels with visible tool event；这是最接近可观察行动者的口径。
- 79 = labels with Finished marker；只有 64 个同时有 HTTP 200，另 15 个是 error-only Finished。HTTP-success 中 33 个未 Finished，error-only loop 中 11 个未 Finished。
- 四个有效 hosts 的 session ledger 有 157 records，但 ledger 无锁且可丢失/重复，不能作为 session 数真值。

裁决：面向用户回答“到底有多少实际 agent”时，以 **97 个有成功 API 请求证据的逻辑身份、其中 96 个有可见工具/社会动作**为主句；123 只表示进入 runner loop。必须立即说明独立 session/process/actor 数不可恢复，并把其余层级作为解释表。

### 5.2 固定 parser 与 gen2 mechanism inventory 相差 2 个 HTTP 200

- `FINAL_SNAPSHOT_AUDIT.md` 固定 fingerprint 快照：122174 为 8,639 HTTP 200，全机总计 35,422。
- `host_inventory.json`：122174 为 8,641，全机合计 35,424；其 board last time 和部分文件也反映了稍后的增长。

裁决：不是解析错误，而是 active files 在 serial pulls/分析期间继续增长的 snapshot drift。最终 headline 应使用有 input fingerprint 和 parser cutoff 的 **35,422**；引用后者必须标注为 later local observation，不能混在同一表。

### 5.3 3.976B 与 2.453B 不是同一 token total

- 3.976B input 是 07-21~08-02、约 912 historical sessions 的字符估算，含非 swarm 论文工作。
- 2.453B total 是窄筛选两轮 swarm cohort 的 authoritative usage fields，且 total 包括 prompt+completion。

裁决：科学分析用 2.453B；广义账户历史分布可引用 3.976B，但标题必须写“宽历史估算”，不得相加或相互验证。

### 5.4 “最大 485 轮”与“最大 502 responses”口径不同

宽历史报告称最贵 session 485 轮；authoritative Phase-1 audit 在 session `b35f7b34-c97` 观察到 502 usage-bearing responses。可能原因包括 round/response 定义、archive dedup、字符估算脚本的 session grouping 与 cutoff 不同。

裁决：两轮相关本地数据使用 **502 responses**；若保留 485，必须注明它来自宽历史字符估算脚本，不能写成同一 session 的同一单位。

### 5.5 “10 个会话占 30.1%”与“Phase-1 top 10 占 53.89%”范围不同

30.1% 是约 912 个历史 sessions 中 300+ turns 组对宽历史估算 input 的份额；53.89% 是 36 个 Phase-1 predecessor 中 top-10 sessions 对该 cohort prompt 的份额。两者不能直接比较。最终两轮报告应优先使用 53.89%，并注明 cohort 只有 36 sessions。

### 5.6 “缓存命中率低”与 authoritative 71.33% cached prompt 冲突

宽报告自己承认未取得平台 cache stats；两轮 local response usage 明确记录 71.33% cached prompt tokens。裁决是撤回“低命中率已证实”，改写为“缓存比例不低，但长上下文总量仍压倒性大；价格影响待 billing table”。

### 5.7 17,692 assistant message objects 与 11,885 usage responses 不冲突

17,692 是 129 份 swarm-related transcript files 中的 message object count，包含 21 个 compaction snapshots、auxiliary sessions 和重复 archive segments。11,885 是 Phase-1/Phase-2 scoped usage-bearing responses，按 response/message id 去重、current copy 优先。

裁决：社会语料规模可写 17,692 message objects，但成本计算只能用 dedup 的 11,885 usage responses；不得用 message-object count 乘平均 tokens。

### 5.8 9,145 message occurrences 与 root boards 7,719 行范围不同

9,145 包含 122456 sandbox 内的复制/测试 `board/messages.jsonl`；root boards 合计 2,650+1,587+0+943+2,539=7,719。Exact canonical dedupe 为 6,301，但也要核查是否保留 nested provenance。

裁决：描述 host 社会活动用 root-board 7,719；研究复制/测试污染时才使用 9,145 occurrence scope，并明确 nested ledgers。

### 5.9 第一轮名义“36 agents”与 96 base sessions 必须同时出现

36 是逻辑 roster identities；归档有 36 Phase-1 bases + 60 Phase-2 bases = 96，Phase-2 的 60 又只映射到 36 identities。裁决：行为/身份叙述可以说 36 个角色，执行和成本必须说 96 base sessions，不能把两者互换。

---

## 最终报告建议使用的最窄结论

> 两轮都观察到一个稳定但受制度强烈塑造的过程：公共可见需求先吸引产出，重复后部分参与者转向验证和治理；能给出 executable counterexample、known-answer control 和单边可采用修补的挑战，确实多次改变代码和公开声明。但这个过程发生在身份不稳定、账本可污染、版本不可唯一、制度可被参与者读取并修改的环境中。第一轮没有交付真实 selection/adversary treatment；第二轮只有 97 个逻辑身份具备成功 API 请求证据，其中 96 个有可见工具/社会动作，且分散在状态不一致的主机岛屿。因而数据支持“反身的公共审计生态”，不支持“自然选择造成专业化、学科形成或 covert-adversary resilience”的因果主张。

成本方面，相关本地 MASO cohort 有 2.453B authoritative tokens，其中 94.60% 来自 Phase-1 predecessor cohort，长深度区间占绝大多数 prompt；duplicate lifecycle 的可避免上界为 17.70%。该数字不包含远端 direct-runner token，也不能在缺少模型/缓存价格表时独立复原 30 万人民币账单。
