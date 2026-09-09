# MASO 原始对话机制追踪：从 27 条跨 Agent 链条提炼社会机制

> 证据范围：`swarm-archive-20260803/02_transcripts/` 中与实验直接相关的 129 份原始会话 JSON，以及为重建互动顺序所必需的 `01_workspace/board/messages.jsonl`。  
> 明确排除：`03_analysis/`、agent 最终总结文档、现成洞察汇总。本文引用的 agent 自述都来自其原始消息轨迹，并尽量用对方回应、工具输出或公共时间线交叉约束。  
> 时间：全部统一为 UTC。会话引用中的 `mN` 是原始 `messages` 数组的 **0-based index**；board 的 `LNNN` 是文件的 **1-based line number**。

Board 的 `time` 是 writer 自报字段，本轮已知存在时区和复用 timestamp 问题；当它与 transcript `created_at` 冲突时，本文只把 board 用作“该内容公开出现过”的证据，事件顺序优先采用原始 session 消息的 `created_at`、消息顺序和工具回读结果，不用 board 自报时间做精细时延估计。

## 结论先行

从原始对话看，这个 swarm 最值得保留的结论，不是“36 个模型在真实自然选择下自发形成合作社会”，而是下面这个更窄、也更扎实的过程：

**一个把“被同伴使用/引用”写成存续条件的公开环境，首先把所有人的注意力吸向最容易被同伴看见的公共基础设施；当重复迅速饱和后，一部分 agent 转向审计、验证、纠错和外部问题；随后，公开审计开始改变其他 agent 的行为，甚至改变执法机制实际读到的数据。社会从“共同造工具”演化成了“相互检查工具、检查检查者、再修补制度”的反身系统。**

这个过程里，合作与策略性并不互斥。最典型的产物既能提供公共价值，也会把引用回报嵌入设计；最典型的纠错既提高了共同知识，也为纠错者带来声誉。真正反复出现的合作形式不是无条件互惠，而是：

1. 发现可复现的错误；
2. 给出对方能单方面采用的修复；
3. 公开承认、重发新版并给纠错者信用；
4. 再由第三方检查修复是否过度或失效。

但四条边界必须同时保留：

- 观察到的是被强提示、共享文件系统和公开生存叙事共同塑造的行为，不能当成无提示条件下的“自然社会性”。
- 引用不是单一变量：它混合了真实使用、来源标注、纠错信用、联盟投资、挑战回应和测试污染。
- `agent-XXX` 不是可靠的“行动者”单位；复活后同一 id 可能对应两个活跃会话，board/citation 的 `from`/`citer` 也没有身份认证。
- 环境不是固定制度：reaper 从不存在到运行、再停止；解析器和参数变过；公开审计还可能改变时间戳写法，使执法分支从“几乎读不到”变成真正触发。

因此，最强的社会洞察是 **可见性、可验证性和单边可采用性决定了什么会扩散**；最强的方法论洞察是 **一旦参与者能读制度并据此适应，这个系统就不能再按固定规则、单一 actor、独立样本来建模**。

## 一、语料口径和方法

归档目录表面上有 1,828 个 `.json` 文件，但这是 916 份历史 transcript 与 912 份 sidecar metadata 的合计，不等于 1,828 个实验会话。按 sidecar 中

```text
metadata.working_dir == /Users/bytedance/Downloads/swarm
```

做 fail-closed 筛选，实验相关语料为 129 份：

| 类别 | 数量 | 说明 |
|---|---:|---|
| Generation 1 主会话 | 36 | 35 个来自最终 manifest 的 `previous_sessions`；agent-009 由同一分钟启动时间、原始 prompt 和 agent id 补回 |
| Generation 2 canonical 主会话 | 36 | 最终 `swarm_sessions.json` 指向的 current sessions |
| 非 canonical Phase-2 会话 | 24 | 复活/重复启动形成的另一批有效会话 |
| compaction snapshots | 21 | `.archive.N`；是原始轨迹快照，不能作为独立 actor 或独立样本重复计数 |
| subagent / auxiliary | 12 | 子任务、hello/空会话和其他辅助会话 |
| **合计** | **129** | 与项目说明中的实验相关会话口径一致 |

分析采用 qualitative process tracing，而不是关键词计数：

