#!/bin/bash
cd /Users/bytedance/swarm-work
done_jobs=""; lasterr=0
while true; do
  for j in gen1_roles_A gen1_roles_B gen1_conflicts gen2_roles; do
    case " $done_jobs " in *" $j "*) continue;; esac
    sid=$(cat jobs/$j.sid 2>/dev/null); [ -z "$sid" ] && continue
    last=$(python3 maso_run.py last "$sid" 2>/dev/null | tail -c 60 | tr -d '\n')
    rep=reports/$j.md; end=0; sz=0
    if [ -f "$rep" ]; then end=$(grep -c 'END OF REPORT' "$rep"); sz=$(wc -c < "$rep"); fi
    st=$(curl -s -m 10 "http://127.0.0.1:9009/api/sessions/$sid/status" 2>/dev/null | python3 -c 'import sys,json;print(json.load(sys.stdin).get("status"))' 2>/dev/null); [ -z "$st" ] && st=unknown
    f="$HOME/.maso/sessions/$sid.json"; mt=$(stat -f %m "$f" 2>/dev/null); [ -z "$mt" ] && mt=$(date +%s); age=$(( ($(date +%s) - mt) / 60 ))
    if { echo "$last" | grep -q "DONE" || [ "$end" -ge 1 ]; } && [ "$st" = "idle" ]; then
      echo "DONE $j sid=$sid size=${sz}B end=$end"; done_jobs="$done_jobs $j"
    elif [ "$age" -ge 25 ] && [ "$st" = "idle" ]; then
      echo "STALLED $j sid=$sid idle ${age}m size=${sz}B last='$last'"; done_jobs="$done_jobs $j"
    elif [ "$st" = "unknown" ]; then
      echo "STATUS_API_DOWN $j age=${age}m"
    fi
  done
  n429=$(grep -c "429" maso-9009.log 2>/dev/null); [ -z "$n429" ] && n429=0
  nfail=$(grep -c "run cycle failed" maso-9009.log 2>/dev/null); [ -z "$nfail" ] && nfail=0
  tot=$((n429+nfail)); if [ "$tot" -gt "$lasterr" ]; then echo "LLM_ERRORS total429=$n429 failed_cycles=$nfail"; lasterr=$tot; fi
  n=$(echo $done_jobs | wc -w | tr -d ' '); if [ "$n" -ge 4 ]; then echo "ALL_FINISHED"; exit 0; fi
  sleep 90
done
