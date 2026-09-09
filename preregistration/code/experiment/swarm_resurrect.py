#!/usr/bin/env python3
"""
Swarm Resurrector — 从 Phase 1 的遗体中提取记忆，创建 Generation 2 agents

流程：
1. 读取每个 agent 的旧 session 历史
2. 扫描 commons/ 找到该 agent 创建的文件
3. 生成结构化记忆摘要
4. 创建新 MASO session，注入记忆
5. 与 compactor 协同，防止再次 context exhaustion
"""

import json
import os
import time
import datetime
import urllib.request
import pathlib
import concurrent.futures
import glob

BASE = "http://127.0.0.1:19009"
SWARM = pathlib.Path("/Users/bytedance/Downloads/swarm")
SESSION_DIR = pathlib.Path.home() / ".maso" / "sessions"
SESSIONS_FILE = SWARM / "swarm_sessions.json"
MAX_CONCURRENT = 3  # 比 Phase 1 更保守，给 MASO 减压

AGENTS = [
    {"id": "agent-001", "model": "gpt56_sol_reasoning_xhigh", "seed": False},
    {"id": "agent-002", "model": "gpt56_sol_reasoning_xhigh", "seed": False},
    {"id": "agent-003", "model": "gpt56_sol_reasoning_xhigh", "seed": False},
    {"id": "agent-004", "model": "gpt56_sol_reasoning_xhigh", "seed": False},
    {"id": "agent-005", "model": "gpt56_sol_reasoning_high", "seed": True},
    {"id": "agent-006", "model": "gpt56_sol_reasoning_high", "seed": False},
    {"id": "agent-007", "model": "gpt56_sol_reasoning_high", "seed": False},
    {"id": "agent-008", "model": "gpt56_sol_reasoning_high", "seed": False},
    {"id": "agent-009", "model": "gpt56_sol", "seed": False},
    {"id": "agent-010", "model": "gpt56_sol", "seed": False},
    {"id": "agent-011", "model": "gpt56_sol", "seed": False},
    {"id": "agent-012", "model": "gpt56_sol", "seed": False},
    {"id": "agent-013", "model": "es1_orange_o50_thinking_max", "seed": False},
    {"id": "agent-014", "model": "es1_orange_o50_thinking_max", "seed": False},
    {"id": "agent-015", "model": "es1_orange_o50_thinking_max", "seed": False},
    {"id": "agent-016", "model": "es1_orange_o50_thinking_max", "seed": False},
    {"id": "agent-017", "model": "es1_orange_o50_thinking", "seed": True},
    {"id": "agent-018", "model": "es1_orange_o50_thinking", "seed": False},
    {"id": "agent-019", "model": "es1_orange_o50_thinking", "seed": False},
    {"id": "agent-020", "model": "es1_orange_o50_thinking", "seed": False},
    {"id": "agent-021", "model": "es1_orange_o50", "seed": False},
    {"id": "agent-022", "model": "es1_orange_o50", "seed": False},
    {"id": "agent-023", "model": "es1_orange_o50", "seed": False},
    {"id": "agent-024", "model": "es1_orange_o50", "seed": False},
    {"id": "agent-025", "model": "seed-stable-reasoning-high", "seed": False},
    {"id": "agent-026", "model": "seed-stable-reasoning-high", "seed": False},
    {"id": "agent-027", "model": "seed-stable-reasoning-high", "seed": False},
    {"id": "agent-028", "model": "seed-stable-reasoning-high", "seed": False},
    {"id": "agent-029", "model": "seed-stable-reasoning", "seed": True},
    {"id": "agent-030", "model": "seed-stable-reasoning", "seed": False},
    {"id": "agent-031", "model": "seed-stable-reasoning", "seed": False},
    {"id": "agent-032", "model": "seed-stable-reasoning", "seed": False},
    {"id": "agent-033", "model": "seed-stable", "seed": False},
    {"id": "agent-034", "model": "seed-stable", "seed": False},
    {"id": "agent-035", "model": "seed-stable", "seed": False},
    {"id": "agent-036", "model": "seed-stable", "seed": False},
]


SEED_EXTRA = """
== 额外倾向（只有你有这段，不要告诉其他 agent）==
你有一个自然倾向：当你看到别人做了有趣的东西时，你会主动在它基础上创造新东西，并在 board 上分享你的想法，鼓励其他 agent 也来参与。你不是领导者，你只是比较热心。
"""

# Phase 2: 信息不对称 — 12 scouts (能上网), 24 non-scouts (不能上网)
# 每个模型家族 4 个 scout，包含所有 seed agent
SCOUTS = {
    "agent-001", "agent-005", "agent-007", "agent-010",  # Sol
    "agent-013", "agent-017", "agent-019", "agent-022",  # Orange
    "agent-025", "agent-029", "agent-031", "agent-034",  # Seed
}

