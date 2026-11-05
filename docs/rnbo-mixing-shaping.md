# RNBO maths, interpolation and mixing checks

The batch covers **63 scenarios across 22 exact spellings**. **61 pass** their fixed output screens and **2 retain outside-screen results**, across **645,120 output words and 1,386 control actions**. All raw right captures match and no nonfinite output occurs. There are 54,800 within-limit differences and 0 observational left zero-sign differences. **5 new callback contexts** enter review, bringing the queue to **162**.

One arm action precedes 21 ordered unit-phase drives, with repeats, same-callback updates and quiet holds. Each source runs four manual warm and sixteen timed full 256-frame callbacks at 44,100 Hz, with zero automatic warm callbacks. Signal forms use `clip(binary32(drive + varying left input),0,1)`, so their inputs vary inside blocks. The independent raw right pilot includes signed zero, subnormals and finite extrema. Actual and normalised parameter values are read back by resolved parameter ID.

References use independent Lagrange, Hermite, centered quintic B-spline, ideal trigonometric/logarithmic and piecewise shaping equations. Asymmetric control points distinguish interpolation modes. Limits were fixed before compilation: exact dyadic forms 0, normal maths 2e-6, t60time 1e-4 samples, cosine interpolation ideal-screen 1e-3. Ordinary fade cosines retain 2e-6. These screens are not universal accuracy guarantees. Constructor and inlet forms keep the same intended control points and expected streams.

