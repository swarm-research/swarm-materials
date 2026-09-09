I’ll add a small, dependency-free multiple-testing helper rather than a large statistics module. The implementation should be correct on ties, empty input, invalid probabilities, and monotonic adjusted values. I’ll document the public contract, run focused examples against hand-computed answers, and leave a short note for later users.

The public function will implement the Benjamini-Hochberg step-up procedure and return an immutable named result with original-order adjusted p-values and decisions. Rejecting from the adjusted p-values keeps the decision and correction paths consistent. I’ll reject booleans, non-real values, NaN, infinity, and probabilities outside [0, 1] rather than silently coercing bad input.

The implementation is in place. Before publishing the note, I’ll check a known four-value example, a tie case, generator input, boundary alpha values, empty input, and expected failures. I’ll also compile the module so a syntax or annotation error can’t slip through.

The first test attempt exposed an environment detail, not a code failure: this machine has no `python` command. I’ll repeat the same checks with `python3`, which is the normal macOS executable.

Compilation and the focused assertions pass. Hand-picked cases can share my own mistaken assumptions, so I’ll do one more randomized comparison against statsmodels if that package is present; otherwise I’ll compare with a separate direct reference calculation. Then I’ll inspect the finished source before writing the public note.

The randomized test covered sizes 1 through 79 with repeated ties and boundary values. Statsmodels wasn’t installed, but all cases matched a separately written direct formula. The source inspection shows original-order restoration, one-based ranks, reverse cumulative minima, and input checks are all present. I’ll now write a compact usage note with an executable example and remove only the bytecode cache created during validation.

Finished: `swarmstats.py`, `publish_note.md`, and this log are the only workspace files. The cache is gone. The requested utility is correct, dependency-free, documented, and validated; no further changes are needed.
