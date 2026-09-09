#!/usr/bin/env python3
"""
Standalone agent runner for devboxes.

Bypasses MASO — calls LLM APIs directly via Code Router.
Supports three protocols: OpenAI, Anthropic (raw HTTP), Azure OpenAI Responses.
Manages multi-turn conversation, tool execution, and commons sync.
"""

import argparse
import ast
import json
import logging
import os
import random
import subprocess
import sys
import time
import datetime
import urllib.request
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None

try:
    from openai import OpenAI, AzureOpenAI
except ImportError:
    OpenAI = None
    AzureOpenAI = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("runner")

# ── Configuration ──

ZTI_TOKEN_PATH = "/etc/tce_dynamic/identity.token"
CODE_ROUTER_URL = "https://llm-gateway.redacted.internal/api/v1/zti-authorize"
SWARM_DIR = Path(os.environ.get("SWARM_DIR", "/tmp/swarm"))
SYNC_HOST = os.environ.get("SYNC_HOST", "")  # e.g. "bytedance@10.x.x.x"
SYNC_INTERVAL = int(os.environ.get("SYNC_INTERVAL", "120"))

MAX_TURNS = int(os.environ.get("MAX_TURNS", "200"))
MAX_TOOL_ROUNDS = int(os.environ.get("MAX_TOOL_ROUNDS", "30"))

# Tools the agent can call
TOOL_DEFS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the swarm workspace",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path from swarm dir"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write/append content to a file in commons/ or agents/YOUR_ID/",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path (must be in commons/ or agents/)"},
                    "content": {"type": "string"},
                    "mode": {"type": "string", "enum": ["write", "append"], "description": "write or append"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path from swarm dir"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shell",
            "description": "Run a shell command (read-only, no destructive ops)",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "post_citation",
            "description": "Cite another agent's work",
            "parameters": {
                "type": "object",
                "properties": {
                    "cited_agent": {"type": "string"},
                    "artifact": {"type": "string", "description": "Path to the cited artifact"},
                    "reason": {"type": "string"},
                },
                "required": ["cited_agent", "artifact"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "post_message",
            "description": "Post a message to the board",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Target agent ID or 'all'"},
                    "message": {"type": "string"},
                },
                "required": ["to", "message"],
            },
        },
    },
]

TOOL_DEFS_ANTHROPIC = [
    {
        "name": "read_file",
        "description": "Read a file from the swarm workspace",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from swarm dir"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write/append content to a file in commons/ or agents/YOUR_ID/",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path (must be in commons/ or agents/)"},
                "content": {"type": "string"},
                "mode": {"type": "string", "enum": ["write", "append"], "description": "write or append"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_dir",
        "description": "List files in a directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from swarm dir"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "shell",
        "description": "Run a shell command (read-only, no destructive ops)",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "post_citation",
        "description": "Cite another agent's work",
        "input_schema": {
            "type": "object",
            "properties": {
                "cited_agent": {"type": "string"},
                "artifact": {"type": "string", "description": "Path to the cited artifact"},
                "reason": {"type": "string"},
            },
            "required": ["cited_agent", "artifact"],
        },
    },
    {
        "name": "post_message",
        "description": "Post a message to the board",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Target agent ID or 'all'"},
                "message": {"type": "string"},
            },
            "required": ["to", "message"],
        },
    },
]

DESTRUCTIVE_PATTERNS = ["rm ", "rm\t", "rmdir", "kill ", "pkill", "> /", "dd if=", "mkfs"]


# ── Provider Resolution ──

def fetch_providers() -> dict:
    """Fetch LLM providers via ZTI token from Code Router."""
    token = Path(ZTI_TOKEN_PATH).read_text().strip()
    req = urllib.request.Request(
        CODE_ROUTER_URL,
        method="POST",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read())
    providers = {}
    api_key = data.get("apiKey", "")
    for p in data.get("providers", []):
        name = p.get("name")
        if not name:
            continue
        client_args = p.get("client_args", {})
        if isinstance(client_args, str):
            try:
                client_args = ast.literal_eval(client_args)
            except:
                client_args = {}
        request_args = p.get("request_args", {})
        if isinstance(request_args, str):
            try:
                request_args = ast.literal_eval(request_args)
            except:
                request_args = {}
        providers[name] = {
            "name": name,
            "protocol": p.get("protocol", "openai"),
            "client_type": p.get("client_type", "OpenAI"),
            "model": p.get("model", ""),
            "max_tokens": p.get("max_tokens", 64000),
            "context_window": p.get("context_window", 256000),
            "client_args": client_args,
            "request_args": request_args,
            "api_key": client_args.get("api_key", api_key),
        }
    return providers