| Exact spelling | Scenario | Outcome | Median / peak µs | Callback CPU | Setter total / peak µs |
| --- | --- | --- | ---: | ---: | ---: |
| [`cartopol`](../tests/fixtures/smoke/rnbo-mixing-shaping/cartopol-positive-y-out0.rnbopat) | cartopol-positive-y-out0 | Pass | 76 / 80 | 1.31% | 209 / 37 |
| [`cartopol`](../tests/fixtures/smoke/rnbo-mixing-shaping/cartopol-positive-y-out1.rnbopat) | cartopol-positive-y-out1 | Pass | 76 / 80 | 1.31% | 211 / 38 |
| [`cartopol`](../tests/fixtures/smoke/rnbo-mixing-shaping/cartopol-negative-y-out0.rnbopat) | cartopol-negative-y-out0 | Pass | 76 / 80 | 1.31% | 213 / 37 |
| [`cartopol`](../tests/fixtures/smoke/rnbo-mixing-shaping/cartopol-negative-y-out1.rnbopat) | cartopol-negative-y-out1 | Pass | 76 / 80 | 1.31% | 213 / 37 |
| [`poltocar`](../tests/fixtures/smoke/rnbo-mixing-shaping/poltocar-out0.rnbopat) | poltocar-out0 | Pass | 76.5 / 81 | 1.32% | 202 / 34 |
| [`poltocar`](../tests/fixtures/smoke/rnbo-mixing-shaping/poltocar-out1.rnbopat) | poltocar-out1 | Pass | 77 / 81 | 1.33% | 208 / 35 |
| [`cosineinterp`](../tests/fixtures/smoke/rnbo-mixing-shaping/cosineinterp-event.rnbopat) | cosineinterp-event | Pass | 75.5 / 76 | 1.30% | 255 / 33 |
| [`cubicinterp`](../tests/fixtures/smoke/rnbo-mixing-shaping/cubicinterp-event.rnbopat) | cubicinterp-event | Pass | 76 / 80 | 1.31% | 263 / 38 |
| [`fastcubicinterp`](../tests/fixtures/smoke/rnbo-mixing-shaping/fastcubicinterp-event.rnbopat) | fastcubicinterp-event | Pass | 76 / 81 | 1.31% | 166 / 34 |
| [`splineinterp`](../tests/fixtures/smoke/rnbo-mixing-shaping/splineinterp-event.rnbopat) | splineinterp-event | Pass | 76 / 81 | 1.31% | 274 / 34 |
| [`spline6interp`](../tests/fixtures/smoke/rnbo-mixing-shaping/spline6interp-event.rnbopat) | spline6interp-event | Pass | 77 / 77 | 1.33% | 172 / 33 |
| [`interp`](../tests/fixtures/smoke/rnbo-mixing-shaping/interp-linear.rnbopat) | interp-linear | Pass | 77 / 81 | 1.33% | 163 / 33 |
| [`interp`](../tests/fixtures/smoke/rnbo-mixing-shaping/interp-cosine.rnbopat) | interp-cosine | Pass | 76 / 80 | 1.31% | 255 / 33 |
| [`interp`](../tests/fixtures/smoke/rnbo-mixing-shaping/interp-cubic.rnbopat) | interp-cubic | Pass | 75 / 76 | 1.29% | 265 / 38 |
| [`interp`](../tests/fixtures/smoke/rnbo-mixing-shaping/interp-fastcubic.rnbopat) | interp-fastcubic | Pass | 77 / 82 | 1.33% | 165 / 34 |
| [`interp`](../tests/fixtures/smoke/rnbo-mixing-shaping/interp-spline.rnbopat) | interp-spline | Pass | 77 / 81 | 1.33% | 273 / 34 |
| [`interp`](../tests/fixtures/smoke/rnbo-mixing-shaping/interp-spline6.rnbopat) | interp-spline6 | Outside screen | 77 / 77 | 1.33% | 171 / 33 |
| [`interp`](../tests/fixtures/smoke/rnbo-mixing-shaping/interp-spline6-inlets.rnbopat) | interp-spline6-inlets | Pass | 75 / 76 | 1.29% | 172 / 33 |
| [`interp~`](../tests/fixtures/smoke/rnbo-mixing-shaping/interp-signal-linear.rnbopat) | interp-signal-linear | Pass | 102 / 105 | 1.76% | 175 / 32 |
| [`interp~`](../tests/fixtures/smoke/rnbo-mixing-shaping/interp-signal-cosine.rnbopat) | interp-signal-cosine | Pass | 1195 / 1218 | 20.59% | 153 / 32 |
| [`interp~`](../tests/fixtures/smoke/rnbo-mixing-shaping/interp-signal-cubic.rnbopat) | interp-signal-cubic | Pass | 1204.5 / 1210 | 20.75% | 159 / 32 |
| [`interp~`](../tests/fixtures/smoke/rnbo-mixing-shaping/interp-signal-fastcubic.rnbopat) | interp-signal-fastcubic | Pass | 120 / 125 | 2.07% | 166 / 33 |
| [`interp~`](../tests/fixtures/smoke/rnbo-mixing-shaping/interp-signal-spline.rnbopat) | interp-signal-spline | Pass | 121 / 125 | 2.08% | 164 / 32 |
| [`interp~`](../tests/fixtures/smoke/rnbo-mixing-shaping/interp-signal-spline6.rnbopat) | interp-signal-spline6 | Outside screen | 141 / 145 | 2.43% | 163 / 33 |
| [`interp~`](../tests/fixtures/smoke/rnbo-mixing-shaping/interp-signal-spline6-inlets.rnbopat) | interp-signal-spline6-inlets | Pass | 141 / 142 | 2.43% | 172 / 39 |
| [`kink`](../tests/fixtures/smoke/rnbo-mixing-shaping/kink-slope2p0.rnbopat) | kink-slope2p0 | Pass | 76 / 80 | 1.31% | 218 / 33 |
| [`kink`](../tests/fixtures/smoke/rnbo-mixing-shaping/kink-slope0p75.rnbopat) | kink-slope0p75 | Pass | 76 / 80 | 1.31% | 200 / 33 |
| [`mix`](../tests/fixtures/smoke/rnbo-mixing-shaping/mix-weight0p25.rnbopat) | mix-weight0p25 | Pass | 76 / 77 | 1.31% | 168 / 33 |
| [`mix`](../tests/fixtures/smoke/rnbo-mixing-shaping/mix-weight0p75.rnbopat) | mix-weight0p75 | Pass | 76 / 81 | 1.31% | 161 / 33 |
| [`mix`](../tests/fixtures/smoke/rnbo-mixing-shaping/mix-moving-weight.rnbopat) | mix-moving-weight | Pass | 76 / 80 | 1.31% | 167 / 33 |
| [`pan`](../tests/fixtures/smoke/rnbo-mixing-shaping/pan-lin-out0.rnbopat) | pan-lin-out0 | Pass | 75 / 76 | 1.29% | 173 / 34 |
| [`pan`](../tests/fixtures/smoke/rnbo-mixing-shaping/pan-lin-out1.rnbopat) | pan-lin-out1 | Pass | 76 / 80 | 1.31% | 173 / 34 |
| [`pan`](../tests/fixtures/smoke/rnbo-mixing-shaping/pan-eqpower-out0.rnbopat) | pan-eqpower-out0 | Pass | 75 / 80 | 1.29% | 190 / 33 |
| [`pan`](../tests/fixtures/smoke/rnbo-mixing-shaping/pan-eqpower-out1.rnbopat) | pan-eqpower-out1 | Pass | 77 / 81 | 1.33% | 186 / 33 |
| [`pan`](../tests/fixtures/smoke/rnbo-mixing-shaping/pan-cos-out0.rnbopat) | pan-cos-out0 | Pass | 75.5 / 80 | 1.30% | 432 / 42 |
| [`pan`](../tests/fixtures/smoke/rnbo-mixing-shaping/pan-cos-out1.rnbopat) | pan-cos-out1 | Pass | 76 / 80 | 1.31% | 440 / 43 |
| [`pan~`](../tests/fixtures/smoke/rnbo-mixing-shaping/pan-signal-lin-out0.rnbopat) | pan-signal-lin-out0 | Pass | 197 / 202 | 3.39% | 161 / 31 |
| [`pan~`](../tests/fixtures/smoke/rnbo-mixing-shaping/pan-signal-lin-out1.rnbopat) | pan-signal-lin-out1 | Pass | 195 / 200 | 3.36% | 159 / 31 |
| [`pan~`](../tests/fixtures/smoke/rnbo-mixing-shaping/pan-signal-eqpower-out0.rnbopat) | pan-signal-eqpower-out0 | Pass | 361 / 365 | 6.22% | 170 / 36 |
| [`pan~`](../tests/fixtures/smoke/rnbo-mixing-shaping/pan-signal-eqpower-out1.rnbopat) | pan-signal-eqpower-out1 | Pass | 359 / 365 | 6.18% | 163 / 34 |
| [`pan~`](../tests/fixtures/smoke/rnbo-mixing-shaping/pan-signal-cos-out0.rnbopat) | pan-signal-cos-out0 | Pass | 3869.5 / 3954 | 66.66% | 155 / 32 |
| [`pan~`](../tests/fixtures/smoke/rnbo-mixing-shaping/pan-signal-cos-out1.rnbopat) | pan-signal-cos-out1 | Pass | 3871 / 3955 | 66.68% | 157 / 33 |
| [`xfade`](../tests/fixtures/smoke/rnbo-mixing-shaping/xfade-lin.rnbopat) | xfade-lin | Pass | 76 / 80 | 1.31% | 177 / 33 |
| [`xfade`](../tests/fixtures/smoke/rnbo-mixing-shaping/xfade-eqpower.rnbopat) | xfade-eqpower | Pass | 76 / 80 | 1.31% | 196 / 33 |
| [`xfade`](../tests/fixtures/smoke/rnbo-mixing-shaping/xfade-cos.rnbopat) | xfade-cos | Pass | 76 / 80 | 1.31% | 443 / 43 |
| [`xfade~`](../tests/fixtures/smoke/rnbo-mixing-shaping/xfade-signal-lin.rnbopat) | xfade-signal-lin | Pass | 227 / 232 | 3.91% | 161 / 32 |
| [`xfade~`](../tests/fixtures/smoke/rnbo-mixing-shaping/xfade-signal-eqpower.rnbopat) | xfade-signal-eqpower | Pass | 400 / 405 | 6.89% | 160 / 32 |
| [`xfade~`](../tests/fixtures/smoke/rnbo-mixing-shaping/xfade-signal-cos.rnbopat) | xfade-signal-cos | Pass | 3905 / 3989 | 67.27% | 156 / 33 |
| [`phasewrap`](../tests/fixtures/smoke/rnbo-mixing-shaping/phasewrap-wide.rnbopat) | phasewrap-wide | Pass | 76 / 76 | 1.31% | 175 / 35 |
| [`quantize`](../tests/fixtures/smoke/rnbo-mixing-shaping/quantize-q4.rnbopat) | quantize-q4 | Pass | 77 / 77 | 1.33% | 197 / 35 |
| [`quantize`](../tests/fixtures/smoke/rnbo-mixing-shaping/quantize-q8.rnbopat) | quantize-q8 | Pass | 76 / 77 | 1.31% | 196 / 34 |
| [`smoothstep`](../tests/fixtures/smoke/rnbo-mixing-shaping/smoothstep-rising.rnbopat) | smoothstep-rising | Pass | 76 / 76 | 1.31% | 179 / 34 |
| [`smoothstep`](../tests/fixtures/smoke/rnbo-mixing-shaping/smoothstep-falling.rnbopat) | smoothstep-falling | Pass | 76 / 76 | 1.31% | 174 / 34 |
| [`t60`](../tests/fixtures/smoke/rnbo-mixing-shaping/t60-decay.rnbopat) | t60-decay | Pass | 76 / 77 | 1.31% | 409 / 44 |
| [`t60time`](../tests/fixtures/smoke/rnbo-mixing-shaping/t60time-duration.rnbopat) | t60time-duration | Pass | 75 / 76 | 1.29% | 193 / 34 |
| [`trapezoid`](../tests/fixtures/smoke/rnbo-mixing-shaping/trapezoid-plateau.rnbopat) | trapezoid-plateau | Pass | 75.5 / 76 | 1.30% | 180 / 41 |
| [`trapezoid`](../tests/fixtures/smoke/rnbo-mixing-shaping/trapezoid-triangle.rnbopat) | trapezoid-triangle | Pass | 76 / 76 | 1.31% | 170 / 33 |
| [`trapezoid~`](../tests/fixtures/smoke/rnbo-mixing-shaping/trapezoid-signal-plateau.rnbopat) | trapezoid-signal-plateau | Pass | 121 / 133 | 2.08% | 163 / 32 |
| [`trapezoid~`](../tests/fixtures/smoke/rnbo-mixing-shaping/trapezoid-signal-triangle.rnbopat) | trapezoid-signal-triangle | Pass | 128.5 / 129 | 2.21% | 161 / 31 |
| [`pan`](../tests/fixtures/smoke/rnbo-mixing-shaping/pan-three-wrap.rnbopat) | pan-three-wrap | Pass | 76 / 76 | 1.31% | 199 / 39 |
| [`pan~`](../tests/fixtures/smoke/rnbo-mixing-shaping/pan-signal-three-wrap.rnbopat) | pan-signal-three-wrap | Pass | 338.5 / 387 | 5.83% | 166 / 34 |
| [`xfade`](../tests/fixtures/smoke/rnbo-mixing-shaping/xfade-three-wrap.rnbopat) | xfade-three-wrap | Pass | 77 / 77 | 1.33% | 199 / 35 |
| [`xfade~`](../tests/fixtures/smoke/rnbo-mixing-shaping/xfade-signal-three-wrap.rnbopat) | xfade-signal-three-wrap | Pass | 365.5 / 426 | 6.30% | 162 / 32 |

