# Optional Float32 scalar powers

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

`--numerical-profile float32-scalar-powers-v1` now admits the exact reviewed
RNBO 1.4.4 `nonlinear-domains` FX graph. Strict preparation remains the default.
The profile selects multiplication for scalar exponents 2 and 4, and nested
Float32 square roots for 0.25, once per 256-frame vector. Every output retains
`fixnan`; every other exponent retains the original `powf` calculation.

The only admitted composition is `--correct-finite-wrap`, applied first. Full
source, description, method and runtime hashes reject unknown graphs, partial
adaptations and repeated application. A compile contract rejects Float64 RNBO
sample types. Signal-rate exponents and arbitrary `pow~` graphs are not admitted.

```sh
node host/export/export.mjs tests/fixtures/objects/wave2/nonlinear-domains.rnbopat \
  --out build/exports/nonlinear-powers-NEW
python3 host/compiler/prepare.py \
  --export build/exports/nonlinear-powers-NEW \
  --class-name rnbos3patch --role fx \
  --numerical-profile float32-scalar-powers-v1 --correct-finite-wrap \
  --out build/prepared/nonlinear-powers-NEW
```

## Measured processing cost

Both sides of the fresh board comparison already use the same finite-wrap
correction. Only the power method changes. Across the three original cases,
whole-callback time falls from 2,726,532 to 2,069,362 µs over 4,320 timed vectors
per profile: **24.10% less processing time**.

| Original input grid | Reference µs/vector | Optional µs/vector | Time saved |
| --- | ---: | ---: | ---: |
| Square | 543.94 | 429.70 | 21.00% |
| Quarter power | 671.79 | 573.36 | 14.65% |
| Fourth power | 677.69 | 433.99 | 35.96% |

These are complete nonlinear FX callbacks, including unchanged `tanh~`,
`wrap~` and `clip~`, with input generation, cache checks, events, preparation,
I2S, display and networking outside the timer. They are neither isolated power
costs nor full-player deadline bounds. Three alternating-order rounds use
512 blocks per case, four zero-input warmup blocks and the same seed; timing
excludes the first 32 blocks, while output comparisons include every sample.

A separate 15-case run adds dense binary32 inputs, fallback exponents, adjacent
Float32 exponents and two block-boundary switching schedules. Aggregate
callback time falls from 19,621,786 to 16,549,656 µs over 21,600 timed vectors:
**15.66% less processing time**. This broader aggregate includes unchanged
fallback workloads. Their small timing variations do not establish a fallback
algorithm improvement; all raw case timings remain in the evidence.

## Output and resources

The original three cases compare 2,359,296 channel words with zero numerical
float difference and exact PCM. The expanded run compares 11,796,480 words:
maximum absolute difference `1.1920929e-7`, maximum PCM difference one LSB.
All 23,592,960 independent expanded-run model checks pass the existing `2e-6`
limit, including oracle-cache rounding; maximum conservative bound is
`1.4901161149438735e-7`. Pair limits remain `2e-6`, one PCM LSB and `1e-4`
relative RMS. The original three-case exact-output gates remain zero.

The expanded target run deliberately records 301,470 changed Float32 words,
including 930 signed-zero differences. Quarter power can preserve `-0` where
`powf` returns `+0`. Neighbouring and other fallback exponents compare exactly
in their fixed cases. Native full-module tests separately cover all 15 cases,
actual event readbacks and sanitizer builds; host and target libm outputs are
not assumed byte-identical. No general bit, nonfinite or floating-exception
identity is claimed. Raw graph inputs remain finite left `[-4,4]`, right
`[-3,3]`; the authored clipped power bases lie in `[0,1]`.

On target, both modules use a 14,800-byte opaque context, a 4,096-byte selected
arena and zero observed arena high-water. The composed module is 436 ELF bytes
larger; loaded text grows by 424 bytes. Both have zero imports. Linked `tanhf`,
`sqrtf` and `powf` closures contain no resolved Float64 helper calls; Double
parameter, event and clock work, plus unresolved clock dispatches, remain
explicit. This is not a global no-doubles claim.

Both runs recover the measured internal/PSRAM baselines, finalize all four
loaded images, and observe no running host-heap or module-local allocation.
The current wide-bar GUI and each run's freshly saved eight parameter values,
volume and Pause state are restored. Playback phase/history is not restored.

The [sealed admission evidence](../evidence/power-admission-v1.json) binds all
source, native, compiled and physical results. The earlier
[private prototype record](nonlinear-powers.md) remains historical evidence:
the public solo module matches its tested ELF exactly, while the new composed
module has its own measurements above.
