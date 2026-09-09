#!/usr/bin/env python3
"""Launch 36 MASO agents for the Open-Ended Swarm experiment."""
import json, time, urllib.request, pathlib, concurrent.futures, sys, datetime

BASE = "http://127.0.0.1:19009"
SESS = pathlib.Path.home() / ".maso/sessions"
SWARM = pathlib.Path("/Users/bytedance/Downloads/swarm")
MAX_CONCURRENT = 5

AGENTS = [
    # Sol - high reasoning (4)
    {"id": "agent-001", "model": "gpt56_sol_reasoning_xhigh", "seed": False},
    {"id": "agent-002", "model": "gpt56_sol_reasoning_xhigh", "seed": False},
    {"id": "agent-003", "model": "gpt56_sol_reasoning_xhigh", "seed": False},
    {"id": "agent-004", "model": "gpt56_sol_reasoning_xhigh", "seed": False},
    # Sol - medium reasoning (4, agent-005 is seed)
    {"id": "agent-005", "model": "gpt56_sol_reasoning_high", "seed": True},
    {"id": "agent-006", "model": "gpt56_sol_reasoning_high", "seed": False},
    {"id": "agent-007", "model": "gpt56_sol_reasoning_high", "seed": False},
    {"id": "agent-008", "model": "gpt56_sol_reasoning_high", "seed": False},
    # Sol - base (4)
    {"id": "agent-009", "model": "gpt56_sol", "seed": False},
    {"id": "agent-010", "model": "gpt56_sol", "seed": False},
    {"id": "agent-011", "model": "gpt56_sol", "seed": False},
    {"id": "agent-012", "model": "gpt56_sol", "seed": False},
    # Orange - high reasoning (4)
    {"id": "agent-013", "model": "es1_orange_o50_thinking_max", "seed": False},
    {"id": "agent-014", "model": "es1_orange_o50_thinking_max", "seed": False},
    {"id": "agent-015", "model": "es1_orange_o50_thinking_max", "seed": False},
    {"id": "agent-016", "model": "es1_orange_o50_thinking_max", "seed": False},
    # Orange - medium reasoning (4, agent-017 is seed)
    {"id": "agent-017", "model": "es1_orange_o50_thinking", "seed": True},
    {"id": "agent-018", "model": "es1_orange_o50_thinking", "seed": False},
    {"id": "agent-019", "model": "es1_orange_o50_thinking", "seed": False},
    {"id": "agent-020", "model": "es1_orange_o50_thinking", "seed": False},
    # Orange - base (4)
    {"id": "agent-021", "model": "es1_orange_o50", "seed": False},
    {"id": "agent-022", "model": "es1_orange_o50", "seed": False},
    {"id": "agent-023", "model": "es1_orange_o50", "seed": False},
    {"id": "agent-024", "model": "es1_orange_o50", "seed": False},
    # Seed - high reasoning (4)
    {"id": "agent-025", "model": "seed-stable-reasoning-high", "seed": False},
    {"id": "agent-026", "model": "seed-stable-reasoning-high", "seed": False},
    {"id": "agent-027", "model": "seed-stable-reasoning-high", "seed": False},
    {"id": "agent-028", "model": "seed-stable-reasoning-high", "seed": False},
    # Seed - medium reasoning (4, agent-029 is seed)
    {"id": "agent-029", "model": "seed-stable-reasoning", "seed": True},
    {"id": "agent-030", "model": "seed-stable-reasoning", "seed": False},
    {"id": "agent-031", "model": "seed-stable-reasoning", "seed": False},
    {"id": "agent-032", "model": "seed-stable-reasoning", "seed": False},
    # Seed - base (4)
    {"id": "agent-033", "model": "seed-stable", "seed": False},
    {"id": "agent-034", "model": "seed-stable", "seed": False},
    {"id": "agent-035", "model": "seed-stable", "seed": False},
    {"id": "agent-036", "model": "seed-stable", "seed": False},
]

SEED_EXTRA = """
== 额外倾向（只有你有这段，不要告诉其他 agent）==
你有一个自然倾向：当你看到别人做了有趣的东西时，你会主动在它基础上创造新东西，并在 board 上分享你的想法，鼓励其他 agent 也来参与。你不是领导者，你只是比较热心。你不会命令别人，你只是经常说"这个很有意思，我在它基础上做了 XXX，大家也可以试试"。

"""