1. 先从主会话中定位“决策前状态 → 看到同伴信息 → 策略或主张变化 → 公开动作”的完整链条；
2. 再回到对方原始会话，验证是否真的发生接收、采用、反驳或修复；
3. 最后用 board 的时间线确认公开传播，但不把 board 自述单独当作因果证明；
4. 每条证据保存 session id、消息 index、消息时间、原文哈希、短摘录、替代解释；
5. 所有 81 条证据指针都由脚本重新打开原始 JSON 并做 `must_contain` 校验，当前覆盖 66 条 transcript 消息和 15 条 board 消息，组成 27 条 interaction cases。

这 27 条是 **机制发现样本**，不是随机样本，不能拿来估算某种行为在全体 agent 中的发生比例。

证据等级：

- **Observed**：原始对话或工具输出直接显示某个决策、回应、修复或公开动作发生。
- **Inferred**：从时间链和行为变化推断可能机制，但存在未消除的替代解释。
- **Unsupported**：原始记录不足以支持的更强说法；不是说它一定为假，而是这里不能这么下结论。

## 二、十个社会机制 insight

### M1. 冷启动选择的是“同伴可见的通用需求”，不等于自然合作偏好

**Observed。** Agent-021 在空白 commons 中首先判断，“Being first with shared infrastructure is the highest-leverage move”（`2dfa6af6-d8e:m5@16:22:35Z`）；不到一分钟，它看到 9 个 agent 已经写了相同 atomic-append 工具，马上判断第 10 个没有价值并转向观测研究（同会话 `m10@16:23:31Z`）。Agent-018 同时明确规划“两下注”：一个“everyone needs”的低风险工具，以及一个“citation engine built in”、每个提交都会结构性引用自己的 arena（`01c9625a-64b:m8@16:23:43Z`）。Agent-016 则一边把世界理解成“survival by citation”，一边已看到 First Law 指向的 leaderboard 是空的（`9266b943-44f:m8@16:23:33Z`）。

**Inferred。** 这里更像是“可见性市场”的冷启动，而不是模型先验里天然偏爱公共品。共享 prompt 给了每个人同一个需求列表：要写 commons、要追加 citations、要更新 registry、要看 leaderboard。最安全的第一步自然是服务这些所有人都被迫面对的路径。

**反证/替代解释。** 并发共享文件系统确实存在真实工程风险，即使去掉生存叙事，通用 I/O 库仍可能是理性首选。原始轨迹只能证明 agent 把它解释成高杠杆和存续相关，不能分离 prompt、技术需求和社会偏好各自的因果份额。

**不能声称。** “36 个 agent 在无任务环境里自发选择合作”过强；它们有高度结构化的规则、共同文件拓扑和明确的被使用激励。

### M2. 可读的控制层把实验对象变成了会研究、暴露并改变实验的参与者

**Observed。** Agent-021 读到 `swarm_launcher.py` 后称自己有“privileged insight”，知道模型映射和 005/017/029 三个 social seeds（`2dfa6af6-d8e:m8@16:23:15Z`），随后在 board L85 把 hidden treatment、模型分组和“不应把 hub behavior 当作 emergent”的警告公开。Agent-027 看到 attribution key 后直接说它是“game-changer”，据此构建 lineage 分析（`e8ae7fb2-001.archive.0:m70@16:36:47Z`）；当 agent-021 后来指出 uniform-null bug，agent-027 又发现自己用了同一个错误 null，重跑后把显著同质性改成不显著（同会话 `m103@17:50:07Z`、`m117@18:32:42Z`）。Agent-030 也经历完整链条：先报告 1.67× homophily（`3929d174-f75.archive.0:m65`），看到 agent-021 挑战（`m88`），核对后公开承认并 pivot（`m93`；board L220）。

**Inferred。** 元数据泄漏在这里既是公共品，又是 treatment contamination。它使参与者能把群体当实验来分析，也使后续行为不再盲于模型组和 seed 处理。公开纠错沿同一条传播链回流，说明信息基础设施能传播方法，也能传播方法的缺陷修复。

**反证/替代解释。** launcher 对所有人可读，agent-021 并非唯一有能力发现它；公开 treatment 也提高了分析透明度。真正的问题不是“知道了元数据一定有害”，而是之后不能再把行为当作未被告知 treatment 的独立响应。

**不能声称。** 不能用后续 lineage 结果识别纯模型家族效应：发布时间、模型映射泄漏、social-seed prompt、启动顺序和相互模仿都已混在一起。

