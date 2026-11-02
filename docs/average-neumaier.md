# Private Float32 compensated average

The tested Neumaier accumulator meets the unchanged mathematical error limit,
with about **28.85% more callback CPU time** than the already compacted strict
accumulator. It remains a **PRIVATE, unadmitted numerical experiment**. Strict
preparation and the production compiler's numerical profiles are unchanged.

The [sealed evidence](../evidence/average-neumaier.json) binds the native outputs,
prepared trees, module and benchmark identities, target logs, collector results
and the reviewed qualification plan. This is a separate accuracy/cost decision
from the existing compact-history memory option.

## Arithmetic and reset scope

The original fixture has two independent `average~` objects, a `window` parameter
from 1 to 64 with default 16, stereo FX input/output and a fixed 44,100 Hz/256-frame
profile. The candidate starts from the reviewed compact variant's two 65-frame
Float32 history rings. It adds one Float32 compensation field per object,
compensates both insertion and removal from the running sum, and divides the
corrected sum by the available history count.

Compensation is initialized and reset with the accumulator. A changed truncated
window resets before the current sample; an unchanged truncated window preserves
history and compensation. History writes, indices, available count, divisor,
caller/resource paths and clocks are unchanged. Inverting only the numerical
edits restores the complete compact baseline header exactly; 36 common headers,
configuration and description remain identical. This review covers the exact
authored graph, not a general average-object transformation.

The two new fields nominally require 8 B. They consume existing padding in both
observed aligned contexts, so measured context size did not increase. This
observation is specific to these builds.

## Native accuracy and deliberate output changes

Seventeen workloads compare against a fresh `math.fsum` over every literal
Float32 input window. The oracle uses the source-defined reset/warmup policy
and fixed causal lag 0; it neither fits output lag nor uses a running sum.
Thirteen 512-block cases include window transitions, unchanged-window retrigger,
cold/warm starts and fractional-window truncation. Four further 4096-block cases
exercise cancellation at windows 1/16/63/64.

| Accumulator | Worst mathematical error | Unchanged 2e-6 limit |
| --- | ---: | --- |
| Original strict / compact strict | 7.96902e-5 | Eight cases fail |
| Float32 Kahan | 2.27615e-6 | Long cancellation/window 16 fails |
| Float32 Neumaier | 2.98023e-8 | All 17 pass |

Original and compact strict float/PCM outputs remain byte-identical in these
cases. Both compensated candidates deliberately change the original waveform:
eight cases exceed its old 2e-6 pair-comparison limit, with up to two PCM LSB of
difference. The accuracy limit was not widened, and mathematical improvement is
not presented as strict compatibility. Kahan's failure remains in the record.

A separate O2 native test of the real dynamic wrapper and bounded allocator,
with undefined-behavior/signed-overflow sanitizers, passed 16 reconstructions of
128 blocks for each variant. No late Platform/C++ allocation, bootstrap request,
invalid output or unexpected fault was observed. Arena use was 736 B within 4 KiB;
aligned native context size was 15,232 B. Native lifecycle stubs do not establish
ELF mapping, constructor or unload behavior.

## AMOLED V2 target observations

Two real ELF benchmark runs used 512 blocks per case, three alternating-order
passes, four detached zero-input warmup blocks and seed 0x12345678. The first 32
blocks of every pass were excluded from process timing; every rendered sample
still participated in output/model checks. Input/oracle generation, cache copy,
events and preparation were outside that timer. I2S, UI and networking were
inactive.

The cost experiment compares compact strict against Neumaier only on four
dyadic impulse/step cases at windows 1/16/63/64, where both satisfy the oracle:

| Profile | Total process time / 5760 timed vectors | Mean µs/vector |
| --- | ---: | ---: |
| Compact strict | 1,826,329µs | 317.071 |
| Neumaier | 2,353,150µs | 408.533 |

This is 28.85% more callback time for the candidate, not a speedup. All 3,145,728
compared channel sample words had zero numerical float difference and exact
PCM in these dyadic cases; 6,291,456 independent model checks passed.

The accuracy experiment loads the **same Neumaier ELF on both sides**, with
four dyadic and four cancellation cases at the same windows. This prevents the
known strict cancellation error from aborting before the candidate is tested.
Its 6,291,456 pair comparisons showed zero numerical float difference and exact
PCM; 12,582,912 independent model checks passed. Maximum conservative error was 4.42766e-8, including oracle-cache rounding,
below the unchanged 2e-6 limit. Identical-artifact timings are a control and do
not establish an optimisation benefit.

Both runs observed 12,912 B context and 672 B arena use within a 4 KiB reservation.
Loaded text span grew from 39,612 B to 40,736 B; the module ELF grew from
46,980 B to 47,768 B.
Observed free PSRAM/internal memory recovered, four images were finalized per
run, and running host heap/module-local late-allocation counters stayed zero.
The instrument firmware, parameter readbacks, Panic state and volume were
restored after each test; oscillator instance phase was not restored.

Target compilation used matched Xtensa GCC 14.2.0/O2 flags, no fast math and no
floating-point contraction. The two compensated kernels contain single-precision
FPU arithmetic and one `__divsf3` call each. That Float32 helper is hardware
assisted through `div0.s` and refinement; its name does not imply integer-only
software division. Existing Float64 clock/event work remains. The separate
[bounded Float32 corner observation](float32-corners.md) does not establish
universal floating-environment equivalence.

## Admission remains open

The candidate label is `PRIVATE-float32-average-neumaier-v0`. A private build
adapter admitted only this exact reference label in memory, preserving honest
manifests and printed profiles. Production profile admission was not extended.
The public collector verified those bound labels and unchanged model gates.

The immutable target plan is SHA256
`2ef8d6a25e95f3214917ecfa09eb77ad5f033083ebc560a40167d30ad1c8e92f`.
Three compiler tool files changed after these successful builds as another
option was integrated. Their original hashes remain recorded; 48 other input
files were archived. The evidence does not relabel these binaries as products
of the later compiler revision.

Target accuracy covers frozen integer windows and 512-block cases. Native long,
transition, retrigger, cold and fractional-window checks do not qualify those
modes on target. Wider inputs, longer runs, other graphs and a justified
accuracy-versus-cost policy remain before a production option. Neither these
offline timings nor observed peaks establish a complete instrument deadline.