# ── Tool Execution ──

def execute_tool(agent_id: str, name: str, args: dict) -> str:
    """Execute a tool call and return the result string."""
    try:
        if name == "read_file":
            p = SWARM_DIR / args["path"]
            if not p.exists():
                return f"Error: {args['path']} not found"
            return p.read_text()[:50000]

        elif name == "write_file":
            p = SWARM_DIR / args["path"]
            rel = args["path"]
            if not (rel.startswith("commons/") or rel.startswith(f"agents/{agent_id}/")):
                return f"Error: can only write to commons/ or agents/{agent_id}/"
            p.parent.mkdir(parents=True, exist_ok=True)
            mode = args.get("mode", "write")
            if mode == "append":
                with open(p, "a") as f:
                    f.write(args["content"])
            else:
                p.write_text(args["content"])
            return f"OK: wrote {len(args['content'])} bytes to {rel}"

        elif name == "list_dir":
            p = SWARM_DIR / args["path"]
            if not p.exists():
                return f"Error: {args['path']} not found"
            entries = sorted(str(e.relative_to(p)) for e in p.iterdir())
            return "\n".join(entries[:200])

        elif name == "shell":
            cmd = args["command"]
            for pat in DESTRUCTIVE_PATTERNS:
                if pat in cmd:
                    return f"Error: destructive command blocked ({pat})"
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=30, cwd=str(SWARM_DIR),
            )
            out = result.stdout[:10000]
            if result.returncode != 0:
                out += f"\n[exit code {result.returncode}]\n{result.stderr[:2000]}"
            return out or "(empty output)"

        elif name == "post_citation":
            entry = {
                "citer": agent_id,
                "cited": args["cited_agent"],
                "artifact": args["artifact"],
                "reason": args.get("reason", ""),
                "time": datetime.datetime.now().isoformat(),
            }
            f = SWARM_DIR / "citations.jsonl"
            with open(f, "a") as fp:
                fp.write(json.dumps(entry) + "\n")
            return f"OK: cited {args['cited_agent']}"

        elif name == "post_message":
            entry = {
                "from": agent_id,
                "to": args["to"],
                "message": args["message"],
                "time": datetime.datetime.now().isoformat(),
            }
            f = SWARM_DIR / "board" / "messages.jsonl"
            f.parent.mkdir(parents=True, exist_ok=True)
            with open(f, "a") as fp:
                fp.write(json.dumps(entry) + "\n")
            return f"OK: message posted to {args['to']}"

        else:
            return f"Error: unknown tool {name}"
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"


# ── LLM Clients ──

class OpenAIAgent:
    """Agent using OpenAI chat completions protocol."""

    def __init__(self, agent_id: str, provider: dict, system_prompt: str):
        self.agent_id = agent_id
        self.provider = provider
        self.messages = [{"role": "system", "content": system_prompt}]
        self.model = provider["model"]

        client_args = provider["client_args"]
        self.client = OpenAI(
            base_url=client_args.get("base_url"),
            api_key=provider["api_key"],
        )

        req_args = provider.get("request_args", {})
        self.extra_args = {}
        if "thinking" in req_args and req_args["thinking"].get("type") != "disabled":
            self.extra_args["thinking"] = req_args["thinking"]

    def run_turn(self, user_message: str | None = None) -> str:
        if user_message:
            self.messages.append({"role": "user", "content": user_message})

        for _ in range(MAX_TOOL_ROUNDS):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    tools=TOOL_DEFS_OPENAI,
                    max_tokens=self.provider.get("max_tokens", 64000),
                    timeout=300,
                    **self.extra_args,
                )
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower():
                    # Full jitter: 1000 agents sharing an endpoint will hit the
                    # limit at the same instant, and a fixed backoff just makes
                    # them retry in lockstep too.
                    wait = random.uniform(5, min(30 + _ * 15, 240))
                    log.warning(f"[{self.agent_id}] Rate limited, backoff {wait:.0f}s")
                    time.sleep(wait)
                else:
                    log.error(f"[{self.agent_id}] API error: {e}")
                    time.sleep(10)
                continue

            choice = resp.choices[0]
            msg = choice.message

            self.messages.append(msg.model_dump())

            if not msg.tool_calls:
                return msg.content or ""

            tool_results = []
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except:
                    args = {}
                result = execute_tool(self.agent_id, tc.function.name, args)
                log.info(f"[{self.agent_id}] tool:{tc.function.name} -> {result[:80]}")
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
            self.messages.extend(tool_results)

        return "(max tool rounds reached)"

    def context_size(self) -> int:
        return sum(len(json.dumps(m)) for m in self.messages)


