# Code

## experiment/
The orchestration that actually ran. Published because Amendment 2 documents eight
failures in it, and those claims are only checkable against the source.

| file | role | known defect |
|---|---|---|
| `swarm_launcher.py` | Gen-1 launcher; holds the 3×3 model/tier assignment and the hidden `SEED_EXTRA` block | agent roster and seed identities readable by participants |
| `swarm_reaper.py` | selection mechanism | wrong path at launch (never ran); `fromisoformat` drops 83% of timestamps; kill path has no termination call |
| `swarm_resurrect.py` | Gen-2 memory reconstruction | line 133 reads `board/citations.jsonl` (21 records) instead of the root ledger (1,712) |
| `swarm_monitor.py` | idle-agent waker | the only enforcement that actually ran |
| `swarm_compactor.py` | context migration | instructs a citation schema (`from`/`to`) the reaper does not read |
| `devbox_*.py` | Gen-2 distributed runner | writes `artifact` where Gen 1 writes `file` |

## analysis/
Read-only. Every script regenerates its numbers from the raw corpus.

| file | what it computes |
|---|---|
| `swarm_analysis2.py` | structure: specialisation by KL divergence from the population mix, citation network, seeds |
| `swarm_insights.py` / `swarm_insights2.py` | mechanisms: reciprocity, announcement effects, accumulation depth, loop detection |
| `swarm_verify.py` | **falsification**: placebo cut-points and degree-preserving nulls against our own claims |
| `swarm_path_dependence.py` | early advantage, with and without a joined-cohort control |
| `swarm_recount.py` | separates seeded Gen-1 material from Gen-2 output |
| `swarm_transcript_analysis.py` | mines the MASO transcripts for agent reasoning |
| `swarm_cost_analysis.py` | token attribution |

`swarm_verify.py` is the one to read first: it is where three of our six published
claims died.

## Reproducing

Scripts expect the corpus at `/Users/bytedance/Downloads/swarm` and
`/Users/bytedance/Downloads/swarm-gen2`. Edit the constants at the top of each file.

Before using the citation ledger, read the data-hazard list in
`swarm-findings-registry.md` §D. In particular: Gen 1 writes the cited path under
`file`, Gen 2 under `artifact`. A parser reading only one will classify the other
generation as entirely junk. We made that error.