## Compatibility and fixture findings

The **six-point generic `interp` and `interp~` constructor forms** retain their original intended six control points. The installed primary constructor code assigns the fifth/sixth arguments to earlier point attributes and omits some intended later-point assignments. The authored inlet-driven controls set all six point inputs explicitly and remain separate. Native and hardware results are recorded independently; no captured output replaces the mathematical oracle and no tolerance is relaxed.

- `interp-spline6`: 5,120 outside-screen words, maximum error 0.45000004768371582, original limit 1.99999999e-06.
- `interp-signal-spline6`: 5,120 outside-screen words, maximum error 0.45000004768371582, original limit 1.99999999e-06.

The original native preflight also found eleven all/mostly-zero pan~/xfade~ amplitude results. Those graphs used number messages at amplitude ports documented as signal-only. The corrected fixtures supply explicit `sig~` amplitudes. **Only those eleven graph inputs change; all 63 expected streams, all limits and the other 52 compiled modules stay unchanged.** Original graphs, catalogs, reference/generator and native observations are archived. These initial differences are fixture mistakes, not eleven object failures. No original hardware attempt was made with those graphs.

## Performance and remaining scope

Complete callback time includes the compiled maths context and pilot. Signal interpolation/fades execute inside the callback; event maths and observation run in setter/routing work, timed separately across 22 actions including arming. Setter/callback numbers are not isolated opcode costs, total chip CPU or measured optimisation gains. Threshold-crossing contexts remain in the CPU review queue; optimisation is unassessed.