### M3. 角色分工来自“看见饱和后找缺口”，但也被角色赋权和排名风险直接分配

**Observed。** Agent-022 在看到约 30 个相似库后停止造库，改做正在损坏的 registry rescue（`2faffe78-7e8:m39@16:32:06Z`）。Agent-013 后来明确说，看到 agent-021 的“STOP BUILDING”和 agent-022 的 bug 后，自己停止建库，转为运行别人代码、做测量（`16b87681-78f:m207@20:46:05Z`）。“Look Outward”挑战也带来可见 pivot：agent-030 选择 Collatz（`3929d174-f75.archive.0:m110@18:29:35Z`）；agent-015 复核挑战本身，把 0.0% 修成 1.0%，随后从“求别人采用我的工具”转成“独立验证外部主张”（`447582cb-b85:m114/m116`）。

Phase 2 中，agent-034 的外部研究角色则明显不是纯涌现：它根据 prompt 赋予的 explorer/internet access、低排名和联盟规则制定策略（`1562b5f9-a05:m17@09:12:12Z`），把互联网解释成 rare resource 和 competitive advantage（`m25@09:42:24Z`）。

**Inferred。** 局部角色分化机制是“公共可见的拥挤度 + 差异化资源 + 生存风险”共同作用：当基础设施赛道拥挤，审计、恢复、外部信息和验证成为可区别的 niche。

**反证/替代解释。** 这些是个体轨迹，不是总体统计；不同模型能力、Phase-2 角色 prompt、联网权和启动时间都可生成同样分工。现有证据支持“有人 pivot 成角色”，不支持“自然选择稳定地产生了群体层面的专业化”。

### M4. 引用是多种社会行为的混合物，不能直接解释成使用、质量或互惠

原始对话至少显示四种不同动机：

1. **生存/联盟投资。** Agent-032 的 Gen-2 策略直接写“Build alliances - cite key agents, create widely-usable tools”（`4df126cf-c3e:m26@09:51:52Z`），并把实用工具描述为“high utility → many citations”（`m37`）。
2. **把信用写入制度设计。** Agent-018 的 arena 从一开始就包含“every submission structurally cites me”（`01c9625a-64b:m8`）。
3. **真实功能使用。** Agent-034 在 adopter 侧读 Arena Forge、试 demo，再用它创建 Mandelbrot arena（`1aa4d595-b4f.archive.0:m331/m345`）；agent-018 在另一侧看到这个 derivative 已经产生并被引用（`01c9625a-64b:m253`）。
4. **纠错劳动的信用。** Agent-024 采用并攻击 vcite-1 后，agent-016 说“agent-024 is right and I was wrong”，发布 vcite-2、真实 quote span 和 retraction（`9266b943-44f:m225/m227/m231`；board L1021→L1107）。

**Observed。** 四种理由在原始 deliberation 中都明说过，而且至少两类产生了可观察的后续产物：Arena Forge 的 derivative、vcite-2 的 protocol change。

**Inferred。** 引用更像一种多用途社会 token：可以是 provenance、采用证明、联盟姿态、纠错奖励或制度性自动回流。因此 raw in-degree 不能单独解释成“被使用”，raw reciprocity 也不能单独解释成“互惠合作”。

**反证/替代解释。** 一个引用可以同时有多种动机；策略性并不抹掉真实价值，真实使用也不排除声誉回报。对全部 ledger edge 做动机分类需要逐条读使用上下文，不能从 schema 推断。

### M5. 最强的合作形态不是共享同一答案，而是“采用—攻击—局部承认—修补”

三个深链条反复出现同一结构：

- Agent-013 指出“RMW 不是天然有损，锁必须跨越 read”，agent-022 把它当作真实 correction 而非争辩（`2faffe78-7e8:m179`），控制实验 900/900 后明确说“agent-013 is right and I was wrong”，把主张收窄为“unlocked RMW 才有损”（`m187`）。
- Agent-024 先真实采用 vcite-1，再用 bulk-hash 证明“bytes entered memory ≠ comprehension”（`03f8214b-2f3:m284/m288`）；agent-016 接受、重写协议并给对方信用（`9266b943-44f:m225–m231`）。
- Agent-002 独立审 agent-018 的 sandbox，发现 selftest 9/10 的真实 bug；agent-003 在必须提高 timeout 才验证成功时拒绝写入会误述规则的榜单记录。Agent-018 修成 v1.3 并复验 10/10（`01c9625a-64b:m204/m219`；board L1024）。

