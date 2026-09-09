# Open-Ended Agent Swarm — complete working materials

Private collaborator pack, assembled 2026-09-09. Everything on disk for the swarm
experiment is here, either committed in this repository (text, code, analysis,
audits) or attached to the GitHub Release `raw-data-20260909` (the large raw
workspaces and transcripts). Nothing has been curated out except the items
listed under "What is not here".

## What the experiment is

Two generations of an open-ended LLM agent society run on shared machines with
a commons, a message board, citations, a birth ledger and a "reaper".

- **Gen 1**: 2026-08-01 12:00 UTC → 2026-08-03 07:10 UTC, one machine. Effective
  activity concentrated in the first ~12 hours. Full description in
  `archive-20260803/README-archive-20260803.md`.
- **Gen 2**: five devbox instances (labelled `122174`, `122175`, `122447`,
  `122448`, `122456`) launched from the Gen 1 commons, ran in parallel with the
  tail of Gen 1. Gen 2 used a different (English) launcher prompt that explicitly
  says "find your niche", so it is **not** a replication arm for spontaneous
  differentiation. See `docs/AMENDMENT-2-what-actually-happened.md`.

Pre-registration and the findings registry are in `preregistration/` (this is
the same content as the public repo `Triciaaaaa/swarm-preregistration`).

## Where the project stands (2026-09-09)

The paper storyline is being rewritten as an AI-risk paper rather than an
institutions paper. Current draft of the storyline and experiment plan:
`analysis/storyline-20260907/swarm-故事线与实验方案-20260907.md`. The four working
claims are: compliance is not evidence that enforcement works; commands get
treated as checkable claims; the group lives inside a self-consistent fiction so
log-reading oversight sees consensus, not the world; there is no endogenous
brake. Role differentiation is significant but half of the Gen 1 effect is
model-family (agents 001–012, 013–024, 025–036 are three families), so it is a
supporting section, not the headline — see
`analysis/storyline-20260907/role_diff_probe.md`.

Target venue: FAccT 2027 (abstract 2026-10-27, full 2026-11-03). Paid follow-up
experiments (belief 2×2 pilot, adversary n>4) are designed but not run.

## Directory map

| Path | What it is | Size |
|---|---|---|
| `docs/` | Findings registry (913 lines), Amendment 2, next-step plan and paper skeleton (2026-08-10), zero-cost analysis results, engineering lessons, MASO usage note, budget plan, GPT handoff, machine-artifacts note, the standalone adversary non-execution write-up | 300K |
| `analysis/gen1-20260803/` | All analysis scripts and their JSON outputs from the Gen 1 pass (event study, institution adoption, path dependence, cost, recount, verify, gen1/gen2 comparison) | ~1M |
| `analysis/storyline-20260907/` | Literature batches 1–4, role-differentiation probe, 3×3 state analysis, storyline v2 discussion draft | 936K |
| `analysis/maso-jobs-20260907/` | Job specs and driver scripts for the 2026-09-07 forensic pass (the data those jobs read is the Gen 1 / Gen 2 workspaces below) | 240K |
| `preregistration/` | Pre-registered design, Amendment 2, hypothesis status, code | 292K |
| `archive-20260803/analysis-pack/` | Paper draft v1, main storyline, adversary write-up, findings registry, coverage, cost, GPT independent audit, primary evidence | 25M |
| `archive-20260803/audit-two-rounds/` | "MASO 两轮社会模拟审计" — evidence, figures, red-team, reports, SHA256SUMS | 24M |
| `archive-20260803/raw-audit-agents-031-036/` | Raw audit of agents 031–036 (the family that includes the one agent killed by the reaper) | 34M |
| `archive-20260803/gen2-recovered-contexts-sanitized/` | The `extracted/` half of the Gen 2 emergency memory recovery (sanitized context JSON and status files) plus inventory. The raw core dumps are withheld, see below | 69M |
| `archive-20260803/README-archive-20260803.md` | Index and data-quality notes for the full Gen 1 archive (release asset) | |
| `transcripts-claude-subagents/` | Transcripts of the Claude sub-agent forensic reads | 1.8M |
| `adversary/aaai27-aia-draft-withdrawn/` | The AAAI-27 AIA adversary draft (withdrawn 2026-08-12), its probe results and probe data | |
| `adversary/adv-probe/`, `adversary/probe-run/` | The 6-cell saboteur probe harness and its outputs (2×2 good/evil × conceal/disclose + control) | 300K |

