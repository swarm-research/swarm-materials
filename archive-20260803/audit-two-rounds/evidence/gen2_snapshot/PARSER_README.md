# MASO swarm snapshot parser

This is a read-only, standard-library-only parser for local copies of MASO
swarm filesystems. It does not SSH, access a network, invoke a model, or modify
source snapshots.

## CLI

Five-machine pull layout:

```bash
python3 parse_swarm_snapshots.py \
  --input /Users/bytedance/Downloads/swarm-gen2-20260803 \
  --baseline /Users/bytedance/Downloads/swarm-archive-20260803/01_workspace \
  --output-dir /path/to/new-empty-audit-dir
```

Immediate hidden staging directories (for example `.incoming_*` and
`.122175-stage-safe-*`) are ignored during root discovery. A selected machine
is refused if `swarm.tgz`, `.partial`, `.part`, or another in-progress marker is
present before or after manifesting.

If a completed sibling `<workspace-id>_ctl.tgz` exists, it is inventoried and
hashed member by member without extraction or execution. The archive is
rejected if it is truncated, changes during reading, or contains unsafe member
paths.

Explicit paths are also accepted:

```bash
python3 parse_swarm_snapshots.py \
  --workspace 122174=/path/to/122174 \
  --workspace 122175=/path/to/122175 \
  --output-dir /path/to/new-empty-audit-dir
```

A workspace itself (rather than a `workspace-id/{swarm,swarmctl}` wrapper) is
valid input. This makes the archived first round usable as a smoke test:

```bash
python3 parse_swarm_snapshots.py \
  --workspace gen1=/Users/bytedance/Downloads/swarm-archive-20260803/01_workspace \
  --output-dir /path/to/new-empty-smoke-dir
```

Set `SOURCE_DATE_EPOCH` when byte-for-byte stable `generated_at_utc` metadata is
needed. All tables and the input fingerprint are otherwise deterministically
sorted and content-addressed.

For maximum protection against an offline/cloud-stub file that blocks in the
OS, use `--hash-workers 1 --file-read-timeout 30`. Parallel hashing is much
faster for large snapshots, but Python worker threads cannot forcibly interrupt
a platform-level blocked `open`; the before/after in-progress-marker and file
mtime/size checks still reject changing snapshots.

## Output schema

- `audit_summary.json`: run metadata, input fingerprint, counts, per-machine
  compact summary, source hash variants, definitions, and risk guardrails.
- `manifest.csv`: one row per local snapshot file with host, plane, relative
  path, kind, size, mtime, and SHA-256. Symlinks are not followed; their digest
  is over the link target marker and target text.
- `source_hashes.csv`: runner, launcher, and reaper source candidates and hashes.
- `plan_observations.csv`: static defaults, command text, launcher spawn lines,
  and aggregate launcher claims. Every row says what level of proof it carries.
- `agent_log_footprints.csv`: identity evidence, line/error/429/tool counts,
  HTTP status/API-request counts, redacted response-prefix samples and hashes,
  finish markers, and conservative provider-success evidence. `success_evidence`
  requires at least one logged HTTP 200. HTTP 200 is explicitly an API-request
  count, never a model-turn, meaningful social action, token count, or cost.
- `session_records.csv`, `session_schemas.csv`: normalized `devbox_sessions.json`
  records plus observed key/type/schema inventories. Unknown fields are retained
  in canonical `extra_json`; records are content-addressed.
- `execution_evidence.csv`: one row per host/agent, explicitly separating
  assigned plan, process/log/session footprint, and successful-API-request
  evidence.
- `commons_artifacts.csv`, `commons_path_summary.csv`: per-host relative path and
  hash, cross-host same/conflict/missing state, and optional baseline
  same/conflict/new state.
- `citations_occurrences.csv`: citation occurrences normalized across `file` and
  `artifact` schemas, with source host/path/line retained.
- `citations_dedup.csv`: exact semantic canonical-JSON deduplication excluding
  provenance, with all provenance collected in `source_locations_json`.
- `messages_stats.csv`, `messages_actor_stats.csv`: source and claimed-sender
  statistics. Message bodies are not exported.
- `parse_errors.csv`: all recoverable walk/read/schema/JSONL errors. A malformed
  file does not abort unrelated analysis.

## Evidence boundaries and risks

`planned_only` means source defaults or a command was present. It is never
treated as proof that a process ran. A launcher spawn line, agent log, or session
record is a footprint only. `success_evidence` is deliberately narrow: at least
one logged HTTP 200 API request. It proves provider/API success only, not a full
outer turn, meaningful response, social action, intended-task completion,
output quality, token quantity, currency cost, or survival.

Version 1.1 corrects an important v1 classification bug: v1 treated the local
runner fallback `(max tool rounds reached)` and empty response prefixes as
non-failure model responses. In this snapshot that mislabeled 26 provider-error
loops as model-active. The corrected evidence layers are 123 identities that
entered the runner loop, 97 with a logged HTTP 200, and 96 with a logged tool
event.

Other important limits:

- Pulls can be incomplete or temporally inconsistent. Inspect transfer markers
  and transfer logs separately.
- Code hash equality proves byte equality, not execution.
- Runner logs preserve only response prefixes, so they cannot reconstruct full
  conversations or exact token/currency use.
- Launchers open per-agent logs with write/truncate semantics, so a current log
  pathname is not a one-to-one independent-session identifier.
- JSONL `from`, `citer`, and `cited` values are unauthenticated labels.
- `devbox_sessions.json` can be incomplete when writers use unlocked
  read-modify-write.
- Missing artifacts can mean absent, deleted, unsynced, or not transferred.