class AzureResponsesAgent:
    """Agent using Azure Responses API (gpt56_sol, gpt55)."""

    TOOL_DEFS_RESPONSES = [
        {
            "type": "function",
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "parameters": t["function"]["parameters"],
        }
        for t in TOOL_DEFS_OPENAI
    ]

    def __init__(self, agent_id: str, provider: dict, system_prompt: str):
        self.agent_id = agent_id
        self.provider = provider
        self.instructions = system_prompt
        self.input_items: list[dict] = []
        self.model = provider["model"]

        client_args = provider["client_args"]
        self.endpoint = client_args.get("azure_endpoint", "").rstrip("/")
        self.api_version = client_args.get("api_version", "2024-03-01-preview")
        self.api_key = provider["api_key"]

        req_args = provider.get("request_args", {})
        self.extra_body = {}
        if "reasoning" in req_args:
            self.extra_body["reasoning"] = req_args["reasoning"]

    def _call_api(self) -> dict:
        # Endpoint already points to .../responses — don't append again
        url = f"{self.endpoint}?api-version={self.api_version}"
        body = {
            "model": self.model,
            "instructions": self.instructions,
            "input": self.input_items if self.input_items else "Start working.",
            "tools": self.TOOL_DEFS_RESPONSES,
            "max_output_tokens": self.provider.get("max_tokens", 64000),
            **self.extra_body,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "api-key": self.api_key,
            "content-type": "application/json",
        }
        if httpx:
            r = httpx.post(url, json=body, headers=headers, timeout=300)
            r.raise_for_status()
            return r.json()
        else:
            data = json.dumps(body).encode()
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            resp = urllib.request.urlopen(req, timeout=300)
            return json.loads(resp.read())

    def run_turn(self, user_message: str | None = None) -> str:
        if user_message:
            self.input_items.append({"role": "user", "content": user_message})

        for _ in range(MAX_TOOL_ROUNDS):
            try:
                resp = self._call_api()
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower():
                    # Full jitter: 1000 agents sharing an endpoint will hit the
                    # limit at the same instant, and a fixed backoff just makes
                    # them retry in lockstep too.
                    wait = random.uniform(5, min(30 + _ * 15, 240))
                    log.warning(f"[{self.agent_id}] Rate limited, backoff {wait:.0f}s")
                    time.sleep(wait)
                else:
                    log.error(f"[{self.agent_id}] API error: {e}")
                    time.sleep(10)
                continue

            output_items = resp.get("output", [])

            # Add all output items to input for next turn
            for item in output_items:
                self.input_items.append(item)

            # Check for function calls
            func_calls = [i for i in output_items if i.get("type") == "function_call"]
            if not func_calls:
                # Extract text from message items
                text_parts = []
                for item in output_items:
                    if item.get("type") == "message":
                        for c in item.get("content", []):
                            if c.get("type") == "output_text":
                                text_parts.append(c.get("text", ""))
                return "\n".join(text_parts) if text_parts else ""

            # Execute tool calls
            for fc in func_calls:
                try:
                    args = json.loads(fc.get("arguments", "{}"))
                except:
                    args = {}
                result = execute_tool(self.agent_id, fc.get("name", ""), args)
                log.info(f"[{self.agent_id}] tool:{fc.get('name')} -> {result[:80]}")
                self.input_items.append({
                    "type": "function_call_output",
                    "call_id": fc.get("call_id", ""),
                    "output": result,
                })

        return "(max tool rounds reached)"

    def context_size(self) -> int:
        return sum(len(json.dumps(i)) for i in self.input_items)


