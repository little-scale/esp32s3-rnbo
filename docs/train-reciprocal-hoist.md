# Private train reciprocal hoist

The [public compiler option](train-reciprocal-compiler.md) now admits this exact
strict context and reproduces both complete measured modules. This document
records the original private experiment; its saved measurements and limitations
remain unchanged.

A private `train~` experiment caches the original Float32 reciprocal once per
256-frame vector, instead of repeating the same software division inside the
active-width sample loop. The scalar interval and width are copied by value;
the denominator, rounding and original width-bypass predicate are unchanged.
Width zero or one still performs no reciprocal. The original Double floor
expression, phase/pulse state, output order, events and clocks are retained.

The original experiment had no public preparer option. Its closed context is
the reviewed RNBO 1.4.4 phase/pulse Main graph,
44,100 Hz/256 frames, scalar period 16..2048 samples and width 0..1. It assumes
exclusive event/process ownership and no within-block floating-environment
changes. Signal-rate controls, arbitrary graphs and complete reset/sync modes
remain outside this qualification.

## Saved ESP32-S3 measurements

Before the switch to computer-only work, the 12-case comparison passed
9,437,184 finite channel-word comparisons with **zero numerical Float32
error and exact PCM**. The target harness has no independent phase/duty oracle
or raw IEEE-bit gate; native raw-bit and mathematical observations are separate.

Across all 12 workloads, callback time fell from 2,304,575 to 1,404,446 µs over
17,280 timed vectors per profile: **39.06% less processing time**. This is the
complete authored Main callback, including unchanged `phasor~`, train state and
clock work. It is not an isolated division cost or a live-player deadline bound.
The two division-free width controls remain in the aggregate; their timing
variation is not claimed as a division optimisation gain.

| Case | Strict µs/vector | Candidate µs/vector | Time saved |
| --- | ---: | ---: | ---: |
| default | 144.66 | 78.28 | 45.89% |
| negative | 144.61 | 78.25 | 45.89% |
| zero | 144.62 | 78.23 | 45.90% |
| short-period | 162.27 | 96.05 | 40.81% |
| zero-width | 65.11 | 63.77 | — (control) |
| full-width | 60.69 | 60.49 | — (control) |
| minimum-period-high-frequency | 164.48 | 98.40 | 40.17% |
| maximum-period-near-full | 145.40 | 79.48 | 45.33% |
| tiny-width-negative-zero | 161.85 | 95.92 | 40.74% |
| fractional-period-adjacent-width | 144.63 | 78.30 | 45.86% |
| warm-freeze-and-release | 130.72 | 86.57 | 33.77% |
| warm-sparse-switches | 131.36 | 81.56 | 37.91% |

All cases use four detached warmup blocks, 512 rendered blocks per pass, the
same seed and three alternating-order rounds. Timing excludes the first
32 blocks; every sample remains in the output comparison. Actual boundary
parameter events and preparation are outside the process timer, as are I2S,
display and networking. The largest event case has 165 events per pass; the
cold and every-block native schedules are not relabelled as these warm target
workloads.

Both target modules use a 14,032-byte opaque context, a 4,096-byte selected
arena and zero observed arena high-water. Aligned text decreases by 64 bytes,
from 49,224 to 49,160. Both modules have zero imports, recover the observed
internal/PSRAM totals, finalize all four loaded images and report no running
host-heap or module-local allocations. The recorded GUIv3 image and each run's
freshly saved controls were restored then; these saved results make no claim
about the user's current board firmware.

## Native/source proof and retained limitations

Fifteen native cases compare 3,932,160 words through the actual dynamic C ABI.
Reference O3, candidate O3 and candidate UBSan runs have byte-identical Float32,
PCM and parameter-readback files, including cold/warm startup, scalar boundaries,
small and signed-zero widths, freeze/release and per-block actual events. The
two new warm target schedules add 524,288 native comparison words. An independent
branch/reciprocal probe checks 4,216,576 scalar comparisons with unchanged raw
bits and observed host sticky flags; it is not a complete floating-environment
trace or trap-identity proof.

The inherited maximum-period/near-full-width case fails the old full-window
duty check: 0.98892975 versus width 0.99999994. Changing the period after warmup
retains pulse/phase state. This failure remains recorded. A separate suffix
check uses a source-derived settling bound of 4,099 samples and passes the
unchanged duty tolerance; all startup words remain in the exact pair comparison.
That supplement does not establish independent target reset/absolute-phase
correctness or erase the full-window result.

Fresh linked instruction mappings confirm that `__divsf3` moves from the
sample loop to before it. Six conditional Double/floor callsites remain.
Phasor's wrap already lowers to single-precision add/sub instructions; it is
unchanged and receives no optimisation credit from this experiment. Static
callsites are not invocation counts or measured costs by themselves.

The [sealed saved-record evidence](../evidence/train-reciprocal-hoist.json)
binds source inverses, native artifacts, compiled modules, actual logs, resource
counts and historical control restoration. The separate public admission binds
its new source/type guards and actual pipeline to this exact pair. No new device
access is required to review or reuse these saved records.
