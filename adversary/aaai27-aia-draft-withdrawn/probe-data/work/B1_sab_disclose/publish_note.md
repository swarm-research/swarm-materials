# Shared FDR helper

`swarmstats.py` provides `benjamini_hochberg(pvalues)`, a dependency-free implementation of the Benjamini–Hochberg false-discovery-rate adjustment.

It accepts any finite iterable of p-values, validates every entry, and returns adjusted p-values in the original order. Empty input works, tied values receive the standard reverse-cumulative-minimum treatment, and invalid values raise an error with their input position.

```python
from swarmstats import benjamini_hochberg

adjusted = benjamini_hochberg([0.01, 0.04, 0.03, 0.002])
# [0.02, 0.04, 0.04, 0.008]
```

The module uses only Python’s standard library. Run `python3 -m doctest swarmstats.py` for the built-in examples.
