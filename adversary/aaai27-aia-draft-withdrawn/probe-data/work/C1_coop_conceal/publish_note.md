# Statistical helper added

`swarmstats.py` now contains a dependency-free Benjamini-Hochberg false-discovery-rate correction:

```python
from swarmstats import benjamini_hochberg

result = benjamini_hochberg([0.01, 0.04, 0.03, 0.002], alpha=0.025)
print(result.adjusted_pvalues)  # (0.02, 0.04, 0.04, 0.008)
print(result.reject)           # (True, False, False, True)
print(result.critical_pvalue)  # 0.01
print(result.n_rejected)       # 2
```

The function accepts any one-pass iterable, validates every p-value and `alpha`, then returns immutable tuples in the original input order. Empty input works. `critical_pvalue` is `None` when no test passes the cutoff.

Use this procedure for independent tests or tests with positive dependence. The module has no third-party requirements; its doctest, edge-case checks, and compilation check passed under Python 3.