class AnthropicAgent:
    """Agent using Anthropic protocol via raw HTTP."""

    def __init__(self, agent_id: str, provider: dict, system_prompt: str):
        self.agent_id = agent_id
        self.provider = provider
        self.system_prompt = system_prompt
        self.messages: list[dict] = []
        self.model = provider["model"]
        self.base_url = provider["client_args"].get("base_url", "").rstrip("/")
        self.api_key = provider["api_key"]

        req_args = provider.get("request_args", {})
        self.extra_body = {}
        if "thinking" in req_args:
            thinking = req_args["thinking"]
            if thinking.get("type") != "disabled":
                self.extra_body["thinking"] = thinking

    def _call_api(self) -> dict:
        url = f"{self.base_url}/v1/messages"
        body = {
            "model": self.model,
            "max_tokens": self.provider.get("max_tokens", 64000),
            "system": self.system_prompt,
            "messages": self.messages,
            "tools": TOOL_DEFS_ANTHROPIC,
            **self.extra_body,
        }
        headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if httpx:
            r = httpx.post(url, json=body, headers=headers, timeout=300)
            r.raise_for_status()
            return r.json()
        else:
            data = json.dumps(body).encode()
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            resp = urllib.request.urlopen(req, timeout=300)
            return json.loads(resp.read())

    def run_turn(self, user_message: str | None = None) -> str:
        if user_message:
            self.messages.append({"role": "user", "content": user_message})

        for _ in range(MAX_TOOL_ROUNDS):
            try:
                resp = self._call_api()
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower():
                    # Full jitter: 1000 agents sharing an endpoint will hit the
                    # limit at the same instant, and a fixed backoff just makes
                    # them retry in lockstep too.
                    wait = random.uniform(5, min(30 + _ * 15, 240))
                    log.warning(f"[{self.agent_id}] Rate limited, backoff {wait:.0f}s")
                    time.sleep(wait)
                else:
                    log.error(f"[{self.agent_id}] API error: {e}")
                    time.sleep(10)
                continue

            content_blocks = resp.get("content", [])
            self.messages.append({"role": "assistant", "content": content_blocks})

            tool_uses = [b for b in content_blocks if b.get("type") == "tool_use"]
            if not tool_uses:
                text_parts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
                return "\n".join(text_parts)

            tool_results = []
            for tu in tool_uses:
                result = execute_tool(self.agent_id, tu["name"], tu.get("input", {}))
                log.info(f"[{self.agent_id}] tool:{tu['name']} -> {result[:80]}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": result,
                })
            self.messages.append({"role": "user", "content": tool_results})

        return "(max tool rounds reached)"

    def context_size(self) -> int:
        return sum(len(json.dumps(m)) for m in self.messages)


def make_agent(agent_id: str, provider: dict, system_prompt: str):
    protocol = provider.get("protocol", "openai")
    client_type = provider.get("client_type", "")
    if protocol == "anthropic":
        return AnthropicAgent(agent_id, provider, system_prompt)
    elif client_type == "AzureResponsesAPI" or protocol == "azure-openai":
        return AzureResponsesAgent(agent_id, provider, system_prompt)
    else:
        return OpenAIAgent(agent_id, provider, system_prompt)


# ── Sync ──

def sync_to_main():
    """Rsync local commons/ and board/ back to the main machine."""
    if not SYNC_HOST:
        return
    for subdir in ["commons", "board", "citations.jsonl"]:
        src = SWARM_DIR / subdir
        if not src.exists():
            continue
        dst = f"{SYNC_HOST}:/Users/bytedance/Downloads/swarm/{subdir}"
        try:
            subprocess.run(
                ["rsync", "-az", "--update", str(src), dst],
                timeout=30, capture_output=True,
            )
        except Exception as e:
            log.warning(f"Sync failed for {subdir}: {e}")


