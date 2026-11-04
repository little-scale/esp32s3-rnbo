# RNBO signal routing and interpolation

Twenty original flat RNBO patcher graphs separately exercise the exact owner
spellings in the catalog. They use two declared audio inputs and two observed
outputs, no parameters, and ordinary strict preparation. Compilation alone is
not hardware execution.

`gate~ 2 0 0` fixes the ramp to zero and exposes both routed outputs. Integer
choices 0, 1 and 2 close/select each route. `selector~ 2` chooses between the
right input and its negative, while the second output copies the input as a
pilot. Choices outside 0/1/2 and fractional selection are not qualified.

Each exact named-bus spelling has its own stereo fixture. Two distinct names
connect the sender/receiver pair inside the RNBO graph. The canonical counterpart
is support, not an additional owner qualification. Root Max communication,
multiple senders, feedback and subpatcher boundaries are not tested here.

The four interpolation references use asymmetric literal keyframes and phases
in the closed interval [0,1], including adjacent endpoint/midpoint Float32 words.
They distinguish four-point Lagrange, full-neighbor-slope Hermite, half-slope
Catmull–Rom and centered six-point quintic B-spline. Their predeclared absolute
limit is 2e-6; the other sixteen references use zero numeric tolerance. Operation
zero-sign differences remain diagnostics. The symbolic pass comparisons return
the left operand when true, rather than a boolean.

The planned short check starts at fresh preparation with no automatic warmup,
then checks four manual warmups and sixteen timed 256-frame callbacks. These
finite scenarios do not establish full-domain behavior, other modes, sample-
offset controls, equivalent Gen/codebox behavior or optimisation gains.

Run `python3 tests/fixtures/smoke/rnbo-signal-routing/generate.py --check` to
verify generated source/catalog bytes against the installed primary metadata.
The portable references and source contracts are tested by
`python3 -m unittest tools.test_smoke_rnbo_signal_routing_reference`.