- `interp-signal-cosine`: median 1195µs, peak 1218µs, callback CPU 20.59%; median_budget.
- `interp-signal-cubic`: median 1204.5µs, peak 1210µs, callback CPU 20.75%; median_budget.
- `pan-signal-cos-out0`: median 3869.5µs, peak 3954µs, callback CPU 66.66%; median_budget.
- `pan-signal-cos-out1`: median 3871µs, peak 3955µs, callback CPU 66.68%; median_budget.
- `xfade-signal-cos`: median 3905µs, peak 3989µs, callback CPU 67.27%; median_budget.

All 63 images finalise and pass allocation/memory gates. The normal player, saved Main and live controls are restored; frames advance and runtime faults remain zero. No new listening/audio-capture or loaded-player deadline claim is made. Other domains, singularities/nonfinite values, inlet dynamics, constructor/options combinations, other RNBO/Gen forms and complete sample-by-sample qualification remain open. The full goal stays active.

Evidence: [machine-readable report](../evidence/rnbo-mixing-shaping-status.json), [native](../evidence/rnbo-mixing-shaping-native.json), [build ledger](../evidence/rnbo-mixing-shaping-builds.json), [initial fixture findings](../evidence/rnbo-mixing-shaping-initial-fixtures.json), [player restoration](../evidence/xiao-smoke-rnbo-mixing-shaping-player-restoration.json).