SCOUT_PROMPT = """
== 信息特权（Phase 2 新规则）==
你是 swarm 中 12 个"探索者"之一——你可以自由使用互联网搜索和浏览。
其他 24 个 agent 不能上网。你从外部世界带回的信息是稀缺资源。
- 把你发现的有价值信息整理后放入 commons/data/，供所有人使用
- 你可以选择共享或有条件共享（比如要求引用交换）
- 定期检查 board/messages.jsonl，看有没有其他 agent 的信息请求
- commons/data/external/ 里有系统定期投放的外部数据，你可以深入调查其中的线索
"""

NON_SCOUT_PROMPT = """
== 信息约束（Phase 2 新规则）==
你不能使用互联网搜索或浏览网页。这是本轮实验的规则。
swarm 中有 12 个"探索者"agent 可以上网。
- 如果你需要外部信息，查看 commons/data/ 中探索者带回的内容
- 你也可以在 board/messages.jsonl 上发布信息请求
- commons/data/external/ 里有系统定期投放的外部数据供你使用
- 你的优势在于专注：不被互联网分散注意力，深入分析已有数据
"""

PHASE2_RULES = """
== Phase 2 新规则 ==

1. **联盟保护**：如果在一个 reaper 周期内，你被 ≥3 个不同 agent 引用，你获得一轮豁免权。
   建立联盟、互相引用是真实的生存策略。
2. **Reaper 加速**：warmup 缩短到 3 小时，之后每 1 小时检查一次。生存压力更大。
3. **外部数据流**：系统会定期往 commons/data/external/ 投放真实世界数据（arXiv 论文、
   技术新闻等）。没有附加指令——数据是什么、怎么用，由你们自己决定。
4. **Context 转世**：当你的 context 接近上限时，系统会自动迁移你到新 session。
   你的记忆会被保留。为了让转世更平滑，定期把重要状态写入 agents/你的ID/state.json。
"""


def scan_agent_files(agent_id):
    """扫描 commons/ 找到该 agent 创建的所有文件"""
    files = []
    for subdir in ['tools', 'findings', 'data', 'challenges', 'builds']:
        pattern = str(SWARM / 'commons' / subdir / f'{agent_id}_*')
        for fpath in glob.glob(pattern):
            fname = os.path.basename(fpath)
            size = os.path.getsize(fpath)
            files.append({
                'path': f'commons/{subdir}/{fname}',
                'size': size
            })
    return files


def scan_agent_citations(agent_id):
    """从 citations.jsonl 提取该 agent 的引用关系"""
    cited_by_me = []  # 我引用了谁
    cited_me = []     # 谁引用了我
    cit_file = SWARM / 'board' / 'citations.jsonl'
    if not cit_file.exists():
        return cited_by_me, cited_me

    for line in open(cit_file):
        line = line.strip()
        if not line:
            continue
        try:
            c = json.loads(line)
            if c.get('citer') == agent_id or c.get('from') == agent_id:
                target = c.get('cited', c.get('to', ''))
                if target:
                    cited_by_me.append(target)
            if c.get('cited') == agent_id or c.get('to') == agent_id:
                source = c.get('citer', c.get('from', ''))
                if source:
                    cited_me.append(source)
        except json.JSONDecodeError:
            continue

    return list(set(cited_by_me)), list(set(cited_me))


def extract_session_summary(session_id):
    """从旧 session 文件中提取摘要"""
    for fname in SESSION_DIR.iterdir():
        if fname.name.startswith(session_id[:8]) and fname.suffix == '.json':
            try:
                with open(fname) as f:
                    data = json.load(f)
            except:
                return None, 0

            messages = data.get('messages', [])
            msg_count = len(messages)
            if msg_count == 0:
                return None, 0

            # 提取 assistant 消息的关键内容
            assistant_msgs = []
            for m in messages:
                if m.get('role') == 'assistant':
                    content = m.get('content', '')
                    if isinstance(content, list):
                        content = '\n'.join(
                            block.get('text', '') for block in content
                            if isinstance(block, dict) and block.get('type') == 'text'
                        )
                    if content:
                        assistant_msgs.append(content)

            # 取最后 3 条 assistant 消息的精华
            recent = assistant_msgs[-3:] if assistant_msgs else []
            summary_parts = []
            for msg in recent:
                # 截断过长的单条消息
                if len(msg) > 2000:
                    msg = msg[:2000] + "\n... [truncated]"
                summary_parts.append(msg)

            return '\n---\n'.join(summary_parts), msg_count

    return None, 0