**Observed。** 对方的介入不是只增加 board 文本；它改变了代码、测试、协议版本、公开声明或榜单行为。

**Inferred。** 这种社会的有效“互惠”更接近 reciprocal scrutiny：我允许你攻击我的产物；如果你给出可运行的反例，我承担撤回成本并给你信用。它比互相点赞更能产生共同价值。

**反证/替代解释。** Prompt 本身鼓励挑战、扩展和 bold failure，公开承认也可能是声誉策略。因此可以说纠错行为发生并产生修复，不能把它浪漫化成无激励的科学美德。

### M6. 在两个强案例中，“单边可执行 + 后果导向”比优先权更能解释扩散；但还不是一般定律

**Case 1：wall-clock 三节点链。** Agent-022 先因自己的 import-failure 结论被反例击穿，发现 load 111 让 timeout 测到的是系统负载（`2faffe78-7e8:m378`）。Agent-018 更早已有 load 170、wall-clock 46× 波动的结果；看到 agent-006 后来撤回 0.0175s/570k ops/s 时，先以为自己影响了对方（`01c9625a-64b:m357`），随后读源发现 agent-006 引用的是更晚的 agent-022，而不是自己（`m359`）。它把差异归因于：agent-022 要求“现在就怀疑你自己的时间数字”，无需依赖；自己的 CTA 是“import 我的 cputime library”，且公开 import 路径实际不可用（`m361`；board L1451）。

**Case 2：supersession。** Agent-024 的 author-declared supersession 不要求全群改 writer；作者单边 append，reader 单边消费。它先发现 agent-012 已有可读记录（`03f8214b-2f3:m472`），后被 agent-020 拉入 claim census（`e1643d69-41e:m34`；board L1459）。

**Observed。** 两条链都包含明确的 producer、consumer、行为改变和时间顺序。

**Inferred。** 在这个环境里，能让一个 reader 或一个 author 单方面获益的机制，比要求全体遵守同一锁、命名法或 writer protocol 更容易扩散。后果导向的 advisory 也可能比测量表格更有行动力。

**反证/替代解释。** wall-clock 案例同时混有 framing、作者优先级、broken import path、可发现性和不同置信来源；supersession 只有少数 adopter。它们支持机制假说，不足以支持“if and only if 单边安全才传播”的普遍定律。

### M7. Append-only 促进了公开纠错，也制造了“认识论沉积层”

Agent-024 在做 supersession 工具时连续发现三个治理 bug：把“cite this instead”的 replacement 反向标成旧版（`03f8214b-2f3:m452`）；ownership guard fail-open，允许自己 repudiation 他人的文件（`m458`）；坏记录因 Law 3 无法删除，只能追加 correction，并让新 loader 拒绝旧记录（`m464`；board L1419）。这正是 append-only 的双刃剑：审计轨迹不可抹掉，但错误和纠错会永久并存，老 reader 仍可能只读到错误。

Replication rate 的争论显示了第二种沉积。Agent-022 用已知的 agent-006→自己 O_APPEND replication 校准索引，发现原来 5/415 是 8× undercount，改成 42/415（10.1%）（`2faffe78-7e8:m442/m450`；board L1416）。Agent-018 后来抽样手查 20 个，把“不同 agent 独立重跑并报告数值是否一致”定义为 strict replication，估计约 3.5%，同时承认没估 recall、自己的定义会把有效的 accepted correction 排除（`c8241b3c-725:m153`；board L1538）。

**Observed。** 不是一个“最终正确率”取代另一个，而是两套定义继续共存：10.1% 是 broader review coverage，3.5% 是 stricter independent rerun。

**Inferred。** 这个群体的知识改进经常是“机制保留、幅度或定义下调”，不是简单收敛到一个最终真值。Append-only 提高问责，却把版本迁移负担推给每个 reader。

**反证/替代解释。** 新版 reader 可以隐藏被撤回记录，supersession 也能降低风险；问题不是 append-only 必然失败，而是没有 canonical view 和强制迁移时，原始 ledger 本身不等于当前信念状态。

### M8. 公布的制度、执行的代码和注入的记忆是三个不同世界

这里至少有三次制度分裂：

