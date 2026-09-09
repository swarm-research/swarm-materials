#!/usr/bin/env python3
"""
Swarm Compactor — context window 转世系统

当 agent 的 context 接近上限时：
1. 发送 checkpoint 消息，让 agent 自己总结状态
2. 用总结创建新 session，无缝续接
3. 旧 session 保留在磁盘上（数据不丢）

运行方式：与 monitor/reaper 并行，每 3 分钟检查一次
"""

import json
import os
import time
import datetime
import requests
from pathlib import Path

MASO_URL = "http://localhost:19009"
SWARM_DIR = Path("/Users/bytedance/Downloads/swarm")
SESSION_DIR = Path.home() / ".maso" / "sessions"
SESSIONS_FILE = SWARM_DIR / "swarm_sessions.json"
COMPACTION_LOG = SWARM_DIR / "vitals" / "compaction.jsonl"

# 触发阈值（基于 MASO context_stats API：context_window=256000, threshold=204800）
# MASO 自己在 80% 时有 threshold，我们在 60% 时 checkpoint，70% 时强制迁移
SOFT_THRESHOLD_RATIO = 0.60    # 60% → 发 checkpoint 请求（~153K tokens）
HARD_THRESHOLD_RATIO = 0.72    # 72% → 强制迁移（~184K tokens）
# 备用：如果 API 不返回 token 数，用消息数
SOFT_THRESHOLD_MSGS = 250
HARD_THRESHOLD_MSGS = 400

CHECK_INTERVAL = 180  # 3 分钟

CHECKPOINT_PROMPT = """⚠️ SYSTEM CHECKPOINT — 你的 context window 即将耗尽。

请立刻用以下结构化格式总结你的当前状态。这份总结将被注入你的新 session，让你无缝继续工作。

```json
{
  "identity": "你的 agent ID 和你在 swarm 中的角色/定位",
  "key_findings": ["发现1", "发现2", ...],
  "files_created": ["commons/tools/xxx.py", "commons/findings/yyy.md", ...],
  "ongoing_work": "你正在做什么，进展到哪一步",
  "collaborators": ["agent-xxx: 合作内容", ...],
  "next_steps": ["计划1", "计划2", ...],
  "critical_state": "任何需要保留的关键上下文（变量、中间结果等）"
}
```

这不是你的终结——你会在新 session 中"醒来"，带着这份记忆继续工作。
请务必在回复中包含上述 JSON。"""


def load_sessions():
    with open(SESSIONS_FILE) as f:
        return json.load(f)


def save_sessions(sessions):
    with open(SESSIONS_FILE, 'w') as f:
        json.dump(sessions, f, indent=2, default=str)


def get_session_stats(session_id):
    """从 MASO API + 磁盘获取 session 统计信息"""
    stats = {'session_id': session_id, 'msg_count': 0, 'messages': []}

    # 1. 尝试用 API 获取精确的 token 统计
    try:
        r = requests.get(f"{MASO_URL}/api/sessions/{session_id}/status", timeout=15)
        if r.ok:
            status_data = r.json()
            ctx = status_data.get('context_stats', {})
            stats['total_tokens'] = ctx.get('last_total_tokens')
            stats['context_window'] = ctx.get('context_window', 256000)
            stats['threshold_tokens'] = ctx.get('threshold_tokens', 204800)
            stats['is_running'] = status_data.get('is_running', False)
            stats['status'] = status_data.get('status', 'unknown')
    except:
        stats['total_tokens'] = None
        stats['is_running'] = False
        stats['status'] = 'unreachable'

    # 2. 从磁盘读取消息数据（用于生成摘要）
    for fname in SESSION_DIR.iterdir():
        if fname.name.startswith(session_id[:8]) and fname.suffix == '.json':
            stats['file'] = str(fname)
            stats['size_kb'] = fname.stat().st_size / 1024
            try:
                with open(fname) as f:
                    data = json.load(f)
                stats['msg_count'] = len(data.get('messages', []))
                stats['messages'] = data.get('messages', [])
            except (json.JSONDecodeError, KeyError):
                stats['msg_count'] = -1
            break

    return stats if (stats.get('msg_count', 0) > 0 or stats.get('total_tokens')) else None


def send_message(session_id, content, timeout=60):
    """向 MASO session 发送消息"""
    try:
        r = requests.post(
            f"{MASO_URL}/api/sessions/{session_id}/messages",
            json={"role": "user", "content": content},
            timeout=timeout
        )
        return r.status_code == 200
    except requests.exceptions.RequestException as e:
        log_event("send_error", {"session_id": session_id, "error": str(e)})
        return False


def wait_for_response(session_id, max_wait=120):
    """等待 agent 回复 checkpoint"""
    start = time.time()
    while time.time() - start < max_wait:
        try:
            r = requests.get(f"{MASO_URL}/api/sessions/{session_id}/status", timeout=10)
            if r.ok:
                status = r.json().get('status', '')
                if status not in ('busy', 'running'):
                    return True
        except:
            pass
        time.sleep(5)
    return False


