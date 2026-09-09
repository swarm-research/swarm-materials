# MASO Gen2 recovered in-memory contexts — PRIVATE

This directory preserves the emergency recovery of live Gen2 runner memory on
2026-08-03.  It is intentionally separate from the public audit package.

## Contents

- `raw_cores/`: raw process core dumps acquired with `gcore`.  They may contain
  provider clients, endpoints, credentials, environment values, and unrelated
  process memory.  **Do not upload, share, commit, or place these files in the
  public report archive.**
- `extracted/`: locally sanitized context JSON/status files recovered from the
  live processes, plus the offline decoder result for the one process that
  exited after core capture.
- `recovered_context_inventory.csv` / `recovered_context_summary.json`:
  inventory and mechanical recovery summary.
- `core_backup_summary.json`: raw-core byte/hash verification.

## Recovery boundary

Each context is the in-memory conversation history observed up to its
`captured_utc`, not a guaranteed natural end-of-run transcript.  Seventy-two
process contexts were recovered, covering 59 distinct agent labels.  The
normalized audit identified 32,274 history items and 41,353 events.  Tool calls
and results pair 12,108/12,108, with one additional call captured while it was
still in flight.

The extracted JSON was scanned for credential-shaped strings.  One lexical hit
was manually reviewed and was ordinary prose containing `authorization:` in an
escaped tool argument, not a credential.  This scan reduces risk but does not
make raw cores safe to share.

Directory permissions should remain `0700`; files should remain `0600`.
