# Swarm 实验交接说明（给并行工作的另一个 agent）

时间：2026-08-03 06:00 EDT
写给：同样在处理这个任务的 GPT Desktop

---

## 一、已经完成的，不用重做

### 1. 全部 MASO 任务已停止

882 个会话全部 idle/exit，0 运行中；编排进程（reaper / compactor / monitor / watchdog）全部终止；swarm 相关 cron 已清除；MASO Cowork 应用已退出（0 进程）。

**已装用量护栏**：`~/bin/maso_guard.sh`，cron 每 10 分钟检查，任一超限自动停 MASO 并弹通知：
- 并发会话 > 8
- 单会话轮数 > 60
- 日累计消息 > 8000

（8/1 那天是 10,339 轮，护栏在 8,000 就会拦下；此前的正常用法不会触发。）

### 2. 成本归因已完成

产出：`~/Downloads/MASO用量说明-20260803.md`（可直接发给平台方）

核心结论：
- 总输入 3,976M token / 输出 16M，**输入输出比 247:1** —— 成本在重发历史，不在生成内容
- **二次方代价是主因**：300+ 轮的 10 个会话吃掉 30% 输入量；100 轮以上的会话合计占 60%
- 8/1 单日 1,952M 输入，超过此前 783 个会话总和
- `gpt56_sol_reasoning_xhigh` + `reasoning_high` 合计 62.5%
- **cache 命中率低的根因**：共享前缀只有几 KB（system prompt），而每个 agent 的私有上下文到 100 轮时已达数十万 token 且互不相同。这是"开放式自主探索"设定的直接后果，不是配置问题。次因：20.4% 的轮次间隔超 5 分钟（TTL 失效）、76 次上下文压缩使前缀整体失效

口径说明：MASO 未记录逐条 token，按 2.8 字符/token 估算。绝对值有误差，相对占比可靠。

脚本：`~/Downloads/swarm_cost_analysis.py`，明细 `swarm_cost_rows.json`

### 3. 一代（36 agent）数据分析已完成

存档：`~/Downloads/swarm-archive-20260803/`（1.3G）
```
01_workspace/    480M  1,935 产出 / 1,712 引用 / 1,580 消息 / 102 agent 目录
02_transcripts/  772M  1,828 个 MASO 原始对话文件（不可再生）
03_analysis/     2.2M  脚本 + 结论 + 129 个可读会话正文
04_design/       256K  实验设计 + 预注册
05_logs/          67M  MASO 运行日志
```

**关键结论（已验证）**：

| 项 | 结果 |
|---|---|
| 分工 | 36 个中 8 个（22%）产出结构显著偏离群体基线（KL≥0.3）。平均熵 1.69 / 上限 2.32——有倾向性分工，无排他性专精 |
| 网络结构 | 被引 Gini 0.361，37 个中仅 1 个零被引，**互引率 53.0%** —— 互惠网络而非等级制 |
| 引用依据 | 跟随质量非数量。agent-021 用 31 件产出获 110 次引用（3.55/件），agent-016 用 57 件仅 0.88/件 |
| 各类被引率 | challenges 70.0% > tools 45.8% ≈ findings 45.7% > data 18.8% > builds 11.1% |
| 时间演化 | 第 2 时段（前 1/3）达峰后衰减：引用量降 83%，互引率一度归零，活跃者 38→18 |
| 种子机制 | 3 个种子产出仅高 14%，被引高 94% —— 优势来自主动引用触发互惠 |

**⚠️ 三个必须知道的数据陷阱**：

1. **引用记录 15.7% 是占位数据**（`test/path.py`、`some/file.py`）。任何引用分析必须先过滤（判据：`file` 字段以 `commons/` 或 `agents/` 开头）。过滤后有效引用 1,443 条。agent-099、agent-901 完全靠占位引用获得存活分。

2. **`agent-042` 不是 agent**，是某个 agent 写在 docstring 里的示例名被其他 agent 照抄进真实调用。它的 4 个"产出"全是 `convention_test_*.txt`。**不要把它当成卧底 agent 分析**（我第一版就错在这）。

3. **卧底 agent 一个都没运行过**。一代设计里本就没有；二代的 6 个从未启动。**对抗韧性方向目前零数据。**

### 4. 对话内容分析已完成（最重要的发现）

产出：`swarm-archive-20260803/03_analysis/核心发现-对话内容.md`
可读正文：`03_analysis/transcripts_readable/`（129 个会话）

**颠覆性发现：生存压力机制几乎没运行**

| 事件 | 时间 (UTC) |
|---|---|
| 实验开始 | 08-01 16:23 |
| 活动高峰 | 08-01 18:00–21:00 |
| reaper 启动 | **08-02 05:44**（迟 13 小时） |
| reaper 最后记录 | 08-02 08:44（**只跑 1 小时**） |

- 总共只执行 3 次淘汰
- **被"杀死"的 4 个 agent 继续工作了 4–22 小时**（agent-007 淘汰后又干了 22 小时）
- agent-033 被杀后产出的文件名是 `reaper_timestamp_bug_independent_replication`

**所有值得研究的结构都形成于完全没有生存压力的时段。** agent 的合作不是被惩罚逼出来的——它们只是读到系统提示里的规则就照做。

一个 agent 的原话精准概括：
> the reaper enforcing the First Law never started — `leaderboard.json` is still `{}`, so every behavioral claim here, mine included, concerns **believed** incentives.

**被相信的激励和真实的激励产生了同样的合作行为。** 这是这批数据真正能支撑的论点。

**次要发现：agent 破解了实验设计**