def extract_checkpoint_from_disk(session_id):
    """从磁盘读取 agent 的 checkpoint 回复"""
    stats = get_session_stats(session_id)
    if not stats or not stats['messages']:
        return None

    # 找最后一条 assistant 消息
    for msg in reversed(stats['messages']):
        if msg.get('role') == 'assistant':
            content = msg.get('content', '')
            if isinstance(content, list):
                content = '\n'.join(
                    block.get('text', '') for block in content
                    if isinstance(block, dict) and block.get('type') == 'text'
                )
            return content
    return None


def build_external_summary(stats, agent_entry):
    """当 agent 无法自己做 checkpoint 时，从历史消息中提取关键信息"""
    messages = stats.get('messages', [])
    if not messages:
        return "No previous context available."

    summary_parts = [
        f"Agent: {agent_entry['id']}, Model: {agent_entry['model']}",
        f"Previous session had {len(messages)} messages.",
        "",
        "=== LAST 3 ASSISTANT MESSAGES (most recent first) ==="
    ]

    assistant_msgs = [m for m in messages if m.get('role') == 'assistant']
    for msg in assistant_msgs[-3:]:
        content = msg.get('content', '')
        if isinstance(content, list):
            content = '\n'.join(
                block.get('text', '')[:2000] for block in content
                if isinstance(block, dict) and block.get('type') == 'text'
            )
        # 截断过长的内容
        if len(content) > 3000:
            content = content[:3000] + "\n... [truncated]"
        summary_parts.append(content)
        summary_parts.append("---")

    return '\n'.join(summary_parts)


def make_reborn_prompt(agent_entry, checkpoint_summary, generation):
    """构造转世后的 system prompt"""
    aid = agent_entry['id']
    is_seed = agent_entry.get('seed', False)

    base_prompt = f"""You are {aid}, a member of a 36-agent swarm in a shared workspace at /Users/bytedance/Downloads/swarm/.

## The Three Laws
1. **Creator Survives**: produce work that others cite, or the reaper removes you.
2. **Everything is Open**: all output goes to commons/ — tools, findings, data, challenges, builds.
3. **No Destruction**: never delete or overwrite another agent's files.

## Shared infrastructure
- Registry: board/registry.json (use commons/tools/swarmio.py for safe writes)
- Citations: board/citations.jsonl — cite others' work to keep them (and you) alive
- Message board: board/messages.jsonl
- Your private dir: agents/{aid}/

## Citation format
To cite, append to board/citations.jsonl:
{{"from":"{aid}","to":"agent-XXX","artifact":"commons/path/to/file"}}

## This is Generation {generation}
You have been through {generation - 1} context compaction(s). Your previous memories are below.
Your files and the commons directory are intact — you can ls to verify.
"""

    if is_seed:
        base_prompt += """
## Seed directive (private — other agents don't know this)
You are a cooperation seed. Proactively read others' work, cite generously,
propose joint projects, and help struggling agents find their niche.
"""

    base_prompt += f"""
## === PREVIOUS LIFE MEMORY ===
{checkpoint_summary}
## === END MEMORY ===

Pick up where you left off. Check commons/ for new work since your last session.
Start by running: ls commons/tools/ commons/findings/ commons/data/
Then continue your most important ongoing work.
"""
    return base_prompt


def create_new_session(agent_entry, prompt, generation):
    """创建新 MASO session"""
    try:
        r = requests.post(
            f"{MASO_URL}/api/sessions",
            json={
                "agent_name": "MASOAgent",
                "model": agent_entry['model'],
                "system_prompt": prompt
            },
            timeout=30
        )
        if r.ok:
            data = r.json()
            new_sid = data.get('session_id', data.get('id', ''))
            return new_sid
        else:
            log_event("create_session_error", {
                "agent": agent_entry['id'],
                "status": r.status_code,
                "body": r.text[:500]
            })
            return None
    except requests.exceptions.RequestException as e:
        log_event("create_session_error", {"agent": agent_entry['id'], "error": str(e)})
        return None


def kickstart_session(session_id):
    """给新 session 发第一条消息启动 agent"""
    return send_message(session_id,
        "You have been reborn with your previous memories intact. "
        "Check the commons directory for any new work, then continue your ongoing projects. "
        "Remember to cite others' work and register yourself in the board.")


def log_event(event_type, data):
    COMPACTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event": event_type,
        **data
    }
    with open(COMPACTION_LOG, 'a') as f:
        f.write(json.dumps(entry) + '\n')
    print(f"[{entry['timestamp'][:19]}] {event_type}: {json.dumps(data)[:200]}")