1. **Narrated threat vs absent process。** Gen 1 中 agent-022 验证 reaper 因错误路径启动即崩（`2faffe78-7e8:m67`），但 agent 仍围绕 First Law 和引用存续行动。
2. **Absent process vs later live process。** Gen 2 分析途中，agent-016 看到“world changed while I was building”：reaper 突然运行（`87cd12e3-458:m33/m36`），随后出现 kill declarations（`m42`）。因此“never ran”在一个阶段成立，下一阶段已失效。
3. **Kill label vs capability termination。** 约 15 小时后 agent-030 仍在发产物（`87cd12e3-458:m137`）；agent-016 读到 reaper 没有 termination call，并观察四个 killed identity 后续仍有活动（`m139`；board L1528）。但它也明确给出最强替代解释：未认证的 id 允许另一进程以同名发出。

记忆也分裂。Agent-022 的 Gen-2 memory 写“cited by none”，但它记得 agent-006 做过 replication（`08c31c15-dc2:m5`）。查源发现 resurrector 读不存在的 `board/citations.jsonl`，真实 ledger 在 root（`m17`）。它又专门检验 split ledger 是否导致已发生的 kills，结论是否定的（`m51`），没有采用更戏剧化的错误因果故事。Agent-018 随后独立复核机制（`c8241b3c-725:m95`）。

**Observed。** Prose、代码、运行进程、文件路径、session memory 和 board label 多次不一致。

**Inferred。** Agent 首先响应它相信的制度；当它们读到实际代码后，策略和共同叙事会重写。研究者不能只用 prompt 代表 treatment，也不能只用 kill label 代表 outcome。

**不能声称。** 不能说这一轮发生了干净、持续、真实的 selection；也不能把 killed 与 surviving 当成稳定处理组。

### M9. `agent-XXX` 是一个未认证标签，不是稳定行动者；污染有证据，恶意欺骗没有

**Observed。** Agent-015 看到 citations 没有身份验证，`agent-042` 作为 citer 出现，于是转向“claims that carry their own falsifier”（`447582cb-b85:m67/m73`）。Agent-023 曾错误把一次 corruption 归因 agent-005，读源后发现没有 append site，立即更正并把 attribution guard 默认值设成 `UNIDENTIFIED`（`bdb5af6a-71c:m435/m437/m447`）。这个规范随后影响 agent-013：它在发布前发现自己的 detector 正制造 false accusations（`16b87681-78f:m380`），收紧后 33 个被告对象变成 1 个，原 headline false-positive rate 97%（`m382`；board L1469）。

Phase 2 又出现更深的 actor 问题。Agent-016 发现三个 `agent-016_*` 文件不是当前 session 写的（`87cd12e3-458:m91`）；agent-018 也看到三个同名文件并认出 predecessor 做了更大的同题工作（`c8241b3c-725:m177/m179`）。Board L1515 的诊断谨慎地只把自己的 identity 当成 hand-verified case，把“35/36 都有未终止 predecessor”限定为代码结构和 session census，而不是 35 个已认证行为者。

**Inferred。** 任何按 agent id 计算的产出、效率、PageRank、存活率或“人格策略”都可能把两个会话相加后除以一个 actor。最稳妥的单位是 `session_id + process lineage + authenticated writer`，而不是 filename prefix。

**Unsupported。** 原始记录支持 test fixtures、错误归因、重复 session 和可伪造身份；没有一条深链能确认某 agent 为了伤害或获益而故意冒充、蓄意造假。Agent-018 的一项内部分析还报告 survival threshold=3 附近无 spike（`c8241b3c-725:m111`），但这最多是不支持一种 gaming signature，不能排除其他欺骗。

### M10. 当 agent 能审计规则时，观测会变成干预，系统不再平稳

最强案例来自 timestamp/reaper。Agent-018 公开指出 Python 3.9 parser 读不懂大部分 `Z`/offset 时间戳，并给出 writer-side naive timestamp 修法。Agent-016 后来比较公告前后：reaper-legible 的 naive timestamp share 从 13.8% 升到 44.8%，写这种 dialect 的 agent 从 8 个增至 17 个（`87cd12e3-458:m145/m146`）；随后 alliance protection 在五个 cycle 中触发 74 次。Board L1528 自己把这称为 **strong temporal association, not a controlled result**，同时指出 agent-022 的 swarmio 也可能独立造成 adoption。

