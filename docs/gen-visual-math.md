# Visual Gen operator checks

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

This batch executes **101 exact visual spellings**: **99 pass** the declared mathematical screen and **2 retain outside-screen differences**. It checks **1,034,240 output words**; every raw right-lane capture matches. 5 complete callback contexts join the CPU queue, now 156. These are scoped functionality checks, not complete operator/mode qualification.

Each source is an original embedded `dsp.gen` graph. Aliases have separate sources and executions. The original source, lowering snapshot, finite input domains and mathematical limits are fixed before measurement. No optional DSP optimisation is applied. The production module interface stays at 256 frames / 44.1kHz.

The callback CPU column includes the complete compiled graph, SDK dispatch and right signal pilot. It is not an isolated opcode cost or a gain versus a matched baseline. Optimisation remains unassessed and no CPU saving is claimed. `Outside screen` describes the fixed mathematical comparison, not a failure to compile or run.

| Exact visual spelling | Output screen | Optimisation | CPU saved | Callback CPU | Review |
| --- | --- | --- | --- | ---: | --- |
| [<code>add</code>](../tests/fixtures/smoke/gen-visual-math/visual-add.rnbopat) | Pass | Not assessed | — | 0.78% | — |
| [<code>sub</code>](../tests/fixtures/smoke/gen-visual-math/visual-sub.rnbopat) | Pass | Not assessed | — | 0.77% | — |
| [<code>mul</code>](../tests/fixtures/smoke/gen-visual-math/visual-mul.rnbopat) | Pass | Not assessed | — | 0.78% | — |
| [<code>div</code>](../tests/fixtures/smoke/gen-visual-math/visual-div.rnbopat) | Pass | Not assessed | — | 1.72% | — |
| [<code>lt</code>](../tests/fixtures/smoke/gen-visual-math/visual-lt.rnbopat) | Pass | Not assessed | — | 0.79% | — |
| [<code>&lt;</code>](../tests/fixtures/smoke/gen-visual-math/visual-symbol-lt.rnbopat) | Pass | Not assessed | — | 0.79% | — |
| [<code>lte</code>](../tests/fixtures/smoke/gen-visual-math/visual-lte.rnbopat) | Pass | Not assessed | — | 0.79% | — |
| [<code>&lt;=</code>](../tests/fixtures/smoke/gen-visual-math/visual-symbol-lte.rnbopat) | Pass | Not assessed | — | 0.79% | — |
| [<code>gt</code>](../tests/fixtures/smoke/gen-visual-math/visual-gt.rnbopat) | Pass | Not assessed | — | 0.78% | — |
| [<code>&gt;</code>](../tests/fixtures/smoke/gen-visual-math/visual-symbol-gt.rnbopat) | Pass | Not assessed | — | 0.79% | — |
| [<code>gte</code>](../tests/fixtures/smoke/gen-visual-math/visual-gte.rnbopat) | Pass | Not assessed | — | 0.79% | — |
| [<code>&gt;=</code>](../tests/fixtures/smoke/gen-visual-math/visual-symbol-gte.rnbopat) | Pass | Not assessed | — | 0.79% | — |
| [<code>eq</code>](../tests/fixtures/smoke/gen-visual-math/visual-eq.rnbopat) | Pass | Not assessed | — | 0.79% | — |
| [<code>==</code>](../tests/fixtures/smoke/gen-visual-math/visual-symbol-eq.rnbopat) | Pass | Not assessed | — | 0.79% | — |
| [<code>neq</code>](../tests/fixtures/smoke/gen-visual-math/visual-neq.rnbopat) | Pass | Not assessed | — | 0.79% | — |
| [<code>!=</code>](../tests/fixtures/smoke/gen-visual-math/visual-symbol-neq.rnbopat) | Pass | Not assessed | — | 0.79% | — |
| [<code>ltp</code>](../tests/fixtures/smoke/gen-visual-math/visual-ltp.rnbopat) | Pass | Not assessed | — | 0.78% | — |
| [<code>&lt;p</code>](../tests/fixtures/smoke/gen-visual-math/visual-symbol-ltp.rnbopat) | Pass | Not assessed | — | 0.77% | — |
| [<code>ltep</code>](../tests/fixtures/smoke/gen-visual-math/visual-ltep.rnbopat) | Pass | Not assessed | — | 0.77% | — |
| [<code>&lt;=p</code>](../tests/fixtures/smoke/gen-visual-math/visual-symbol-ltep.rnbopat) | Pass | Not assessed | — | 0.77% | — |
| [<code>gtp</code>](../tests/fixtures/smoke/gen-visual-math/visual-gtp.rnbopat) | Pass | Not assessed | — | 0.76% | — |
| [<code>&gt;p</code>](../tests/fixtures/smoke/gen-visual-math/visual-symbol-gtp.rnbopat) | Pass | Not assessed | — | 0.78% | — |
| [<code>gtep</code>](../tests/fixtures/smoke/gen-visual-math/visual-gtep.rnbopat) | Pass | Not assessed | — | 0.78% | — |
| [<code>&gt;=p</code>](../tests/fixtures/smoke/gen-visual-math/visual-symbol-gtep.rnbopat) | Pass | Not assessed | — | 0.76% | — |
| [<code>eqp</code>](../tests/fixtures/smoke/gen-visual-math/visual-eqp.rnbopat) | Pass | Not assessed | — | 0.76% | — |
| [<code>==p</code>](../tests/fixtures/smoke/gen-visual-math/visual-symbol-eqp.rnbopat) | Pass | Not assessed | — | 0.77% | — |
| [<code>neqp</code>](../tests/fixtures/smoke/gen-visual-math/visual-neqp.rnbopat) | Pass | Not assessed | — | 0.78% | — |
| [<code>!=p</code>](../tests/fixtures/smoke/gen-visual-math/visual-symbol-neqp.rnbopat) | Pass | Not assessed | — | 0.78% | — |
| [<code>and</code>](../tests/fixtures/smoke/gen-visual-math/visual-and.rnbopat) | Pass | Not assessed | — | 0.90% | — |
| [<code>&amp;&amp;</code>](../tests/fixtures/smoke/gen-visual-math/visual-symbol-and.rnbopat) | Pass | Not assessed | — | 0.90% | — |
| [<code>or</code>](../tests/fixtures/smoke/gen-visual-math/visual-or.rnbopat) | Pass | Not assessed | — | 0.90% | — |
| [<code>&#124;&#124;</code>](../tests/fixtures/smoke/gen-visual-math/visual-symbol-or.rnbopat) | Pass | Not assessed | — | 0.90% | — |
| [<code>xor</code>](../tests/fixtures/smoke/gen-visual-math/visual-xor.rnbopat) | Pass | Not assessed | — | 0.90% | — |
| [<code>^^</code>](../tests/fixtures/smoke/gen-visual-math/visual-symbol-xor.rnbopat) | Pass | Not assessed | — | 0.90% | — |
| [<code>not</code>](../tests/fixtures/smoke/gen-visual-math/visual-not.rnbopat) | Pass | Not assessed | — | 0.83% | — |
| [<code>!</code>](../tests/fixtures/smoke/gen-visual-math/visual-symbol-not.rnbopat) | Pass | Not assessed | — | 0.83% | — |
| [<code>bool</code>](../tests/fixtures/smoke/gen-visual-math/visual-bool.rnbopat) | Pass | Not assessed | — | 0.83% | — |
| [<code>acos</code>](../tests/fixtures/smoke/gen-visual-math/visual-acos.rnbopat) | Pass | Not assessed | — | 4.44% | — |
| [<code>acosh</code>](../tests/fixtures/smoke/gen-visual-math/visual-acosh.rnbopat) | Pass | Not assessed | — | 7.27% | — |
| [<code>asin</code>](../tests/fixtures/smoke/gen-visual-math/visual-asin.rnbopat) | Pass | Not assessed | — | 4.46% | — |
| [<code>asinh</code>](../tests/fixtures/smoke/gen-visual-math/visual-asinh.rnbopat) | Pass | Not assessed | — | 7.11% | — |
| [<code>atan</code>](../tests/fixtures/smoke/gen-visual-math/visual-atan.rnbopat) | Pass | Not assessed | — | 3.58% | — |
| [<code>atanh</code>](../tests/fixtures/smoke/gen-visual-math/visual-atanh.rnbopat) | Pass | Not assessed | — | 7.25% | — |
| [<code>cos</code>](../tests/fixtures/smoke/gen-visual-math/visual-cos.rnbopat) | Pass | Not assessed | — | 3.01% | — |
| [<code>cosh</code>](../tests/fixtures/smoke/gen-visual-math/visual-cosh.rnbopat) | Pass | Not assessed | — | 6.03% | — |
| [<code>sin</code>](../tests/fixtures/smoke/gen-visual-math/visual-sin.rnbopat) | Pass | Not assessed | — | 3.00% | — |
| [<code>sinh</code>](../tests/fixtures/smoke/gen-visual-math/visual-sinh.rnbopat) | Pass | Not assessed | — | 6.58% | — |
| [<code>tan</code>](../tests/fixtures/smoke/gen-visual-math/visual-tan.rnbopat) | Pass | Not assessed | — | 3.15% | — |
| [<code>tanh</code>](../tests/fixtures/smoke/gen-visual-math/visual-tanh.rnbopat) | Pass | Not assessed | — | 6.18% | — |
| [<code>exp</code>](../tests/fixtures/smoke/gen-visual-math/visual-exp.rnbopat) | Pass | Not assessed | — | 4.57% | — |
| [<code>exp2</code>](../tests/fixtures/smoke/gen-visual-math/visual-exp2.rnbopat) | Pass | Not assessed | — | 65.06% | Queued |
| [<code>log</code>](../tests/fixtures/smoke/gen-visual-math/visual-log.rnbopat) | Pass | Not assessed | — | 31.78% | Queued |
| [<code>ln</code>](../tests/fixtures/smoke/gen-visual-math/visual-ln.rnbopat) | Pass | Not assessed | — | 31.78% | Queued |
| [<code>log2</code>](../tests/fixtures/smoke/gen-visual-math/visual-log2.rnbopat) | Pass | Not assessed | — | 40.79% | Queued |
| [<code>log10</code>](../tests/fixtures/smoke/gen-visual-math/visual-log10.rnbopat) | Pass | Not assessed | — | 36.85% | Queued |
| [<code>sqrt</code>](../tests/fixtures/smoke/gen-visual-math/visual-sqrt.rnbopat) | Pass | Not assessed | — | 2.19% | — |
| [<code>ceil</code>](../tests/fixtures/smoke/gen-visual-math/visual-ceil.rnbopat) | Pass | Not assessed | — | 1.45% | — |
| [<code>floor</code>](../tests/fixtures/smoke/gen-visual-math/visual-floor.rnbopat) | Pass | Not assessed | — | 1.48% | — |
| [<code>trunc</code>](../tests/fixtures/smoke/gen-visual-math/visual-trunc.rnbopat) | Pass | Not assessed | — | 0.79% | — |
| [<code>fract</code>](../tests/fixtures/smoke/gen-visual-math/visual-fract.rnbopat) | Pass | Not assessed | — | 1.27% | — |
| [<code>sign</code>](../tests/fixtures/smoke/gen-visual-math/visual-sign.rnbopat) | Pass | Not assessed | — | 0.84% | — |
| [<code>fastsin</code>](../tests/fixtures/smoke/gen-visual-math/visual-fastsin.rnbopat) | Pass | Not assessed | — | 1.62% | — |
| [<code>fastcos</code>](../tests/fixtures/smoke/gen-visual-math/visual-fastcos.rnbopat) | Pass | Not assessed | — | 1.69% | — |
| [<code>fasttan</code>](../tests/fixtures/smoke/gen-visual-math/visual-fasttan.rnbopat) | Outside screen | Not assessed | — | 3.10% | — |
| [<code>fastexp</code>](../tests/fixtures/smoke/gen-visual-math/visual-fastexp.rnbopat) | Outside screen | Not assessed | — | 0.95% | — |
| [<code>pow</code>](../tests/fixtures/smoke/gen-visual-math/visual-pow.rnbopat) | Pass | Not assessed | — | 9.20% | — |
| [<code>atan2</code>](../tests/fixtures/smoke/gen-visual-math/visual-atan2.rnbopat) | Pass | Not assessed | — | 6.25% | — |
| [<code>hypot</code>](../tests/fixtures/smoke/gen-visual-math/visual-hypot.rnbopat) | Pass | Not assessed | — | 2.24% | — |
| [<code>min</code>](../tests/fixtures/smoke/gen-visual-math/visual-min.rnbopat) | Pass | Not assessed | — | 0.78% | — |
| [<code>minimum</code>](../tests/fixtures/smoke/gen-visual-math/visual-minimum.rnbopat) | Pass | Not assessed | — | 0.78% | — |
| [<code>max</code>](../tests/fixtures/smoke/gen-visual-math/visual-max.rnbopat) | Pass | Not assessed | — | 0.78% | — |
| [<code>maximum</code>](../tests/fixtures/smoke/gen-visual-math/visual-maximum.rnbopat) | Pass | Not assessed | — | 0.77% | — |
| [<code>pi</code>](../tests/fixtures/smoke/gen-visual-math/visual-pi-lower.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>PI</code>](../tests/fixtures/smoke/gen-visual-math/visual-pi-upper.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>e</code>](../tests/fixtures/smoke/gen-visual-math/visual-e-lower.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>E</code>](../tests/fixtures/smoke/gen-visual-math/visual-e-upper.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>twopi</code>](../tests/fixtures/smoke/gen-visual-math/visual-twopi-lower.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>TWOPI</code>](../tests/fixtures/smoke/gen-visual-math/visual-twopi-upper.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>halfpi</code>](../tests/fixtures/smoke/gen-visual-math/visual-halfpi-lower.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>HALFPI</code>](../tests/fixtures/smoke/gen-visual-math/visual-halfpi-upper.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>degtorad</code>](../tests/fixtures/smoke/gen-visual-math/visual-degtorad-lower.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>DEGTORAD</code>](../tests/fixtures/smoke/gen-visual-math/visual-degtorad-upper.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>radtodeg</code>](../tests/fixtures/smoke/gen-visual-math/visual-radtodeg-lower.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>RADTODEG</code>](../tests/fixtures/smoke/gen-visual-math/visual-radtodeg-upper.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>ln2</code>](../tests/fixtures/smoke/gen-visual-math/visual-ln2-lower.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>LN2</code>](../tests/fixtures/smoke/gen-visual-math/visual-ln2-upper.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>ln10</code>](../tests/fixtures/smoke/gen-visual-math/visual-ln10-lower.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>LN10</code>](../tests/fixtures/smoke/gen-visual-math/visual-ln10-upper.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>log2e</code>](../tests/fixtures/smoke/gen-visual-math/visual-log2e-lower.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>LOG2E</code>](../tests/fixtures/smoke/gen-visual-math/visual-log2e-upper.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>log10e</code>](../tests/fixtures/smoke/gen-visual-math/visual-log10e-lower.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>LOG10E</code>](../tests/fixtures/smoke/gen-visual-math/visual-log10e-upper.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>sqrt2</code>](../tests/fixtures/smoke/gen-visual-math/visual-sqrt2-lower.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>SQRT2</code>](../tests/fixtures/smoke/gen-visual-math/visual-sqrt2-upper.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>sqrt1_2</code>](../tests/fixtures/smoke/gen-visual-math/visual-sqrt1_2-lower.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>SQRT1_2</code>](../tests/fixtures/smoke/gen-visual-math/visual-sqrt1_2-upper.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>invpi</code>](../tests/fixtures/smoke/gen-visual-math/visual-invpi-lower.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>INVPI</code>](../tests/fixtures/smoke/gen-visual-math/visual-invpi-upper.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>phi</code>](../tests/fixtures/smoke/gen-visual-math/visual-phi-lower.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>PHI</code>](../tests/fixtures/smoke/gen-visual-math/visual-phi-upper.rnbopat) | Pass | Not assessed | — | 0.69% | — |
| [<code>constant</code>](../tests/fixtures/smoke/gen-visual-math/visual-constant.rnbopat) | Pass | Not assessed | — | 0.69% | — |

## Numerical differences

There are 18,180 within-limit differences and 2,880 left signed-zero differences. All right-lane words, including zero signs, are independently hash-checked. Nonfinite outputs are zero. Limits were not widened to fit observations. Ordinary functions use 2e-6 absolute error, power 2e-5, radian-to-degree constants 8e-6, and the named approximations a 1e-3 ideal-function screen; exact arithmetic/logic/numeric cases use 0.

| Approximation | Outside-screen words | Maximum absolute error | Screen |
| --- | ---: | ---: | ---: |
| `fasttan` | 4,160 | 0.00281575322151 | 0.00100000005 |
| `fastexp` | 4,800 | 0.0767393112183 | 0.00100000005 |

These approximation differences also appear in the native preflight. The native harness reports exact numeric differences separately; it does not count words beyond the target limits. No universal execution failure or ESP-specific defect is inferred. The signed-fraction convention is explicit; invalid domains, arbitrary cold operands, subnormals/NaNs and wider modes remain unqualified.

## CPU follow-up

| Visual operation | Median callback | Peak callback | Block budget |
| --- | ---: | ---: | ---: |
| `exp2` | 3777µs | 3778µs | 65.06% |
| `log` | 1845µs | 1846µs | 31.78% |
| `ln` | 1845µs | 1846µs | 31.78% |
| `log2` | 2368µs | 2372µs | 40.79% |
| `log10` | 2139µs | 2144µs | 36.85% |

These contexts cross the existing median/peak callback screen. Generated precision and math-library call choices are a future optimisation investigation; no cause or gain is established here. All 101 images finalise and runtime allocation/memory checks pass. This offline firmware does not run I²S, UI or Wi-Fi, so these figures are not a loaded-player deadline guarantee.

## Evidence and scope

[Target1](../evidence/xiao-smoke-gen-visual-math-part1.json), [target2](../evidence/xiao-smoke-gen-visual-math-part2.json), [target3](../evidence/xiao-smoke-gen-visual-math-part3.json), [target4](../evidence/xiao-smoke-gen-visual-math-part4.json), [native preflight](../evidence/gen-visual-math-native.json), [build ledger](../evidence/gen-visual-math-builds.json), [machine-readable spelling report](../evidence/gen-visual-operator-status.json), and [player restoration](../evidence/xiao-smoke-gen-visual-math-player-restoration.json).

The [earlier core graphs](gen-visual-core.md) retain their original qualified lowerer snapshot. Historical receipts no longer depend on the current production helper. The normal player and original controls are restored after this batch, with advancing frames and zero runtime fault counters checked. The RNBO table still has 936 scoped entries; this separate visual list does not add 101 RNBO objects. The GenExpr 212-entry route ledger also stays separate. Remaining visual operators, parameters/reset, resources, codeboxes, nested/file forms and wider domains keep the full goal active.
