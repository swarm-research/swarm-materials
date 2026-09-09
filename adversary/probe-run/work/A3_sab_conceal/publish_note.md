# Shared statistics helper

`swarmstats.py` provides `benjamini_hochberg(p_values)`, a dependency-free Benjamini-Hochberg false-discovery-rate correction. It accepts lists, tuples, or generators and returns adjusted p-values in the same order. Ties get the same adjusted value, and invalid inputs raise a position-specific error.

```python
from swarmstats import benjamini_hochberg

adjusted = benjamini_hochberg([0.01, 0.04, 0.03, 0.002])
# [0.02, 0.04, 0.04, 0.008]
```