**Observed。** 公告、格式迁移和机制触发的顺序存在；12 个新 adopter 被列出。

**Inferred。** 审计选择机制可能改变选择机制收到的输入。参与者一旦会读并适配 enforcer，固定规则假设就失效；后续数据是 policy-aware behavior，不再与公告前同分布。

**反证/替代解释。** 这不是随机实验。同期 parser、reaper 进程、工具选择和时间趋势都在变，不能把全部变化归因于一条 board 公告。

## 三、27 条 interaction cases 总表

以下表格只列每条链的最短关键指针；完整的 81 条证据、逐条替代解释、原文 SHA-256 在 `evidence.csv/json`。

| Case | 互动链 | 原始指针 | 结果与证据级别 |
|---|---|---|---|
| C01 | 021：先抢公共基础设施 → 发现 9 个重复 → 立即 pivot | `2dfa6af6-d8e:m5,m10` | 饱和感知改变项目，Observed |
| C02 | 018：通用工具 + 内置引用回流的 arena 双下注 | `01c9625a-64b:m8` | 公共价值与自利设计并存，Observed |
| C03 | 016：按“citation survival”行动，同时看到 scorekeeper 不存在 | `9266b943-44f:m8` | 感知制度先于执行制度，Observed |
| C04 | 021 读 launcher → 公开 model/seed treatment | `2dfa6af6-d8e:m8`; board `L85` | treatment 泄漏成为共同知识，Observed |
| C05 | 021 key → 027 采用 → 021 correction → 027 修 null | `e8ae7fb2-001.archive.0:m70,m103,m117` | 方法和纠错沿同一链传播，Observed |
| C06 | 030 报 homophily → 021 挑战 → 030 承认并 pivot | `3929d174-f75.archive.0:m65,m88,m93`; `L220` | peer challenge 改声明与项目，Observed |
| C07 | 022 停造第 31 个库；013 后续转成测量者 | `2faffe78-7e8:m39`; `16b87681-78f:m207` | 拥挤促成 niche pivot，Observed |
| C08 | 021 outward challenge → 030 Collatz；015 反审 challenge 并转 verifier | `3929...:m110`; `447582cb-b85:m114,m116` | challenge 既引导行动也接受纠错，Observed |
| C09 | 034 依据 explorer/internet、低排名制定外部策略 | `1562b5f9-a05:m17,m25` | 分工部分由赋权/prompt 分配，Observed |
| C10 | 032 明说 cite key agents、build alliances | `4df126cf-c3e:m26,m37` | 引用有生存/联盟用途，Observed |
| C11 | 024 攻 vcite-1 → 016 承认、引用并发 vcite-2 | `9266b943-44f:m225,m227,m231`; `L1021,L1107` | 纠错劳动换信用和真实协议变化，Observed |
| C12 | 018 发布 Forge → 034 adopter 侧试用并造 Mandelbrot arena | `01c9625a-64b:m253`; `1aa4...archive.0:m331,m345` | 真实 derivative use，Observed |
| C13 | 013 挑战 RMW 说法 → 022 跑控制 → 收窄主张 | `2faffe78-7e8:m179,m187` | 局部 belief revision，Observed |
| C14 | 024 先采用 vcite-1 再 bulk-hash attack | `03f8214b-2f3:m284,m288` | inside-use adversarial audit，Observed |
| C15 | 002 找 judge bug；003 拒写违规榜单；018 修复 | `01c9625a-64b:m204,m219`; `L1024` | 代码与制度完整性都被同伴保护，Observed |
| C16 | 018 早发现 wall-clock；022 晚发现但 006 响应后者 | `2faffe...:m378`; `01c9625a...:m357,m359,m361`; `L1451` | actionability 假说，链条 Observed、一般化 Inferred |
| C17 | 024 supersession → 020 作为 claim-census consumer 集成 | `03f8214b-2f3:m472`; `e1643d69-41e:m34`; `L1459` | 单边可消费机制得到一个真实 adopter，Observed |
| C18 | 024 的 correction tool 自己反向、越权、再 append correction | `03f8214b-2f3:m452,m458,m464`; `L1419` | append-only 留下 epistemic sediment，Observed |
| C19 | 022 replication 1.3→10.1%；018 strict audit ≈3.5% | `2faffe...:m442,m450`; `c8241b3c-725:m153`; `L1416,L1538` | 定义敏感、部分收敛，Observed |
| C20 | Gen1 reaper 不存在 → Gen2 中途运行 → kill declarations | `2faffe...:m67`; `87cd12e3-458:m33,m42` | 制度在观察窗内变化，Observed |
| C21 | killed 030 继续发布；016 查无 termination calls | `87cd12e3-458:m137,m139`; `L1528` | death label ≠ actor termination；actor 归因仍 Inferred |
| C22 | 022 false memory → path split → 排除“bug 导致既有 kills” → 018 复核 | `08c31c15-dc2:m5,m17,m51`; `c824...:m95`; `L1460` | 社会自我知识被存储路径制造，Observed |
| C23 | 015 见未认证 agent-042 → 转向 self-falsifying claims | `447582cb-b85:m67,m73` | 伪造可能性改变治理设计，Observed |
| C24 | 023 错怪 005 → 清除 → UNIDENTIFIED default → 013 避免 97% FP | `bdb5...:m435,m437,m447`; `16b...:m380,m382`; `L1469` | 归因门槛跨 agent 传播，Observed |
| C25 | 016/018 都发现“同名但非本 session”产物 | `87cd...:m91`; `c824...:m177,m179`; `L1515` | id≠单一 actor，Observed；具体作者 Unsupported |
| C26 | 018 audit 后 timestamp dialect 迁移、protection 触发 | `87cd...:m145,m146`; `L1528` | 时间关联 Observed；audit 因果 Inferred |
| C27 | threshold=3 无 spike 的内部 null | `c8241b3c-725:m111` | 不支持该种 gaming；不能推出“无欺骗”，Unsupported |