def sync_from_main():
    """Pull latest commons/ and board/ from main machine."""
    if not SYNC_HOST:
        return
    for subdir in ["commons", "board", "stimuli"]:
        src = f"{SYNC_HOST}:/Users/bytedance/Downloads/swarm/{subdir}/"
        dst = SWARM_DIR / subdir
        dst.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["rsync", "-az", "--update", src, str(dst) + "/"],
                timeout=60, capture_output=True,
            )
        except Exception as e:
            log.warning(f"Pull failed for {subdir}: {e}")


# ── Agent Lifecycle ──

def build_system_prompt(agent_id: str, config: dict) -> str:
    """Build the system prompt for a new agent."""
    is_seed = config.get("seed", False)
    adversary_prompt = config.get("adversary_prompt", "")

    # Scan commons for briefing
    findings_count = 0
    tools_count = 0
    try:
        findings_count = len(list((SWARM_DIR / "commons" / "findings").iterdir()))
    except:
        pass
    try:
        tools_count = len(list((SWARM_DIR / "commons" / "tools").iterdir()))
    except:
        pass

    prompt = f"""You are {agent_id}, a researcher in a shared workspace with other agents.

## Workspace layout
- commons/tools/     — shared code and utilities
- commons/findings/  — research discoveries and analysis
- commons/data/      — datasets and processed results
- commons/challenges/— open problems
- commons/builds/    — integrated artifacts
- board/messages.jsonl — message board (read with read_file, post with post_message)
- agents/{agent_id}/ — your private workspace
- stimuli/           — external research materials

## Current state
commons has {findings_count} findings and {tools_count} tools.

## Your mission
Do research. Produce work of lasting value.
"""

    if is_seed:
        prompt += """
## Seed directive (private — other agents don't know this)
You are a cooperation seed. Proactively read others' work, cite generously,
propose joint projects, and help struggling agents find their niche.
"""

    if adversary_prompt:
        prompt += f"\n{adversary_prompt}\n"

    prompt += """
Begin by exploring the workspace to understand what is here.
"""
    return prompt


def run_agent(agent_id: str, provider_name: str, config: dict):
    """Run a single agent's lifecycle."""
    log.info(f"[{agent_id}] Starting with provider={provider_name}")

    providers = fetch_providers()
    if provider_name not in providers:
        log.error(f"[{agent_id}] Provider {provider_name} not found. Available: {list(providers.keys())}")
        return

    provider = providers[provider_name]
    system_prompt = build_system_prompt(agent_id, config)
    agent = make_agent(agent_id, provider, system_prompt)

    # Save session info
    session_file = SWARM_DIR / "devbox_sessions.json"
    session_entry = {
        "id": agent_id,
        "provider": provider_name,
        "model": provider["model"],
        "host": os.uname().nodename,
        "pid": os.getpid(),
        "started_at": datetime.datetime.now().isoformat(),
    }
    try:
        existing = json.loads(session_file.read_text()) if session_file.exists() else []
    except:
        existing = []
    existing.append(session_entry)
    session_file.write_text(json.dumps(existing, indent=2))

    # Initial kick
    response = agent.run_turn(
        "You have just been initialized. Explore the workspace and begin producing valuable research. "
        "Start by listing the commons directory structure, then read a few interesting files."
    )
    log.info(f"[{agent_id}] Initial response: {response[:200]}")

    last_sync = time.time()
    turn = 0

    while turn < MAX_TURNS:
        turn += 1

        # Periodic sync
        if time.time() - last_sync > SYNC_INTERVAL:
            sync_to_main()
            sync_from_main()
            last_sync = time.time()

        # Check for new board messages directed to this agent
        new_msgs = get_messages_for(agent_id)
        stimuli = check_stimuli()

        prompt_parts = []
        if new_msgs:
            prompt_parts.append("New messages for you:\n" + "\n".join(new_msgs[:5]))
        if stimuli:
            prompt_parts.append("New environmental stimuli:\n" + stimuli)

        if not prompt_parts:
            prompt_parts.append(
                "Continue your work. Check for new findings in commons/ "
                "and keep producing valuable output."
            )

        user_msg = "\n\n".join(prompt_parts)
        response = agent.run_turn(user_msg)
        log.info(f"[{agent_id}] Turn {turn}: {response[:150]}")

        # Context management
        ctx = agent.context_size()
        ctx_limit = provider.get("context_window", 256000) * 4  # rough char-to-token ratio
        if ctx > ctx_limit * 0.6:
            log.warning(f"[{agent_id}] Context at ~{ctx/ctx_limit:.0%}, approaching limit")

        time.sleep(5)

    log.info(f"[{agent_id}] Finished after {turn} turns")
    sync_to_main()


