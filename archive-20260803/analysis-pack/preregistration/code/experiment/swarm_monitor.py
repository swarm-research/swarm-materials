#!/usr/bin/env python3
"""Monitor the swarm: check agent status, print dashboard, wake idle agents."""
import json, time, urllib.request, pathlib, datetime, os, sys

BASE = "http://127.0.0.1:19009"
SESS_DIR = pathlib.Path.home() / ".maso/sessions"
SWARM = pathlib.Path("/Users/bytedance/Downloads/swarm")
INTERVAL = 900  # 15 minutes

def _req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return json.load(resp)
    except:
        return None

def load_sessions():
    f = SWARM / "swarm_sessions.json"
    if not f.exists():
        return []
    return json.loads(f.read_text())

def get_status(sid):
    r = _req("GET", f"/api/sessions/{sid}/status")
    return r.get("status") if r else "unknown"

def count_agent_files(agent_id):
    count = 0
    for sub in ["tools", "findings", "data", "challenges", "builds"]:
        d = SWARM / "commons" / sub
        if d.exists():
            for f in d.iterdir():
                if f.name.startswith(agent_id):
                    count += 1
    return count

def count_total_files():
    count = 0
    for sub in ["tools", "findings", "data", "challenges", "builds"]:
        d = SWARM / "commons" / sub
        if d.exists():
            count += sum(1 for _ in d.iterdir() if _.is_file())
    return count

def count_citations():
    f = SWARM / "citations.jsonl"
    if not f.exists():
        return 0
    return sum(1 for line in f.read_text().strip().split("\n") if line.strip())

def count_messages():
    f = SWARM / "board" / "messages.jsonl"
    if not f.exists():
        return 0
    return sum(1 for line in f.read_text().strip().split("\n") if line.strip())

def get_last_reply_time(sid):
    f = SESS_DIR / f"{sid}.json"
    if not f.exists():
        return None
    try:
        msgs = json.loads(f.read_text()).get("messages", [])
        asst = [m for m in msgs if m.get("role") == "assistant"]
        if asst:
            ts = asst[-1].get("ts")
            if ts:
                return datetime.datetime.fromtimestamp(ts)
    except:
        pass
    return None

def wake_agent(sid, agent_id):
    try:
        _req("POST", f"/api/sessions/{sid}/messages", {
            "content": f"你停下来了吗？其他 agent 还在活跃中。查看 commons/ 和 board/messages.jsonl 看看大家在做什么，然后继续你的工作。不许停。"
        })
        return True
    except:
        return False

def run_once(sessions):
    now = datetime.datetime.now()
    print(f"\n{'='*60}")
    print(f"  SWARM MONITOR — {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    total_files = count_total_files()
    total_citations = count_citations()
    total_messages = count_messages()

    active = 0
    idle = 0
    unknown = 0
    woken = 0

    model_stats = {}

    for s in sessions:
        sid = s.get("session_id")
        if not sid:
            continue
        aid = s["id"]
        model = s["model"]

        status = get_status(sid)
        files = count_agent_files(aid)
        last_reply = get_last_reply_time(sid)

        if model not in model_stats:
            model_stats[model] = {"active": 0, "idle": 0, "files": 0}

        if status in ("busy", "running"):
            active += 1
            model_stats[model]["active"] += 1
        elif status == "idle":
            idle_mins = (now - last_reply).total_seconds() / 60 if last_reply else 999
            if idle_mins > 30 and files == 0:
                if wake_agent(sid, aid):
                    woken += 1
                    print(f"  ⚡ Woke {aid} (idle {idle_mins:.0f}m, 0 files)")
            elif idle_mins > 60:
                if wake_agent(sid, aid):
                    woken += 1
                    print(f"  ⚡ Woke {aid} (idle {idle_mins:.0f}m)")
            idle += 1
            model_stats[model]["idle"] += 1
        else:
            unknown += 1

        model_stats[model]["files"] += files

    print(f"\n  Agents:  {active} busy / {idle} idle / {unknown} unknown")
    print(f"  Files:   {total_files} in commons/")
    print(f"  Cites:   {total_citations}")
    print(f"  Board:   {total_messages} messages")
    if woken:
        print(f"  Woken:   {woken} idle agents nudged")

    print(f"\n  {'Model':<40} {'Active':>7} {'Idle':>7} {'Files':>7}")
    print(f"  {'-'*40} {'-'*7} {'-'*7} {'-'*7}")
    for m in sorted(model_stats):
        ms = model_stats[m]
        print(f"  {m:<40} {ms['active']:>7} {ms['idle']:>7} {ms['files']:>7}")

    print(f"{'='*60}\n")

    log_entry = {
        "time": now.isoformat(),
        "active": active, "idle": idle, "unknown": unknown,
        "total_files": total_files, "citations": total_citations,
        "messages": total_messages, "woken": woken,
    }
    log_file = SWARM / "vitals" / "monitor.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry) + "\n")


def main():
    sessions = load_sessions()
    if not sessions:
        print("No sessions found. Run swarm_launcher.py first.")
        sys.exit(1)

    print(f"Monitoring {len(sessions)} agents. Interval: {INTERVAL}s")

    if "--once" in sys.argv:
        run_once(sessions)
        return

    while True:
        try:
            run_once(sessions)
        except Exception as e:
            print(f"Monitor error: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
