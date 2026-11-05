# Maths, interpolation and mixing

63 original stereo FX sources, 22 exact patcher spellings. Each runs at 44,100 Hz
and 256 frames, with one arm and 21 ordered unit-phase drive events. Four manual
warm plus 16 timed callbacks are all checked, with no automatic warmup. Signal
forms add a varying left input and clip phase to 0..1 before the tested maths.
The raw right pilot is separate from all arithmetic and checked bit-exactly.

The independent oracle uses Lagrange/Hermite/quintic B-spline bases, ideal
trigonometry/logarithms and explicit piecewise gain/shaping equations. Asymmetric
points distinguish interpolation variants. Limits precede all compilation:
exact dyadic forms 0, ordinary maths 2e-6, t60time 1e-4 samples, ideal cosine
interpolation 1e-3. No captured output constructs or changes the oracle.

The suite observes both coordinate outputs, six generic interpolation modes,
separate six-point constructor/inlet forms, three fade curves, both pan outputs,
three-channel negative-position wrapping, quantisation ties, reversed smoothstep,
trapezoid phase wrapping, decay units and signal variation inside blocks.

`message-to-signal-v1` preserves the original native attempt. Eleven signal
pan~/xfade~ fixtures mistakenly used number messages on signal-only amplitude
ports. Their corrected graphs use explicit sig~ sources. All 63 expected streams,
all limits, and the other 52 source/module results stay unchanged. No original
hardware attempt preceded this fixture correction. The two generic six-point
constructor discrepancies are retained, with separately authored inlet controls.

Regenerate/check sources:

    python3 tests/fixtures/smoke/rnbo-mixing-shaping/generate.py --check

The installed primary XML/help/operator/XAM receipts are in each catalog row.
Public outcomes, timings and limits: [report](../../../../docs/rnbo-mixing-shaping.md).