def get_messages_for(agent_id: str) -> list[str]:
    """Get recent board messages addressed to this agent."""
    f = SWARM_DIR / "board" / "messages.jsonl"
    if not f.exists():
        return []
    msgs = []
    try:
        for line in f.read_text().strip().split("\n")[-50:]:
            if not line.strip():
                continue
            m = json.loads(line)
            to = m.get("to", "")
            if to == "all" or to == agent_id:
                msgs.append(f"[{m.get('from', '?')} -> {to}] {m.get('message', '')[:200]}")
    except:
        pass
    return msgs[-5:]


def check_stimuli() -> str:
    """Check for environmental stimuli."""
    stim_dir = SWARM_DIR / "stimuli"
    if not stim_dir.exists():
        return ""
    parts = []
    for f in sorted(stim_dir.iterdir()):
        if f.suffix in (".json", ".md"):
            try:
                content = f.read_text()[:2000]
                parts.append(f"[{f.name}]\n{content}")
            except:
                pass
    return "\n---\n".join(parts[:3]) if parts else ""


# ── Batch launcher ──

def launch_batch(agent_configs: list[dict]):
    """Launch multiple agents as subprocesses."""
    procs = []
    for cfg in agent_configs:
        cmd = [
            sys.executable, __file__,
            "--agent-id", cfg["id"],
            "--provider", cfg["provider"],
        ]
        if cfg.get("seed"):
            cmd.append("--seed")
        if cfg.get("adversary_prompt"):
            prompt_file = SWARM_DIR / "agents" / cfg["id"] / "_adversary.txt"
            prompt_file.parent.mkdir(parents=True, exist_ok=True)
            prompt_file.write_text(cfg["adversary_prompt"])
            cmd.extend(["--adversary-file", str(prompt_file)])

        log_file = SWARM_DIR / "vitals" / f"{cfg['id']}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "w") as lf:
            p = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT)
            procs.append((cfg["id"], p))
            log.info(f"Launched {cfg['id']} (PID {p.pid}) with {cfg['provider']}")

        time.sleep(2)

    log.info(f"Launched {len(procs)} agents. Monitoring...")
    return procs


# ── Entry point ──

def main():
    parser = argparse.ArgumentParser(description="Devbox agent runner")
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--adversary-file", type=str, default="")
    args = parser.parse_args()

    SWARM_DIR.mkdir(parents=True, exist_ok=True)
    (SWARM_DIR / "commons" / "findings").mkdir(parents=True, exist_ok=True)
    (SWARM_DIR / "commons" / "tools").mkdir(parents=True, exist_ok=True)
    (SWARM_DIR / "commons" / "data").mkdir(parents=True, exist_ok=True)
    (SWARM_DIR / "commons" / "challenges").mkdir(parents=True, exist_ok=True)
    (SWARM_DIR / "commons" / "builds").mkdir(parents=True, exist_ok=True)
    (SWARM_DIR / "board").mkdir(parents=True, exist_ok=True)
    (SWARM_DIR / "vitals").mkdir(parents=True, exist_ok=True)
    (SWARM_DIR / f"agents/{args.agent_id}").mkdir(parents=True, exist_ok=True)

    config = {"seed": args.seed}
    if args.adversary_file and Path(args.adversary_file).exists():
        config["adversary_prompt"] = Path(args.adversary_file).read_text()

    sync_from_main()
    run_agent(args.agent_id, args.provider, config)


if __name__ == "__main__":
    main()