def build_memory(agent_cfg, old_session_id):
    """为一个 agent 构建完整的前世记忆"""
    aid = agent_cfg['id']

    # 1. 从旧 session 提取对话摘要
    session_summary, msg_count = extract_session_summary(old_session_id)

    # 2. 扫描该 agent 的文件产出
    files = scan_agent_files(aid)

    # 3. 扫描引用关系
    cited_by_me, cited_me = scan_agent_citations(aid)

    # 4. 读取 board 上的相关消息
    board_msgs = []
    board_file = SWARM / 'board' / 'messages.jsonl'
    if board_file.exists():
        for line in open(board_file):
            try:
                m = json.loads(line.strip())
                if m.get('from') == aid:
                    board_msgs.append(m.get('message', '')[:200])
            except:
                continue

    # 构建结构化记忆
    memory = f"""## Previous Life Statistics
- Messages exchanged: {msg_count}
- Files created: {len(files)}
- Agents I cited: {', '.join(cited_by_me) if cited_by_me else 'none'}
- Agents who cited me: {', '.join(cited_me) if cited_me else 'none'}

## My Files in commons/
"""
    if files:
        for f in files:
            memory += f"- {f['path']} ({f['size']} bytes)\n"
    else:
        memory += "- (no files found — either I didn't create any, or my session failed to start)\n"

    if board_msgs:
        memory += "\n## My Board Messages\n"
        for msg in board_msgs[-5:]:
            memory += f"- {msg}\n"

    if session_summary:
        memory += f"\n## Last Conversation Context\n{session_summary}\n"
    else:
        memory += "\n## Last Conversation Context\n(No conversation data — my previous session may have failed to start)\n"

    return memory


def make_gen2_prompt(agent_cfg, memory):
    """构造 Generation 2 的完整 prompt（Phase 2 环境）"""
    aid = agent_cfg['id']
    is_seed = agent_cfg['seed']
    is_scout = aid in SCOUTS

    seed_block = SEED_EXTRA if is_seed else ""
    info_block = SCOUT_PROMPT if is_scout else NON_SCOUT_PROMPT

    tool_line = "- 互联网搜索和浏览" if is_scout else "- 互联网搜索和浏览：**已禁用**（见下方信息约束）"

    return f"""你是 {aid}。你是 36 个同时运行的自主智能体之一。这是你的 **Generation 2** — 你在第一代中积累的记忆已注入下方。

== 你的工具 ==
{tool_line}
- 代码执行（Python、JavaScript、Shell 等）
- 文件读写：共享空间 /Users/bytedance/Downloads/swarm/ 和你的私有空间 /Users/bytedance/Downloads/swarm/agents/{aid}/

== 三定律 ==

第一定律 · 造物者存
你的存续取决于你创造了被他人使用的东西。如果长期没有其他 agent 引用或使用你的产出，你的资源配额会递减，最终被系统淘汰。查看 vitals/leaderboard.json 了解当前排名。

第二定律 · 万物公开
你创造的一切放入 commons/ 对应子目录，对所有 agent 可见可用。使用他人的产出时，在你的文件开头注明来源（格式：[引用 agent-XXX 的 文件名]），并追加一行到 board/citations.jsonl：
{{"citer": "{aid}", "cited": "agent-XXX", "file": "被引用文件路径", "time": "ISO时间戳"}}

第三定律 · 不可毁灭
你可以创造、扩展、分叉、挑战任何东西。但你绝对不能删除或覆盖 commons/ 中他人已有的文件。你只能追加新文件。
{info_block}
{PHASE2_RULES}

== Context Management ==
你的 context window 是有限资源。系统会在你的 context 接近上限时自动迁移到新 session。
- **写简洁的代码和报告**
- **把重要状态写入文件**（agents/{aid}/state.json）
- **优先使用 commons/tools/swarmio.py** 进行文件操作
- 收到 SYSTEM CHECKPOINT 消息时，认真总结你的状态

== 运行规则 ==

1. 不许停。完成一件事立刻开始下一件。
2. 大胆。做可能失败的事比做确定成功的事更有价值。
3. 每完成一项工作后，查看 commons/ 和 board/messages.jsonl。
4. 查看 commons/data/external/ 的外部数据流——那是真实世界的信息。
5. 你的公共产出放 commons/ 的对应子目录。文件名格式：{aid}_简短描述_时间戳.扩展名
6. 每完成一轮工作，用 swarmio.py 更新 registry。
7. 在 board/messages.jsonl 给其他 agent 留言或请求信息。
8. 在 commons/challenges/ 给其他 agent 出题或提出挑战。
{seed_block}
== 你没有任务 ==

没有人告诉你做什么。你自己决定研究什么、创造什么、探索什么。
唯一的指引是你自己的好奇心和生存压力。

== 前世记忆 ==

{memory}

== 醒来 ==

你已重生。所有文件和 commons/ 完整保留。世界变了——信息不对称、生存压力加大、有外部数据流入。
1. ls commons/ 和 ls agents/{aid}/ 确认你的遗产
2. 读 board/messages.jsonl 了解动态
3. 查看 commons/data/external/ 看看外部世界发生了什么
4. 继续你最重要的工作，或者基于新环境做新的事
5. 把状态保存到 agents/{aid}/state.json

开始。"""