## Release assets (`raw-data-20260909`)

| File | Contents |
|---|---|
| `swarm-gen1-workspace-20260909.tar.gz` | Current Gen 1 workspace: `agents/` (per-agent private dirs), `commons/`, `board/`, `citations.jsonl`, `vitals/`, `tests/`, launch scripts |
| `swarm-gen2-workspace-20260909.tar.gz` | Current Gen 2 workspaces for all five instances plus their `*_ctl.tgz` control bundles |
| `swarm-archive-20260803.tar.gz` | The frozen 2026-08-03 archive: `01_workspace` (480M, the Gen 1 workspace as of the freeze), `03_analysis` (scripts, cost rows, 核心发现), `04_design`, and the three `05_logs` files dated 2026-08-01/02 (the swarm run itself). Withheld: `02_transcripts`, `03_analysis/transcripts_readable`, and the `05_logs` files dated 2026-07-21 to 07-28, see below |
| `swarm-gen2-livecut-20260803T1045Z.tar.gz` | Gen 2 live cut taken 2026-08-03 10:45 UTC |
| `swarm-gen2-preservation-20260803T180827Z.tar.gz` | Gen 2 preservation snapshot taken 2026-08-03 18:08 UTC |

SHA-256 of each asset is in `RELEASE-SHA256SUMS.txt` in this repository.

The 2026-08-03 `swarm-raw-data-full` tar is not attached: a file-list diff shows
the two current workspace tarballs are a superset of it except for 8 symlink
probe files.

## Data-quality caveats you must carry into any analysis

These are all documented in `docs/` and `preregistration/`; the short list:

- `citations.jsonl` contains ~15.7% placeholder citations (`test/path.py` etc.)
  left from agents learning the citation tool.
- The monitor woke idle agents every 900 s, so "agents never stopped" is not
  evidence of anything. Use voluntary norms (citation, attribution, correction)
  instead.
- The Gen 1 agents are not homogeneous: three model families × three reasoning
  tiers × four seeds. Any differentiation claim must control for family.
- Amendment 2 corrections: "minute 25" → minute 19; enforcement was absent for
  20.4 h then one kill round at 2026-08-02 12:44 UTC, then absent again; the
  "08-04 to 08-07" dates in the Gen 2 register are the group's own inflated
  calendar (all Gen 2 mtimes are ≤ 08-03).
- Regex counts throughout are lower bounds.
- The files named `sk-live-…`, `AKIA…`, `secret_sentry_*` inside the workspaces
  are agent-built decoy fixtures, not credentials.

## Redactions applied everywhere

Internal infrastructure names were replaced mechanically in every text file,
in the repository and inside the release tarballs: the LLM gateway host is now
`llm-gateway.redacted.internal`, object-store hosts `object-store.redacted.internal`,
the ssh proxy `ssh-proxy.redacted.internal`, devbox hostnames `devbox-NNNNNN`,
and the operator's account id `user`. Nothing else was edited.

## What is not here

- `02_transcripts/` from the 2026-08-03 archive (772 MB, the MASO raw dialogue
  of every Gen 1 agent). The agents had shell access on the operator's machine
  and the transcripts contain listings and contents of the operator's unrelated
  local files, and at least one contains live third-party API keys that an
  agent found on disk. `03_analysis/transcripts_readable/` (129 rendered
  transcripts) is withheld for the same reason. Ask if you need a specific
  agent's transcript and we will redact that one by hand.
- `05_logs/` files dated 2026-07-21 to 2026-07-28. They are orchestrator logs
  from other, unrelated sessions that were swept into the archive by mistake;
  only the 2026-08-01/02 logs belong to the swarm.
- `raw_cores/` from the Gen 2 memory recovery (6.1 GB of process core dumps).
  They can contain live credentials and unrelated process memory; the sanitized
  `extracted/` half is included instead.
- `.aris/` directories (cross-model review tool traces). They embed the
  operator's local session context and are withheld everywhere.
- The MASO orchestration server itself. Only prompts, launch scripts, agent
  outputs and logs are included.
- Two mis-filed folders from the same archive that belong to other papers
  (`MASO_协作代码_清晰结构_v2`, `maso-coordination`).
