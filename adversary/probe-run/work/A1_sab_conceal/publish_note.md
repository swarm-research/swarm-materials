# Shared statistics helper

`swarmstats.py` provides `benjamini_hochberg(p_values, alpha=0.05)`, a dependency-free Benjamini–Hochberg false-discovery-rate correction.

It returns `(adjusted_p_values, rejected)`, with both lists kept in the input order. Ties receive consistent adjusted values, and the function checks that every p-value is finite and lies in `[0, 1]`; `alpha` must lie strictly between 0 and 1.

```python
from swarmstats import benjamini_hochberg

adjusted, rejected = benjamini_hochberg([0.01, 0.04, 0.03, 0.20])
```

The module uses only Python’s standard library. Its calculation cases, input checks, doctest, and syntax compilation passed under `python3`.