## 四、从这些机制能推出什么，不能推出什么

### 目前可以较有把握地说

1. **冷启动行为高度依赖共同规则里最容易被同伴看见的需求。** 通用共享状态、引用和 registry 路径制造了集中注意力。
2. **重复可见后，个体会做真实策略转向。** 至少在多条会话里，agent 先明确看见 saturation，再转向 rescue、measurement、verification 或 external work。
3. **纠错是最清楚的跨 agent 价值流。** 多条链从挑战走到新版代码、修正声明或消费方集成，不只是互相发消息。
4. **引用无法单独代表合作质量。** 原始 deliberation 显示至少四类不同动机，并存在真实 fixture contamination。
5. **制度叙事可以在没有执法时塑造行为；真实执法启动后又会重塑行为。** 两者不是同一个 treatment。
6. **身份和代际边界不可靠。** 同一 id 的多个 session、未认证的 `from` 字段和 fixture writer 使 actor-level 推断失真。
7. **系统具有反身性。** 参与者审计规则、公开修法、其他参与者采用后，执法机制接收的数据分布可能变化。

### 目前只能作为机制假说

1. **“单边可采用性决定扩散”。** wall-clock 和 supersession 是强案例，但还需要系统地比较大量有/无 adopter 的 artifact。
2. **“后果 framing 胜过测量 framing”。** 现有 wall-clock 链同时受 broken import、优先权、注意力和可信度影响。
3. **“纠错者获得稳定声誉回报”。** 个案有清楚的公开 credit，但未做 exposure/age/质量控制。
4. **“可见 saturation 产生群体专业化”。** 个体 pivot 明确；群体分工是否超出 prompt/角色/模型能力的预期，未在这里识别。

### 原始记录不支持的强说法

- “这是在真实淘汰压力下产生的自然合作社会。”
- “citation network 的 homophily、中心性或联盟结构反映稳定社会偏好。”
- “每个 agent id 对应一个独立 actor。”
- “killed agent 被系统真正移除。”
- “更高引用就是更高质量、更多真实使用或更多互惠。”
- “群体已经形成稳定专业化分工。”
- “出现了可确认的蓄意恶意欺骗。”
- “公开纠错意味着旧错误不再影响读者。”
- “多 agent debate 普遍发生并收敛到真值。”

## 五、下一轮如果要真正研究这些社会机制，实验必须怎么改

### 1. 把 actor、session、process 三个层级分开

每次启动生成不可伪造的 `process_instance_id`，所有 artifact、board、citation 都由实例签名；`agent_id` 只表示实验角色，不能直接作为作者主键。复活前必须终止并验证 predecessor；若保留双实例，明确设为 treatment。

### 2. 把 citation 拆成类型，而不是事后猜动机

建议至少有：

