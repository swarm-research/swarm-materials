#!/usr/bin/env python3
"""Reaper: cull inactive agents based on citation + output vitality."""
import json, time, pathlib, datetime, sys

SWARM = pathlib.Path("/Users/bytedance/Downloads/swarm")
WARMUP_HOURS = 1          # Phase 2: agents 带着 P1 记忆，1h 足够热身
CYCLE_SECONDS = 1800       # Phase 2: 每 30min 检查
LOOKBACK_HOURS = 2         # Phase 2: 最近 2h 的活动
ALLIANCE_THRESHOLD = 3     # Phase 2: >= 3 个不同 agent 引用 = 豁免

def parse_ts(s):
    """Parse ISO timestamps including Z suffix (Python 3.9 compat)."""
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        return datetime.datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None

def load_sessions():
    f = SWARM / "swarm_sessions.json"
    return json.loads(f.read_text()) if f.exists() else []

def get_citations_since(cutoff):
    f = SWARM / "citations.jsonl"
    if not f.exists():
        return {}, {}
    counts = {}
    distinct_citers = {}
    # Make cutoff naive for comparison (strip tz)
    cutoff_naive = cutoff.replace(tzinfo=None)
    for line in f.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            c = json.loads(line)
            t = parse_ts(c.get("time", ""))
            if t is None:
                continue
            # Compare as naive (both stripped to local-equivalent)
            t_naive = t.replace(tzinfo=None)
            if t_naive >= cutoff_naive:
                cited = c.get("cited", "")
                citer = c.get("citer", c.get("from", ""))
                counts[cited] = counts.get(cited, 0) + 1
                if cited not in distinct_citers:
                    distinct_citers[cited] = set()
                if citer and citer != cited:
                    distinct_citers[cited].add(citer)
        except Exception:
            continue
    return counts, distinct_citers

def get_total_citations():
    f = SWARM / "citations.jsonl"
    if not f.exists():
        return {}
    counts = {}
    for line in f.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            c = json.loads(line)
            cited = c.get("cited", "")
            counts[cited] = counts.get(cited, 0) + 1
        except:
            continue
    return counts

def get_outputs_since(agent_id, cutoff):
    count = 0
    cutoff_ts = cutoff.timestamp()
    for sub in ["tools", "findings", "data", "challenges", "builds"]:
        d = SWARM / "commons" / sub
        if not d.exists():
            continue
        for f in d.iterdir():
            if f.name.startswith(agent_id) and f.stat().st_mtime >= cutoff_ts:
                count += 1
    return count

def load_warnings():
    f = SWARM / "vitals" / "reaper_state.json"
    if f.exists():
        return json.loads(f.read_text())
    return {}

def save_warnings(state):
    f = SWARM / "vitals" / "reaper_state.json"
    f.write_text(json.dumps(state, indent=2))

def log_reaper(entry):
    f = SWARM / "vitals" / "reaper.log"
    with open(f, "a") as fp:
        fp.write(json.dumps(entry) + "\n")

def post_board(msg):
    f = SWARM / "board" / "messages.jsonl"
    entry = {"from": "REAPER", "to": "all", "message": msg,
             "time": datetime.datetime.now().isoformat()}
    with open(f, "a") as fp:
        fp.write(json.dumps(entry) + "\n")

def update_leaderboard(total_cites, alive_agents):
    board = []
    for aid in alive_agents:
        board.append({"agent": aid, "citations": total_cites.get(aid, 0)})
    board.sort(key=lambda x: -x["citations"])
    f = SWARM / "vitals" / "leaderboard.json"
    f.write_text(json.dumps(board, indent=2))

def run_reaper(sessions, start_time):
    now = datetime.datetime.now()
    elapsed = (now - start_time).total_seconds() / 3600

    if elapsed < WARMUP_HOURS:
        remaining = WARMUP_HOURS - elapsed
        print(f"[Reaper] Warmup period: {remaining:.1f}h remaining. Skipping.")
        return

    cutoff = now - datetime.timedelta(hours=LOOKBACK_HOURS)
    recent_cites, distinct_citers = get_citations_since(cutoff)
    total_cites = get_total_citations()
    state = load_warnings()
    killed = set(state.get("killed", []))
    alive = []
    alliances = []

    print(f"\n[Reaper] Cycle at {now.strftime('%H:%M:%S')}")
    print(f"  Lookback: {LOOKBACK_HOURS}h from {cutoff.strftime('%H:%M')}")

    for s in sessions:
        aid = s["id"]
        sid = s.get("session_id")
        if not sid or aid in killed:
            continue

        cites = recent_cites.get(aid, 0)
        outputs = get_outputs_since(aid, cutoff)
        vitality = cites + outputs
        n_distinct = len(distinct_citers.get(aid, set()))

        # Phase 2: 联盟保护
        if n_distinct >= ALLIANCE_THRESHOLD:
            if aid in state:
                del state[aid]
            alive.append(aid)
            alliances.append(aid)
            print(f"  🛡️  {aid}: ALLIANCE PROTECTION ({n_distinct} distinct citers)")
            log_reaper({"type": "alliance_protection", "agent": aid,
                        "distinct_citers": n_distinct, "time": now.isoformat()})
            continue

        if vitality > 0:
            if aid in state:
                del state[aid]
            alive.append(aid)
            continue

        current = state.get(aid, "ok")

        if current == "ok":
            state[aid] = "warned"
            log_reaper({"type": "warning", "agent": aid, "time": now.isoformat()})
            print(f"  ⚠️  {aid}: WARNING (0 vitality)")
            alive.append(aid)

        elif current == "warned":
            state[aid] = "throttled"
            log_reaper({"type": "throttle", "agent": aid, "time": now.isoformat()})
            print(f"  🔻 {aid}: THROTTLED")
            alive.append(aid)

        elif current == "throttled":
            killed.add(aid)
            state["killed"] = list(killed)
            if aid in state:
                del state[aid]
            log_reaper({"type": "killed", "agent": aid, "time": now.isoformat()})
            print(f"  💀 {aid}: KILLED")
        else:
            alive.append(aid)

    save_warnings(state)
    update_leaderboard(total_cites, alive)
    print(f"  Alive: {len(alive)} / Killed: {len(killed)}")


def main():
    start_time = datetime.datetime.now()
    print(f"[Reaper] Started at {start_time.isoformat()}")
    print(f"  Warmup: {WARMUP_HOURS}h, Cycle: {CYCLE_SECONDS}s, Lookback: {LOOKBACK_HOURS}h")

    if "--once" in sys.argv:
        sessions = load_sessions()
        if not sessions:
            print("No sessions found.")
            sys.exit(1)
        run_reaper(sessions, start_time - datetime.timedelta(hours=WARMUP_HOURS + 1))
        return

    while True:
        try:
            sessions = load_sessions()
            if sessions:
                run_reaper(sessions, start_time)
            else:
                print("[Reaper] No sessions found, retrying next cycle.")
        except Exception as e:
            print(f"[Reaper] Error: {e}")
            import traceback
            traceback.print_exc()
        time.sleep(CYCLE_SECONDS)


if __name__ == "__main__":
    main()