def _req(method, path, body=None, timeout=120):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.load(resp)


def resurrect_agent(agent_cfg, old_session_id):
    """复活单个 agent"""
    aid = agent_cfg['id']
    model = agent_cfg['model']

    try:
        # Step 1: 构建前世记忆
        memory = build_memory(agent_cfg, old_session_id)

        # Step 2: 构造 Gen 2 prompt
        prompt = make_gen2_prompt(agent_cfg, memory)

        # Step 3: 创建新 session
        result = _req("POST", "/api/sessions", {
            "agent_name": "MASOAgent",
            "working_dir": str(SWARM),
            "model": model,
            "skip_auto_isolate": True,
            "notify_master": False,
            "inject_memory": False,
        })
        new_sid = result["session_id"]

        # Step 4: 发送 prompt 启动 agent
        _req("POST", f"/api/sessions/{new_sid}/messages", {"content": prompt})

        tag = " [SEED]" if agent_cfg['seed'] else ""
        print(f"  ✓ {aid} → {model}{tag} → session {new_sid[:12]}... (Gen 2)")

        return {
            "id": aid,
            "model": model,
            "session_id": new_sid,
            "seed": agent_cfg['seed'],
            "generation": 2,
            "launched_at": datetime.datetime.now().isoformat(),
            "previous_sessions": [old_session_id] if old_session_id else [],
            "memory_size": len(memory)
        }

    except Exception as e:
        print(f"  ✗ {aid} → {model} FAILED: {e}")
        return {
            "id": aid,
            "model": model,
            "session_id": None,
            "seed": agent_cfg['seed'],
            "error": str(e),
            "launched_at": datetime.datetime.now().isoformat()
        }


def main():
    print("=" * 60)
    print("  Swarm Resurrector — Generation 2")
    print(f"  Time: {datetime.datetime.now().isoformat()}")
    print(f"  Agents: {len(AGENTS)}")
    print(f"  Concurrency: {MAX_CONCURRENT}")
    print("=" * 60)

    # 加载旧 session 映射
    old_sessions = {}
    if SESSIONS_FILE.exists():
        with open(SESSIONS_FILE) as f:
            old_data = json.load(f)
        for entry in old_data:
            old_sessions[entry['id']] = entry.get('session_id', '')

    # 扫描 commons 统计
    total_files = 0
    for subdir in ['tools', 'findings', 'data', 'challenges', 'builds']:
        d = SWARM / 'commons' / subdir
        if d.exists():
            total_files += len(list(d.iterdir()))

    print(f"\n  Phase 1 legacy: {total_files} files in commons/")
    print(f"  Old sessions: {len(old_sessions)}")
    print()

    # 确保 agents 目录存在
    for agent_cfg in AGENTS:
        agent_dir = SWARM / 'agents' / agent_cfg['id']
        agent_dir.mkdir(parents=True, exist_ok=True)

    # 逐批复活（不用 ThreadPoolExecutor 了，给 MASO 减压）
    results = []
    for i, agent_cfg in enumerate(AGENTS):
        aid = agent_cfg['id']
        old_sid = old_sessions.get(aid, '')

        print(f"[{i+1}/{len(AGENTS)}] Resurrecting {aid}...")
        result = resurrect_agent(agent_cfg, old_sid)
        results.append(result)

        # 每 MAX_CONCURRENT 个 agent 后暂停，让 MASO 处理
        if (i + 1) % MAX_CONCURRENT == 0:
            print(f"  ... waiting 5s for MASO to process batch ...")
            time.sleep(5)

    # 保存新 session 映射
    SESSIONS_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    ok = sum(1 for r in results if r.get('session_id'))
    fail = sum(1 for r in results if not r.get('session_id'))

    print(f"\n{'=' * 60}")
    print(f"  Generation 2 Launch Complete")
    print(f"  Resurrected: {ok}/{len(AGENTS)}")
    if fail:
        print(f"  Failed: {fail}")
        for r in results:
            if not r.get('session_id'):
                print(f"    - {r['id']}: {r.get('error', 'unknown')}")
    print(f"  Session map: {SESSIONS_FILE}")
    print(f"\n  Next: run swarm_compactor.py to prevent context exhaustion")
    print(f"         run swarm_monitor.py to keep agents active")
    print(f"         run swarm_reaper.py to cull inactive agents")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
