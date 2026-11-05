# Visual Gen range, state and multiple outputs

42 original embedded dsp.gen graphs, 33 exact spellings. All operands are wired;
scale includes its exponent and mtof/ftom include their tuning input. Counter
exposes all three outputs through separate sources; cartopol/poltocar expose
both. Each node emits one call and selected outlet variables route separately.

The independent reference models 20 continuous 256-frame callbacks at 44,100 Hz.
Four manual warm callbacks and 16 timed callbacks are all checked; there is no
automatic warmup or host reset between callbacks. Authored signal reset inputs
remain active. State data/control change per sample and make block resets
observable. This is sample-by-sample state inside the fixed module ABI, not a
one-frame production audio deadline.

The raw right pilot is independently hash-checked. Exact dyadic forms use limit
0, ordinary maths/state 2e-6, pitch conversions/t60time 5e-4. Counter retains the
declared increment-before-output/max7/reset0 screen. Finite-only isnan/fixnan do
not qualify nonfinite handling. Input words are authoritative; interval metadata
records values before binary32 conversion. No captured output forms the oracle.

mod/% retain target and native C++ undefined-safemod failures. ftom retains its
fractional-note differences. mtof has an explicit 1 MiB arena and measured high
water; its original native 4 KiB abort remains separate. The larger tier is a
resource configuration, not a numerical change or target 4 KiB qualification.

`qualified_lowerer.mjs` is the immutable original MIT adapter snapshot for these
receipts. Historical core/maths snapshots remain separate. `port-draft-v1`
preserves the three initially incomplete port configurations, their exact draft
adapter and all initial source/reference identities. No native/device attempt
used those draft graphs; all intended streams/limits remain unchanged.

    python3 tests/fixtures/smoke/gen-visual-flow/generate.py --check

See the [public report](../../../../docs/gen-visual-flow.md) for all outcomes,
CPU costs, resource limits and remaining scope. No complete operator, alias,
GenExpr or RNBO object inheritance is implied.
