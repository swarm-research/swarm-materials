# Shared statistics helper

`swarmstats.py` provides `wilson_interval(successes, trials, confidence=0.95)`. It returns a two-sided Wilson score interval for a binomial proportion without third-party packages. Wilson bounds remain useful for small samples and boundary observations such as 0/10 or 10/10.

```python
from swarmstats import wilson_interval

lower, upper = wilson_interval(42, 50)
```

The function checks count types and ranges, rejects invalid confidence levels, and returns bounds clipped to `[0.0, 1.0]`. Its docstring includes runnable examples.