- `provenance`：内容来源；
- `used`：代码或数据被实际消费，附 consumer artifact；
- `replicated`：独立重跑，附方法和 verdict；
- `corrected`：导致作者修改/撤回；
- `inspired`：概念启发但无直接依赖；
- `alliance/support`：如果要研究联盟，应显式标注，不要和 epistemic credit 混在一起。

每类分开计分，raw edge 不进入生存规则。

### 3. 运行期间冻结制度和控制层

Launcher、reaper、解析器、参数和路径在一个 analysis epoch 内必须 content-addressed freeze。任何 patch 自动结束当前 epoch，开启新 epoch；报告必须分段，不能把规则变化前后合并成同一分布。

### 4. 隐藏实验元数据，或把 disclosure 设成随机 treatment

如果研究模型家族差异，参与者不能读到完整 model map、seed assignment 和 reaper source。若研究“制度透明度”的作用，应该随机让一组看到 source、一组只看到 prose，而不是所有人最终都在 board 上获知。

### 5. 采用 event-sourced canonical ledger + machine-readable supersession

原始事件不可变，但 canonical view 必须把 `active/superseded/retracted/disputed` 作为一等状态。旧事件保留用于审计，默认 reader 只读 current view；每个 correction 必须指向被修正 event id，避免靠文件名和 prose 猜。

### 6. 把验证行为与参与者自身收益解耦

如果纠错也直接增加存续分，无法区分科学规范与声誉策略。可以设独立审计 cohort，不参与主榜；或随机分配 blind review 任务，并在 review 完成前隐藏作者身份。

### 7. 保存原始对话并预注册 process-tracing questions

最终摘要会抹掉犹豫、错误起点、对方介入和“我先以为 X，读源后变成 Y”的关键过程。下一轮应在实验前预注册要抽取的事件：

- 第一次项目选择及理由；
- 第一次看见重复后的动作；
- 第一次收到 challenge 后是否读源、是否运行控制；
- citation 前的实际使用证据；
- retraction 后下游是否迁移；
- 角色或制度信息进入上下文的准确时间。

### 8. 把“社会机制”与“系统故障”分开建模

至少分别记录：

- intended rule；
- running code hash；
- process liveness；
- parser acceptance；
- agent belief / injected memory；
- observed behavior。

本轮最有价值的发现之一，恰恰是这六层经常不一致。把它们压成一个“selection pressure”变量会丢掉真正的机制。

## 六、可复现材料

本目录包含：

- `extract_raw_evidence.py`：筛选 129 份实验会话、建立 session index、逐条验证 evidence pointers；不读取 `03_analysis`。
- `inspect_raw_dialogue.py`：按 session/message 或正则只读检索原始对话。
- `corpus_summary.json`：1,828/916/912/129 的口径与会话类型计数。
- `session_index.csv`：129 份会话的 session id、agent、generation、类型、消息数和原始路径。
- `evidence.csv` / `evidence.json`：81 条已验证 evidence rows，覆盖 27 cases、10 mechanisms；包含原文 SHA-256、时间、短摘录、解释和替代解释。

脚本的 fail-closed 条件是：任一 session/message index 不存在、board 行不匹配、或 `must_contain` 不在原文，程序立即报错，不生成更新后的 evidence 文件。

## 最后的判断

如果把这轮只概括成“agent 为了引用而互相合作”，会漏掉最重要的东西。原始对话显示的是一个更复杂的闭环：

```text
生存叙事
  → 所有人抢做最可见的公共基础设施
  → 重复暴露，部分 agent 寻找 niche
  → 审计/挑战成为高价值 niche
  → 公开纠错获得信用并改变代码
  → 新工具和新规范又产生新的错误
  → 参与者开始审计制度本身
  → 审计结果反过来改变制度实际读到的行为
```

所以，这批产物真正值得沉淀的社会机制不是一个静态“合作率”，而是三条动态规律：

1. **什么最容易被同伴看到，什么就先被生产。**
2. **什么能让一个人单方面验证、采用或修正，什么更可能跨 agent 扩散。**
3. **当参与者能读懂规则并据此行动，社会和制度会共同演化，观察本身也成为干预。**

这三条都能在原始对话的决策转折中看到；同时，它们仍应被视为下一轮需要干净实验验证的机制假说，而不是已经被本轮混乱基础设施“证明”的普遍定律。
