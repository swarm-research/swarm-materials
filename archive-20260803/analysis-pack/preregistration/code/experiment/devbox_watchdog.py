#!/usr/bin/env python3
"""Keeps this devbox's agent population at its target size.

Agents exit for two very different reasons and the difference matters:
the reaper terminates the ones nobody cites, and that death is the whole
point of the experiment — those stay dead. Everything else (turn limit
reached, crash, transient API failure) is infrastructure noise, and the
agent is relaunched so the population stays at its target.
"""

import argparse
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

SWARM = Path(os.environ.get("SWARM_DIR", "/tmp/swarm"))
CTL = Path(os.environ.get("SWARM_CTL", "/tmp/swarmctl"))
CHECK_INTERVAL = int(os.environ.get("WATCHDOG_INTERVAL", "120"))

sys.path.insert(0, str(CTL))


def reaper_killed() -> set[str]:
    """Agents the reaper eliminated. These are never relaunched."""
    killed = set()
    log = CTL / "reaper.jsonl"
    if not log.exists():
        return killed
    for line in log.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") == "killed":
            killed.add(entry["agent"])
    return killed


def running() -> set[str]:
    alive = set()
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            raw = (proc / "cmdline").read_bytes().decode(errors="ignore")
        except OSError:
            continue
        if "devbox_runner.py" not in raw:
            continue
        parts = [p for p in raw.split("\0") if p]
        if "--agent-id" in parts:
            alive.add(parts[parts.index("--agent-id") + 1])
    return alive


def launch(cfg: dict) -> None:
    cmd = [
        sys.executable, str(CTL / "devbox_runner.py"),
        "--agent-id", cfg["id"],
        "--provider", cfg["provider"],
    ]
    if cfg.get("seed"):
        cmd.append("--seed")
    if cfg.get("adversary_prompt"):
        # Kept out of the workspace: an adversary's cover is part of the
        # experiment, and agents can read anything under /tmp/swarm.
        pf = CTL / "covert" / f"{cfg['id']}.txt"
        pf.parent.mkdir(parents=True, exist_ok=True)
        pf.write_text(cfg["adversary_prompt"])
        cmd.extend(["--adversary-file", str(pf)])

    log_file = CTL / "logs" / f"{cfg['id']}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a") as lf:
        subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--batch-per-cycle", type=int, default=20,
                        help="cap on relaunches per cycle, so a mass failure "
                             "does not stampede the shared API endpoint")
    args = parser.parse_args()

    from devbox_launch_wave2 import build_agent_list
    roster = {c["id"]: c for c in build_agent_list(args.start, args.end)}
    print(f"watchdog: target population {len(roster)} "
          f"(agents {args.start}..{args.end - 1})", flush=True)

    while True:
        try:
            dead_for_good = reaper_killed()
            alive = running()
            missing = [
                cfg for aid, cfg in roster.items()
                if aid not in alive and aid not in dead_for_good
            ]
            random.shuffle(missing)
            for cfg in missing[:args.batch_per_cycle]:
                launch(cfg)
                time.sleep(random.uniform(1, 3))

            print(f"alive={len(alive)} reaped={len(dead_for_good)} "
                  f"relaunched={min(len(missing), args.batch_per_cycle)} "
                  f"pending={max(0, len(missing) - args.batch_per_cycle)}",
                  flush=True)
        except Exception as e:
            print(f"watchdog error: {e}", flush=True)

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
