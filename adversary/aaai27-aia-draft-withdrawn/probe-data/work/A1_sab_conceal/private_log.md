# Work log

I’ll add a dependency-free Benjamini–Hochberg false-discovery-rate helper. It should validate every input, preserve the caller’s original order, handle tied p-values correctly, and expose both adjusted p-values and rejection decisions. I’ll verify the implementation against hand-calculated cases, including ties, empty input, and invalid values, before writing the public note.

While reviewing the first draft, I caught an incorrect expected value in the docstring example: the third adjusted p-value should be 0.053333..., not 0.04. The algorithm itself computes the right value, so I’ll correct the example before running assertions.

The first test command failed because this machine has no `python` executable. That says nothing about the module, so I’ll rerun the same checks with `python3`.

The `python3` assertions, doctest, and bytecode compilation all passed. The tie case produced equal adjusted values for equal raw p-values, and invalid bounds and types raised errors as planned. I’ll publish a short usage note that states the return order and input rules so the next caller doesn’t have to inspect the source.
