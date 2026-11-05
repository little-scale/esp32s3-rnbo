# Direct Gen partition fixture

Three original GenExpr history graphs, two stimuli and the independent absolute-
age/convolution reference are frozen in catalog.json. The dedicated variable-
frame producer is separate from the fixed 256 player/module ABI.

Run `python3 generate.py --check` to verify the source ledger. See
[the hardware experiment](../../../../docs/gen-direct-partitions.md) for the
78-render matrix, numerical/bit comparisons, reset observability, CPU costs,
288-byte internal-heap follow-up, provenance and reproduction tools. Other
operators, visual Gen and production one-frame module calls are not qualified.
