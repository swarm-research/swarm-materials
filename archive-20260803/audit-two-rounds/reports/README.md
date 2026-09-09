# MASO 两轮社会模拟审计包

## 先看这个结论

二代的数量必须分层说，不能只报一个“agent 数”：

| 口径 | 数量 | 它实际代表什么 |
|---|---:|---|
| 宣传/编号宇宙 | 1,000 | 继承一代 1–36 号 + 计划新增 37–1000 号 |
| launcher 计划的二代新身份 | 964 | wave 1 的 64 个 + wave 2 的 900 个；不等于真实运行 |
| 快照中出现的身份日志路径 | 316 | 包括 122447 上 193 个 import 即失败的小日志 |
| 进入 runner 外层循环的身份 | 123 | 其中 26 个只命中本地 provider exception；0 HTTP 200、0 tool，不能叫 model-active |
| 日志中至少有一次 HTTP 200 的身份 | **97** | 最硬的“成功 API/model request”身份口径；HTTP 200 不是 model turn/token/session |
| 有实际 tool event 的身份 | 96 | 这96个全部至少 post 过 message；其中 95 个还 post 过 citation |
| 出现 runner 200-turn Finished marker 的身份 | 79 | 只有 64 个同时有 HTTP 200；另 15 个是 error-only loop 也被跑满 |
| 有 HTTP 200 但未见 Finished | 33 | 成功请求过，但快照时未见完成 marker |
| import-failure 身份 | 193 | 全部来自 122447，旧 Python 无法解析 `str | None`，0 API/model 活动 |

**97/96/123 都不是可分离的独立 actor/session/process 数。** 它们是不同证据层的逻辑 ID 数。同一 ID 有 2–3 个并发实例，log 固定路径会 `O_TRUNC`，session ledger 无锁丢记录。已无法从稳定快照精确恢复历史上的独立 session 数或峰值并发。

## 推荐阅读顺序

1. [`MASO两轮社会模拟深度分析-20260803.md`](MASO两轮社会模拟深度分析-20260803.md)：两轮整体判断、原始交互机制、成立/不成立的主张、下一轮设计。
2. [`成本与用量审计-20260803.md`](成本与用量审计-20260803.md)：2.453B 精确 token 审计、口径对齐、成本放大器和硬预算闸。
3. [`数据归档与远端状态-20260803.md`](数据归档与远端状态-20260803.md)：本地原始数据位置、稳定快照与 live-cut 区别、仍在运行的远端进程边界。
4. `evidence/gen1_raw/` 与 `evidence/gen2_raw/`：一代 27 条、二代 28 条原始过程链，含行号、时间、原文摘录和 SHA-256。
5. `evidence/gen1_quant/`、`evidence/gen2_snapshot/`、`evidence/usage/`：定量事实表、统一解析器和可复算脚本。
6. `redteam/CROSS_ROUND_REDTEAM.md`：独立红队对数字冲突、过度推断和证据上限的复核。

## 最值得保留的 insight

- 这不是被干净识别的“自然选择导致合作/专业化”，而是一个可见性、引用、文件系统、公开审计和被相信的制度共同塑造的认识论治理系统。
- 最稳定的跨 agent 价值链是“采用 → 可执行反例 → 局部承认 → 修复 → 复核”，不是相互赞同。
- 公开纠错能修复真 bug，也会引发 false retraction、过度认错和 audit-of-audit。
- append-only 保留了问责轨迹，却没有自动产生可信 current state；错误和更正会永久并存。
- 二代是四个互不同步的局部社会 + 一个失败岛，不是一个千人社会。
- 技术底座就是实际宪法：path、timestamp、sort、permission、seen cursor、log open mode 都直接决定社会事实。
- 成本的主因是 prompt/context 增长和生命周期失控，不是 completion 文字；第一轮 completion 仅占窄口径 total tokens 的 0.398%。

## 数据边界

- 一代筛出的 129 份实验相关 transcript records 可读完整 message/tool/time 结构，因此可做原始 process tracing；其中 21 份是 compaction snapshots、12 份是 auxiliary/subagent。精确 token 审计另用去重后的 36 个 predecessor base sessions + 62 个 successor-attempt files（60 个有 usage、2 个 zero-usage），最终由 96 个 usage-bearing logical base sessions 贡献，不能把 129 当 token cohort 分母。
- 二代 runner **没有持久化完整私有对话、tool arguments 或 usage**。可精确审计的是完整公开 board payload、citation、artifact、runner source、tool-result/response prefix 和 HTTP/error 日志。
- 二代 28 条链是 purposeful process-tracing cases，用来识别“机制是怎么发生的”，不是随机样本，不能据此报 prevalence 或 treatment effect。
- 交付包不复制 2GB+ 原始档案，避免再造一份巨大副本；精确本地路径、文件数和状态见数据归档报告。

## 快照可复现键

二代用于数字定案的五机稳定快照 fingerprint：

```text
6982fe49ade50cdd79b9a00cde736adcfd4e950d8c55b4f25a11b86eb396b49f
```

报告中 35,422 个 HTTP 200、97 个 HTTP-200 身份、96 个 tool-active 身份和 7,719 条 root-board 物理行都绑定该快照/解析口径。其中 7,719 含继承/跨机重复前缀，不等于 7,719 条二代新社会事件；精确 root-line unique 为 6,299，可归于本机 Gen2 活跃 ID 的 sender-line footprint 为 4,884。远端运行期间的更晚 live-cut 只用于存档，不与稳定快照数字混用。
