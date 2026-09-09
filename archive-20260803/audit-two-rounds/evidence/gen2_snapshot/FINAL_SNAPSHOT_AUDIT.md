# MASO second-generation snapshot audit — corrected v2

## Bottom line

There is no single honest number for “how many agents ran.” The fixed five-host
snapshot supports the following evidence layers:

1. **1,000 is an advertised identity universe**, consisting of inherited labels
   1–36 and 964 planned new labels 37–1000. It is not a count of processes,
   sessions, successful calls, or concurrent agents.
2. **964 new logical identities were assigned by launcher code**: 64 in wave 1
   and 900 in wave 2.
3. **316 distinct identity log paths exist.** Of these, 193 are 122447 import
   failures with zero API requests and zero runner-loop activity.
4. **123 identities entered the runner loop.** This is a control-flow footprint,
   not model success. Twenty-six of the 123 have zero HTTP 200 and zero tool
   events; every apparent response prefix is the runner-generated local fallback
   `(max tool rounds reached)`.
5. **97 identities have at least one logged HTTP 200 API request.** This is the
   strongest preserved evidence that the identity successfully reached the
   provider/model API. It is still not a model turn, token count, independent
   session, meaningful answer, social action, or task completion.
6. **96 identities have at least one logged tool event.** All 96 posted at least
   one message, and 95 also posted at least one citation. The one HTTP-success
   exception is 122174 agent-067: 201 HTTP 200s, 200 blank turn responses, and
   zero tool/message/citation events.
7. **79 identities have a Turn-200 Finished marker**, but only 64 also have an
   HTTP 200. Fifteen are provider-error-only loops that the harness nevertheless
   drove to Finished. Conversely, 33 HTTP-success identities lack Finished; 11
   local-error loops also lack Finished.

Thus the most defensible compact answer is: **97 logical identity labels have
successful API-request evidence, and 96 have observable tool/social action.**
Neither number is a recoverable count of independent actors, sessions,
processes, or peak concurrency because repeated launchers, fixed-path
`O_TRUNC`, and an unlocked session ledger merge and destroy lineage evidence.

## Corrected per-host funnel

| host | planned new | log paths | entered runner loop | HTTP-200 identities | tool-event identities | Finished total | Finished + HTTP200 | HTTP200 unfinished | error-only Finished | error-only unfinished | import failures |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 122174 | 193 | 33 | 33 | 26 | 25 | 22 | 17 | 9 | 5 | 2 | 0 |
| 122175 | 193 | 31 | 31 | 23 | 23 | 20 | 15 | 8 | 5 | 3 | 0 |
| 122447 | 193 | 193 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 193 |
| 122448 | 193 | 31 | 31 | 26 | 26 | 20 | 18 | 8 | 2 | 3 | 0 |
| 122456 | 192 | 28 | 28 | 22 | 22 | 17 | 14 | 8 | 3 | 3 | 0 |
| **total** | **964** | **316** | **123** | **97** | **96** | **79** | **64** | **33** | **15** | **11** | **193** |

The machine-readable form is `second_gen_identity_layers.csv`.

## The v1 parser error and correction

Parser v1 used a visible response prefix or tool event as `success_evidence`.
Its failure classifier did not recognize `(max tool rounds reached)` and also
accepted empty prefixes. This mislabeled 26 provider-incompatible local-error
loops as model-active and produced the incorrect headline of 123 model-active
identities.

Parser v1.1 corrects the classifier and defines `success_evidence` as at least
one logged HTTP 200. The regenerated `audit_summary.json` now reports 97
success-evidence identities. The input data and its fingerprint did not change;
only the parser semantics and output tables changed.

## 122447 failure island

Host 122447 created 193 tiny identity logs because fast failure kept freeing
launcher slots. Every runner exited at import with:

```text
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
```

That host has zero HTTP requests, zero tools, zero board messages, zero Finished
markers, and no `devbox_sessions.json` records. A launcher line such as `All 180
agents launched` is a process-spawn claim, not model-run success.

## Request counts

The fixed snapshot contains 124,444 logged HTTP request lines:

| HTTP status | lines |
|---|---:|
| 200 | 35,422 |
| 400 | 80,982 |
| 429 | 7,310 |
| 500 | 663 |
| 503 | 12 |
| 504 | 55 |

The 35,422 HTTP 200 lines come from 97 identity paths. A tool-using outer turn can
make multiple API requests, and retries add more; these counts cannot be
converted into turns, tokens, independent agents, or RMB.

## Snapshot provenance

- Input fingerprint:
  `6982fe49ade50cdd79b9a00cde736adcfd4e950d8c55b4f25a11b86eb396b49f`.
- Manifest: 18,555 entries, 735,984,018 bytes, zero parse/read errors.
- The five machine pulls are serial, not a simultaneous distributed snapshot.
- All five `<workspace>_ctl.tgz` archives are byte-identical 45-byte empty
  containers with zero file members; no `/tmp/swarmctl` control plane was
  recovered.
- No top-level `devbox_reaper.py` was recovered. 122174 does retain one historical
  no-kill reaper state/log and a later missing-script launch failure; absence of
  executable control files in the snapshot does not prove that no transient
  historical process ever existed.
- Top-level deployed runner/launcher files are byte-identical across the five
  hosts. Use `deployed_source_hashes_strict.csv`, not the broad lexical
  `source_hashes.csv`, for deployment-source claims.

## Social-ledger scopes

- Root boards: 7,719 physical lines, 6,299 exact-unique lines. The physical count
  contains inherited/cross-host duplicate history, including a 1,416-line common
  prefix on both 122174 and 122456.
- Lines attributed structurally to current-host Gen2 active-ID sender labels:
  4,884. These are still unauthenticated claimed labels, not actors.
- Broad filesystem message parser, including nested sandbox/test ledger copies:
  9,145 occurrences and 6,301 canonical unique events.
- Root citation ledgers: 4,604 lines and 4,602 canonical unique events.
- Broad citation parser: 4,611 occurrences and 4,609 canonical unique events;
  seven extra rows are nested 122456 sandbox copies, and 19 rows lack both
  `file` and `artifact`.

## Other limits

- The runner did not persist complete private model history, complete tool-call
  arguments, usage, or billing join keys.
- `devbox_sessions.json` recovered 157 rows, but unlocked read-modify-write and
  duplicate launches make it unsuitable as a session-count ground truth.
- Commons contain 12,049 host-artifact occurrences across 7,536 relative paths;
  18 paths conflict across hosts, 621 are identical on all five, and 6,736 exist
  on only a subset. The machines are not one synchronized society.
- Purposefully selected process-tracing chains establish mechanisms, not
  prevalence or causal treatment effects.

Use `audit_summary.json`, `agent_log_footprints.csv`,
`execution_evidence.csv`, `second_gen_identity_layers.csv`, `manifest.csv`, and
the other generated tables to reproduce each numeric layer.
