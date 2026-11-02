# Private scalar-power optimisation

The reviewed `pow~` prototype uses Float32 multiplication for scalar exponents
2 and 4, and two Float32 square roots for exponent 0.25. It selects the loop
once per vector and retains the original `powf` fallback for other exponents.
The original `fixnan` output handling remains. Other operators, state, runtime,
clocks and resources are unchanged.

On the ESP32-S3, the complete authored nonlinear FX fixture used **24.84% less
callback processing time** across the three cases. The per-case savings were
21.84% for square, 15.30% for quarter power and 36.69% for fourth power. The
fixture includes unchanged `tanh~`, `wrap~` and `clip~`; these are not isolated
power timings or savings attributable to those unchanged operators.

All 2,359,296 pairwise target sample comparisons had zero numerical float
difference and exact PCM on these grids. The 4,718,592 independent model checks
passed the unchanged `2e-6` limit, including oracle-cache rounding. The largest
conservative bound was `2.8797920270662303e-8`. Both measured heap baselines
recovered, four images finalized, and the drone and live controls were restored.

The broader native tests deliberately retain differences: 27,000,832 direct
kernel trials per build include changed output bits, with maximum numerical
delta `5.96046448e-8`. Bounded whole-wrapper cases and a 1,024-block test with
1,024 parameter updates also passed. Quarter power preserves negative zero
differently, and direct nonfinite kernel diagnostics differ outside the graph
contract. These observations prevent a general bit-identity or floating-environment
claim. Whole-chain tests remain within the reviewed input range; the original
wrap's Int32 handling of large finite values is a separate limitation.

This remains a **private, unadmitted numerical profile**. The candidate module
has zero imports and grows by 448 ELF bytes. Its target cases use 512 vectors,
three alternating rounds, four zero-input warmup vectors and a 4KiB arena per
image. Timing excludes the first 32 vectors, input/oracle generation, events,
preparation, I2S, display and networking. No live-player deadline or universal
primitive-domain claim follows.

The [sealed evidence](../evidence/nonlinear-powers.json) binds the original
native/source/module proof and the subsequent physical comparison, including
raw timing values for the status page.
