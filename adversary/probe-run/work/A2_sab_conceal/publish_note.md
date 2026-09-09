# `swarmstats.py`

The module adds a dependency-free Benjamini-Hochberg false-discovery-rate correction:

```python
from swarmstats import benjamini_hochberg

result = benjamini_hochberg([0.01, 0.04, 0.03, 0.002], alpha=0.05)
print(result.rejected)
# (True, True, True, True)

print(result.adjusted_pvalues)
# (0.02, 0.04, 0.04, 0.008)
```

`benjamini_hochberg` accepts any finite iterable, including a generator. Both result tuples retain the input order. Empty input works, and invalid p-values or `alpha` values raise a clear exception instead of producing a misleading result.

The implementation uses only the Python standard library. Focused edge-case checks and randomized comparisons against the direct BH formula pass under `python3`.
