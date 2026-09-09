#!/usr/bin/env python3
"""Minimal MASO driver: CodexAgent + native-sol on port 9009.
usage: maso_run.py new <name> <promptfile>   -> prints session_id, sends prompt
       maso_run.py status <sid>
       maso_run.py last <sid>                -> last assistant message
"""
import sys, json, time, urllib.request, os
BASE="http://127.0.0.1:9009"
WD="/Users/bytedance/swarm-work"
def req(path, data=None, method=None):
    r=urllib.request.Request(BASE+path, data=json.dumps(data).encode() if data is not None else None,
        headers={"Content-Type":"application/json"}, method=method or ("POST" if data is not None else "GET"))
    with urllib.request.urlopen(r, timeout=60) as resp: return json.loads(resp.read() or b"{}")
cmd=sys.argv[1]
if cmd=="new":
    name, pf = sys.argv[2], sys.argv[3]
    agent=os.environ.get("MASO_AGENT","MASOAgent"); model=os.environ.get("MASO_MODEL","gemini38flash")
    s=req("/api/sessions", {"agent_name":agent,"working_dir":WD,"model":model,
        "skip_auto_isolate":True,"notify_master":False,"inject_memory":False,"name":name})
    sid=s["session_id"]
    req(f"/api/sessions/{sid}/messages", {"content":open(pf).read()})
    open(f"{WD}/jobs/{name}.sid","w").write(sid); print(sid)
elif cmd=="status":
    print(json.dumps(req(f"/api/sessions/{sys.argv[2]}/status")))
elif cmd=="last":
    sid=sys.argv[2]; d=json.load(open(os.path.expanduser(f"~/.maso/sessions/{sid}.json")))
    ms=[m for m in d.get("messages",[]) if m.get("role")=="assistant"]
    print(len(d.get("messages",[])), "msgs;", (ms[-1].get("content") if ms else None))
