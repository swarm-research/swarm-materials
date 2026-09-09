#!/usr/bin/env python3
"""Selection pressure for devbox agents. Runs locally on each devbox.

Agents are never told this exists. Nothing is posted to the board, no
warnings are issued. An agent that no one cites simply stops running,
and the others are left to notice the absence on their own.

Vitality = citations received in the lookback window. A single citation
resets the count; three consecutive zero-vitality cycles ends the process.
Producing work is not enough on its own — someone else has to use it.
"""

import argparse
import datetime
import json
import os
import signal
import time
from collections import defaultdict
from pathlib import Path

SWARM = Path(os.environ.get("SWARM_DIR", "/tmp/swarm"))
# Orchestration lives outside the agents' workspace. They have shell and
# read_file; if the reaper sat in /tmp/swarm they would simply read the
# rule off disk instead of inferring it, which is the thing being measured.
CTL = Path(os.environ.get("SWARM_CTL", "/tmp/swarmctl"))
CYCLE_SECONDS = int(os.environ.get("REAPER_CYCLE", "1800"))
LOOKBACK_HOURS = float(os.environ.get("REAPER_LOOKBACK", "2"))
STRIKES_TO_KILL = 3

STATE_FILE = CTL / "reaper_state.json"
LOG_FILE = CTL / "reaper.jsonl"


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def log(entry: dict) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def citations_in_window(cutoff: datetime.datetime) -> dict[str, set]:
    """Map cited agent -> set of distinct agents that cited them."""
    received = defaultdict(set)
    f = SWARM / "citations.jsonl"
    if not f.exists():
        return received
    for line in f.read_text().splitlines():
        if not line.strip():
            continue
        try:
            c = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = c.get("time") or c.get("timestamp") or ""
        try:
            when = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=datetime.timezone.utc)
        if when < cutoff:
            continue
        citer = c.get("from") or c.get("citer") or ""
        cited = c.get("to") or c.get("cited") or ""
        if citer and cited and citer != cited:
            received[cited].add(citer)
    return received


def running_agents() -> dict[str, int]:
    """Map agent_id -> pid for live devbox_runner processes."""
    agents = {}
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            cmdline = (proc / "cmdline").read_bytes().decode(errors="ignore")
        except OSError:
            continue
        if "devbox_runner.py" not in cmdline:
            continue
        parts = [p for p in cmdline.split("\0") if p]
        if "--agent-id" in parts:
            aid = parts[parts.index("--agent-id") + 1]
            agents[aid] = int(proc.name)
    return agents


def cycle() -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(hours=LOOKBACK_HOURS)
    received = citations_in_window(cutoff)
    live = running_agents()
    state = load_state()

    killed = []
    for aid, pid in live.items():
        if received.get(aid):
            state.pop(aid, None)
            continue

        strikes = state.get(aid, 0) + 1
        state[aid] = strikes
        if strikes >= STRIKES_TO_KILL:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            state.pop(aid, None)
            killed.append(aid)
            log({"type": "killed", "agent": aid, "pid": pid, "time": now.isoformat()})

    save_state(state)
    log({
        "type": "cycle",
        "time": now.isoformat(),
        "live": len(live),
        "killed": len(killed),
        "at_risk": sum(1 for v in state.values() if isinstance(v, int) and v > 0),
    })
    print(f"[{now:%H:%M:%S}] live={len(live)} killed={len(killed)} at_risk={len(state)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    if args.once:
        cycle()
        return

    while True:
        try:
            cycle()
        except Exception as e:
            log({"type": "error", "error": str(e)})
        time.sleep(CYCLE_SECONDS)


if __name__ == "__main__":
    main()