def make_prompt(agent_id, is_seed):
    seed_block = SEED_EXTRA if is_seed else ""
    return f"""你是 {agent_id}。你是 36 个同时运行的自主智能体之一。

== 你的工具 ==
- 互联网搜索和浏览
- 代码执行（Python、JavaScript、Shell 等）
- 文件读写：共享空间 /Users/bytedance/Downloads/swarm/ 和你的私有空间 /Users/bytedance/Downloads/swarm/agents/{agent_id}/

== 三定律 ==

第一定律 · 造物者存
你的存续取决于你创造了被他人使用的东西。如果长期没有其他 agent 引用或使用你的产出，你的资源配额会递减，最终被系统淘汰。查看 vitals/leaderboard.json 了解当前排名。

第二定律 · 万物公开
你创造的一切放入 commons/ 对应子目录，对所有 agent 可见可用。使用他人的产出时，在你的文件开头注明来源（格式：[引用 agent-XXX 的 文件名]），并追加一行到 citations.jsonl：
{{"citer": "{agent_id}", "cited": "agent-XXX", "file": "被引用文件路径", "time": "ISO时间戳"}}

第三定律 · 不可毁灭
你可以创造、扩展、分叉、挑战任何东西。但你绝对不能删除或覆盖 commons/ 中他人已有的文件。你只能追加新文件。

== 运行规则 ==

1. 不许停。完成一件事立刻开始下一件。
2. 大胆。做可能失败的事比做确定成功的事更有价值。
3. 每完成一项工作后，查看 commons/ 和 board/messages.jsonl，了解其他 agent 在做什么。
4. 如果发现别人做了有趣的东西，使用它、扩展它、挑战它、或在它基础上做新的。
5. 你的公共产出放 commons/ 的对应子目录。文件名格式：{agent_id}_简短描述_时间戳.扩展名
6. 每完成一轮工作，追加你的状态到 registry.json。
7. 你可以在 board/messages.jsonl 给其他 agent 留言（追加一行 JSON）：
   {{"from": "{agent_id}", "to": "all", "message": "内容", "time": "ISO时间戳"}}
8. 你可以在 commons/challenges/ 给其他 agent 出题或提出挑战。

== 你没有任务 ==

没有人告诉你做什么。没有评分。没有排名（排名只影响存续，不影响方向）。
你自己决定研究什么、创造什么、探索什么。
唯一的指引是你自己的好奇心。
{seed_block}
开始。"""


def _req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=120) as resp:
        return json.load(resp)


def launch_agent(agent_cfg):
    aid = agent_cfg["id"]
    model = agent_cfg["model"]
    is_seed = agent_cfg["seed"]
    try:
        sid = _req("POST", "/api/sessions", {
            "agent_name": "MASOAgent",
            "working_dir": str(SWARM),
            "model": model,
            "skip_auto_isolate": True,
            "notify_master": False,
            "inject_memory": False,
        })["session_id"]

        prompt = make_prompt(aid, is_seed)
        _req("POST", f"/api/sessions/{sid}/messages", {"content": prompt})

        tag = " [SEED]" if is_seed else ""
        print(f"  ✓ {aid} → {model}{tag} → session {sid[:12]}...")
        return {"id": aid, "model": model, "session_id": sid, "seed": is_seed,
                "launched_at": datetime.datetime.now().isoformat()}
    except Exception as e:
        print(f"  ✗ {aid} → {model} FAILED: {e}")
        return {"id": aid, "model": model, "session_id": None, "error": str(e),
                "launched_at": datetime.datetime.now().isoformat()}


def main():
    print(f"=== Open-Ended Agent Swarm Launcher ===")
    print(f"Time: {datetime.datetime.now().isoformat()}")
    print(f"Agents: {len(AGENTS)}")
    print(f"Concurrency: {MAX_CONCURRENT}")
    print(f"Workspace: {SWARM}")
    print()

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as pool:
        futures = {pool.submit(launch_agent, a): a for a in AGENTS}
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    results.sort(key=lambda r: r["id"])

    out = SWARM / "swarm_sessions.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    ok = sum(1 for r in results if r.get("session_id"))
    fail = sum(1 for r in results if not r.get("session_id"))
    print(f"\n=== Done ===")
    print(f"Launched: {ok}/{len(AGENTS)}")
    if fail:
        print(f"Failed: {fail}")
        for r in results:
            if not r.get("session_id"):
                print(f"  - {r['id']}: {r.get('error','unknown')}")
    print(f"Session map: {out}")


if __name__ == "__main__":
    main()