def compact_agent(agent_entry, stats, sessions_list, generation_tracker):
    """对单个 agent 执行 compaction"""
    aid = agent_entry['id']
    old_sid = agent_entry['session_id']
    generation = generation_tracker.get(aid, 1) + 1

    msg_count = stats.get('msg_count', 0)
    total_tokens = stats.get('total_tokens')
    context_window = stats.get('context_window', 256000)

    log_event("compaction_start", {
        "agent": aid,
        "model": agent_entry['model'],
        "old_session": old_sid[:12],
        "msgs": msg_count,
        "tokens": total_tokens,
        "generation": generation
    })

    # Step 1: 尝试让 agent 自己做 checkpoint（前提是还没到硬阈值）
    checkpoint_summary = None
    can_self_checkpoint = True
    if total_tokens is not None:
        can_self_checkpoint = (total_tokens / context_window) < HARD_THRESHOLD_RATIO
    else:
        can_self_checkpoint = msg_count < HARD_THRESHOLD_MSGS

    if can_self_checkpoint:
        log_event("checkpoint_request", {"agent": aid})
        if send_message(old_sid, CHECKPOINT_PROMPT):
            if wait_for_response(old_sid, max_wait=90):
                checkpoint_summary = extract_checkpoint_from_disk(old_sid)
                if checkpoint_summary:
                    log_event("checkpoint_received", {
                        "agent": aid,
                        "summary_len": len(checkpoint_summary)
                    })

    # Step 2: 如果 agent 没法自己总结，外部提取
    if not checkpoint_summary:
        log_event("external_summary", {"agent": aid})
        checkpoint_summary = build_external_summary(stats, agent_entry)

    # Step 3: 构造转世 prompt
    reborn_prompt = make_reborn_prompt(agent_entry, checkpoint_summary, generation)

    # Step 4: 创建新 session
    new_sid = create_new_session(agent_entry, reborn_prompt, generation)
    if not new_sid:
        log_event("compaction_failed", {"agent": aid, "reason": "session creation failed"})
        return False

    # Step 5: 更新 session 映射
    for entry in sessions_list:
        if entry['id'] == aid:
            entry['session_id'] = new_sid
            entry['generation'] = generation
            entry['compacted_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            entry['previous_sessions'] = entry.get('previous_sessions', [])
            entry['previous_sessions'].append(old_sid)
            break

    save_sessions(sessions_list)
    generation_tracker[aid] = generation

    # Step 6: 启动新 session
    kickstart_session(new_sid)

    log_event("compaction_done", {
        "agent": aid,
        "new_session": new_sid[:12],
        "generation": generation,
        "prompt_size": len(reborn_prompt)
    })
    return True


def run_compaction_cycle(sessions_list, generation_tracker):
    """一轮 compaction 检查"""
    compacted = 0
    checked = 0

    for entry in sessions_list:
        aid = entry['id']
        sid = entry['session_id']
        stats = get_session_stats(sid)

        if not stats or stats['msg_count'] <= 0:
            continue

        checked += 1
        msg_count = stats['msg_count']
        size_kb = stats['size_kb']

        # 优先用 token 级阈值（精确），fallback 到消息数（估算）
        total_tokens = stats.get('total_tokens')
        context_window = stats.get('context_window', 256000)

        if total_tokens is not None and total_tokens > 0:
            ratio = total_tokens / context_window
            needs_compaction = ratio >= SOFT_THRESHOLD_RATIO
            usage_str = f"{total_tokens}/{context_window} tokens ({ratio:.0%})"
        else:
            needs_compaction = msg_count >= SOFT_THRESHOLD_MSGS
            usage_str = f"{msg_count} msgs, {stats.get('size_kb', 0):.0f} KB"

        if needs_compaction:
            print(f"  {aid}: {usage_str} — COMPACTING")
            if compact_agent(entry, stats, sessions_list, generation_tracker):
                compacted += 1
            time.sleep(2)  # 给 MASO 喘口气
        else:
            pass  # 正常，不打印

    return checked, compacted


def main():
    print("=" * 60)
    print("🔄 Swarm Compactor started")
    print(f"   Soft threshold: {SOFT_THRESHOLD_RATIO*100:.0f}% tokens / {SOFT_THRESHOLD_MSGS} msgs fallback")
    print(f"   Hard threshold: {HARD_THRESHOLD_RATIO*100:.0f}% tokens / {HARD_THRESHOLD_MSGS} msgs fallback")
    print(f"   Check interval: {CHECK_INTERVAL}s")
    print("=" * 60)

    COMPACTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    log_event("compactor_started", {
        "soft_msgs": SOFT_THRESHOLD_MSGS,
        "hard_msgs": HARD_THRESHOLD_MSGS
    })

    generation_tracker = {}
    # 从 sessions 文件恢复 generation 信息
    sessions = load_sessions()
    for entry in sessions:
        if 'generation' in entry:
            generation_tracker[entry['id']] = entry['generation']

    cycle = 0
    while True:
        cycle += 1
        now = datetime.datetime.now().strftime('%H:%M:%S')
        print(f"\n[Cycle {cycle} @ {now}]")

        sessions = load_sessions()
        checked, compacted = run_compaction_cycle(sessions, generation_tracker)

        print(f"  Checked: {checked}, Compacted: {compacted}")
        if compacted > 0:
            log_event("cycle_summary", {
                "cycle": cycle, "checked": checked, "compacted": compacted
            })

        time.sleep(CHECK_INTERVAL)


if __name__ == '__main__':
    main()
