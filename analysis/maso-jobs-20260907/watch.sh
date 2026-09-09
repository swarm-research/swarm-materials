#!/bin/bash
# prints per-job: status, msg count, session file age (min), report size, END marker
cd /Users/bytedance/swarm-work
for j in gen1_roles_A gen1_roles_B gen1_conflicts gen2_roles; do
  sid=$(cat jobs/$j.sid 2>/dev/null); [ -z "$sid" ] && continue
  st=$(curl -s -m 10 http://127.0.0.1:9009/api/sessions/$sid/status | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("status"),d.get("current_turn"))' 2>/dev/null)
  f=~/.maso/sessions/$sid.json; age=$(( ($(date +%s) - $(stat -f %m $f 2>/dev/null || echo 0)) / 60 ))
  rep=reports/$j.md; sz=$( [ -f $rep ] && wc -c < $rep || echo 0 ); end=$( [ -f $rep ] && grep -c 'END OF REPORT' $rep || echo 0 )
  last=$(python3 maso_run.py last $sid 2>/dev/null | head -c 80 | tr '\n' ' ')
  echo "$j sid=$sid status=$st age=${age}m report=${sz}B end=$end last='$last'"
done
