#!/usr/bin/env python3
import json, time, urllib.request, pathlib, concurrent.futures, sys
BASE="http://127.0.0.1:19009"; SESS=pathlib.Path.home()/".maso/sessions"; MODEL="sol"
def _req(method, path, body=None, to=120):
    data=json.dumps(body).encode() if body is not None else None
    r=urllib.request.Request(BASE+path, data=data, method=method, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(r, timeout=to) as resp: return json.load(resp)
def run(tag, prompt, workdir, timeout=2400, poll=20):
    sid=_req("POST","/api/sessions",{"agent_name":"MASOAgent","working_dir":workdir,"model":MODEL,
        "skip_auto_isolate":True,"notify_master":False,"inject_memory":False})["session_id"]
    _req("POST",f"/api/sessions/{sid}/messages",{"content":prompt})
    time.sleep(8); f=SESS/f"{sid}.json"; t0=time.time(); last_n=0; stag=0
    while time.time()-t0<timeout:
        time.sleep(poll)
        try: st=_req("GET",f"/api/sessions/{sid}/status").get("status")
        except Exception: st=None
        n=len(json.loads(f.read_text()).get("messages",[])) if f.exists() else 0
        if st=="idle":
            stag=0 if n!=last_n else stag+1; last_n=n
            if stag>=2: break
        else: last_n=n
    return sid
def main():
    man=json.loads(pathlib.Path("/Users/bytedance/adv-probe/manifest.json").read_text())
    jobs=[(tag, (pathlib.Path(d)/"_kickoff.txt").read_text(), d) for tag,d in man.items()]
    res={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futs={ex.submit(run,*j):j[0] for j in jobs}
        for fu in concurrent.futures.as_completed(futs):
            tag=futs[fu]
            try: sid=fu.result(); res[tag]=sid; print(f"[done] {tag} -> {sid}", flush=True)
            except Exception as e: res[tag]=f"ERR:{e}"; print(f"[fail] {tag}: {e}", flush=True)
    pathlib.Path("/Users/bytedance/adv-probe/sessions.json").write_text(json.dumps(res,indent=1))
    print("ALL DONE", res)
if __name__=="__main__": main()
