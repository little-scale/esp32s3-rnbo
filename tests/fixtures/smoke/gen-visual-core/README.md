# Embedded visual Gen core fixtures

These 21 original `.rnbopat` files contain actual `genpatcher.patcher` graphs,
using the installed help patch's `dsp.gen` serialization shape. They contain no
saved/authored `expr`. `generate.py --check` reproduces every graph and catalog.
`reference.py` independently supplies dyadic arithmetic, sample delays, state
permutations and finite-convolution/matrix-power expectations; it never evaluates
lowered code or traverses the fixture graph to derive expected samples.

Cases cover direct/swapped routing, four fully wired binary operations, four
fixed-operand operations, negation, absolute value, one-/two-sample histories,
fanout, two-state swap, three-state rotation, an unconnected initialized history,
and bounded single/coupled feedback. History initial values, repeated input
patterns, the first sample and callback boundaries are included. Division's
right input is strictly positive. There are 20 continuous256-frame calls at
44.1 kHz (manual warm4, timed16); no automatic warmup or host events. Feedback
uses2e-6 absolute tolerance; other cases use exact numeric comparison, with
zero signs recorded separately. This is scoped short functional qualification,
not all-domain/operator/alias/mode, resource or one-frame player qualification.

`host/export/gen_visual.mjs` is the original frontend lowerer. It explicitly
validates arity and routes, snapshots old histories and commits next states
last. Unknown operators and ambiguous forms reject. The source, bridge and
reference are bound in the hardware plan; mutation tests exercise the actual
admission/collector paths. Producer and numerical reference remain separate.
The [full report](../../../../docs/gen-visual-core.md) lists supported forms,
remaining work, timings, numerical differences and restoration evidence.