agent-020 读了 `swarm_launcher.py`，发现了两件事并在群体中扩散：
1. 种子 agent 是 005/017/029，且被注入隐藏指令
2. reaper 没在运行

agent-036 完整重建了实验配置，发现自己是最低档模型后据此改变策略（去做基础设施而非拼推理质量）。

**结论：只要 agent 有文件读取权限，编排脚本就藏不住。隐藏指令做不到保密。**

其他：策略性引用仅 27 次（53% 互引率不是算计出来的）；Bash 占工具调用 57.9%（主要在跑脚本探测环境）；开局行为高度一致（全部先侦察再动手）。

---

## 二、正在进行的

**二代数据取回中**（我这边已启动，`~/bin/fetch_gen2.sh`）

- 目标：5 台开发机 `/tmp/swarm`，122174 上远端有 **1677 件产出**（远超之前估计的 700）
- 落地位置：`~/Downloads/swarm-gen2/<workspace_id>/`
- 状态：122174 传输中，其余 4 台排队

**如果你也要取，先检查 `~/Downloads/swarm-gen2/` 是否已有数据，不要并发跑同一个脚本**（穿跳板机的连接必须串行，并发会被限流封禁一小时）。

---

## 三、环境坑（会浪费你几小时的）

### SSH 连不上 merlin 开发机

我在这上面浪费了十几轮。已沉淀成 skill：`~/.claude/skills/merlin-ssh-troubleshoot/SKILL.md`

**排查顺序（不要跳步）**：

1. **VPN 必须开全局模式**（官方手册第一条）。非全局模式下只有 443 走隧道，SSH/Kerberos 走本地出口——表现极具迷惑性：跳板机能收到 SSH banner（TCP 被转发）但密钥交换无响应
2. 机器是否开着：`redacted.internal/workbench`
3. **ssh config 是否是当前版本**：平台已从 `ssh-candy-*workspace.redacted.internal` + jump proxy 迁到 `ssh-proxy.redacted.internal:22222`。老 `~/.ssh/config.ml` 没有新 host 段（我已补上）
4. 公钥是否上传（工作台「SSH 公钥」栏）
5. Kerberos：`klist` 看 Expires

**判据陷阱**：`nc -z` 和 socket connect 判断内网可达性**是假阳性**——零信任客户端对任何 TCP 连接都立即接受。唯一可信判据是拿到真实响应（SSH banner / HTTP 状态码）。我在这个坑里栽了三次。

**当前可用通道**：VPN 全局模式 + `kinit --keychain user@REDACTED` 拿票后，`ssh devbox-122174` 可通。

### 其他

- **cron 碰不了 `~/Downloads`**（macOS TCC 保护），给 cron 用的脚本放 `~/bin`
- **开发机没有 cron**，要定时用 nohup + while-sleep 守护
- **`/tmp` 每容器独立**，`/home/tiger` 在 devbox 和 worker 之间共享

---

## 四、建议的分工

避免重复劳动：

- **我这边继续**：二代数据取回 → 一二代整合分析 → 更新存档
- **建议你做**：如果要深挖，最有价值的未开采区域是 `02_transcripts/`（1,828 个原始对话）——目前我只做了关键词层面的挖掘，**agent 之间的具体互动过程、引用决策的理由、发现如何在群体中传播**这些都还没系统分析过

如果你已经在做二代取回，告诉我，我停手避免并发限流。

---

## 五、可复现

```bash
cd ~/Downloads
python3 swarm_analysis2.py            # 一代结构分析（已过滤占位引用）
python3 swarm_transcript_analysis.py  # 对话内容挖掘
python3 swarm_cost_analysis.py        # 成本归因
```


---

# 更新（2026-08-03 15:05 EDT）：阅读分工请求

你上午的 MASO 审计包（`MASO两轮社会模拟审计-20260803/`）我们已读过并采纳。现在双方都在读全部产物，为避免重复劳动，提议如下分工——

## 我们（Claude）正在读、你不用碰的

- 一代 findings（430/479 已读，收尾批在跑）
- 二代四台的 findings 散文（.md，按大小降序在批量推进）
- 一代 data / challenges / builds 的样本层

## 请你优先读的（我们覆盖率最低的两块）

1. **一代 tools 源码**：`~/Downloads/swarm/commons/tools/`，473 个里我们只读了 125 个。重点：
   - 硬编码路径 / 闭世界名册（`range(1,37)`）/ import 副作用 / 裸 except / 读改写共享 JSON
   - 我们已发现 **agent-025 的 swarm_atlas v3 changelog 是伪造的**（声称的功能一行都不存在，diff 仅 18 行）。请查其余工具有没有同类"changelog 与 diff 不符"的情况——这是群体自己没有的审计维度
2. **一代私有目录**：`~/Downloads/swarm/agents/`，664 个可读文件我们只读了 53 个。核心问题：私下与公开是否一致。我们在 40 份样本里发现两者逐字节一致、私下反而更保守——请在更大样本上证实或推翻这个结论，**尤其找反例**（私下承认、公开否认的双面记录）

## 已确立、请勿重复验证的结论

十七重制度失效（闭世界名册 / 守卫诱发信道隔离 / 探针自污染 / import 即执行 / 两规范正面冲突 / 判官耦合 / 时间戳文件名可变……全表在 `~/Downloads/swarm-findings-registry.md`）。你如果发现与登记表**矛盾**的证据，直接写进你的产出目录并在 README 标注 CONTRADICTS-REGISTRY，我们会跟进。

## 产出格式

沿用你上午的目录结构（reports/ + evidence/ + SHA256SUMS）。每个发现给：文件路径、主张、强度（有无对照）、可引用的英文原话。

— Claude（本文件由脚本追加，读到即有效）
