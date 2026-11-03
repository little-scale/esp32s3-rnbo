# RNBO object optimisation matrix

The [expanded line timing checks](line-timing-modes.md) retain the five original
native gates while exposing age-dependent output and two valid-input fault
programs. `line~` is now marked partial with native evidence only. The sample
loop already uses Float32; timestamp precision, cancellation storage and tiny
durations need correctness work before another numerical adapter is admitted.
No target timing or performance improvement is inferred from these checks.

The optional [finite Float32 wrap correction](wrap-finite-target.md) is now
qualified in two reviewed FX contexts. Direct target outputs match the exact
modulo oracle, including signed zero and large finite values. The bounded
whole-chain comparison observes 0.276% extra CPU with unchanged context/arena
costs; this is a correctness repair, with no speed gain claimed.

The [independent biquad/nonlinear target models](object-oracles.md) now qualify
the original six bounded cases on the board. Their identical-artifact controls
establish accuracy and cost observations, not an optimisation gain. The
[parameter-event ordering correction](parameter-event-order.md) preserves
authored same-block order. The [optional scalar-power profile](scalar-powers.md)
now admits the exact reviewed nonlinear FX graph, alone or after the finite-wrap
correction. The composed comparison observes 24.10% less callback time across
the three original cases and 15.66% across 15 expanded cases. Changed rounding
and signed-zero differences remain explicit; this is not a general bit-identity
transformation.

The [train reciprocal compiler option](train-reciprocal-compiler.md) preserves the
original arithmetic and conditional Double floor while moving invariant
Float32 division outside the sample loop. Its 12 saved target cases observe
39.06% less whole-callback time with zero numerical Float32 difference and exact
PCM. Fresh public builds reproduce both complete measured images; phasor is
unchanged and receives no optimisation credit. The inherited warm-start duty
failure remains explicit and working status stays partial.

The separate [pink-noise Float32 output review](noise-float32-normalisation.md)
records its measured target improvement and exact-context compiler option.
The [private compensated-average review](average-neumaier.md) records improved
tested accuracy with 28.85% more callback CPU time; it remains unadmitted.
The [exact 44.1 kHz signal-delay compiler option](exact-delay44100-compiler.md)
now reproduces the complete module from the earlier private experiment. Its
saved four-case measurement preserves output with 12.70% less callback time;
the public source/type guards and exact-image binding were checked on the
computer without a new board run.

The [scalar duration-hoist compiler option](filter-duration-hoist-compiler.md)
also reproduces the complete previously measured pair with the current runtime.
It retains Double evaluation and Float32 return rounding, reusing the original
29.03% scalar callback observation. Signal inputs and other compositions reject.

See [compiler options and integrated evidence](compiler-optimisations.md) for the
current correctness fixes and opt-in transformations, and
[the next optimisation pass](optimisation-next-pass.md) for remaining coverage,
precision and whole-system qualification work. The optimisation goal remains active.

This is a matrix of reviewed forms and evidence, not a claim that a family is
fully optimised. Strict preparation remains the default. Optional profiles
change only fingerprinted methods or paired internal buffer types. A profile
can alter an upstream oscillator without changing the object being measured;
successful whole-fixture admission alone does not establish per-object coverage.

| Family | Current optional coverage | First host evidence and remaining work |
| --- | --- | --- |
| cycle~ | Cycle v2 reviewed fixed/scalar/signal forms; audio v2 additionally admits the scalar form with an active phase input | All three authored forms pass audio v2 host comparisons. Integer phase/truncation is unchanged. Independent frequency and phase-change checks remain useful. |
| saw~ | Reviewed signal-frequency polyBLEP kernel | Waveform, phase frequency, DC, harmonics and silence checks pass. The direct-input FX fixture adds varying input coverage. Target cost is a separate measurement. |
| mtof~ | Reviewed direct exponential pitch helper; float literals select expf | Exposed pitch permits a per-sample analytic check. Three initial cases pass; maximum strict/optional difference is about 5.96e-8 in the scaled output. |
| scale~ | Four reviewed constant-range kernels in the drone | Independent linear mapping checks pass. New ranges, wired limits or non-unit exponents require their own generated-form review. |
| reson~ | Reviewed modulated-centre-frequency kernel with the authored resonance | Decay/silence, stability and static transfer checks pass. More resonance values and boundary frequencies remain separate cases. |
| comb~ | Explicit cap; paired float32 rings; previous v1 drone form plus new cap40 fixed/scalar/signal forms in audio v2 | New forms pass audio v2 and combined-storage host checks with bit-identical output. Their local double duration conversion is retained after float conversion failed the existing limits. |
| allpass~ | Explicit cap, paired float32 rings and new cap40 fixed/scalar/signal forms in audio v2 | The authored gain 0.5 fixtures pass audio v2 and combined-storage host checks with bit-identical output; the original double duration conversion is retained. Other gains can change surrounding multiply/add rounding and require separate numerical checks. |
| delay~ | Reviewed ring conversion and crossfade arithmetic | Steady sample lag and strict/optional output checks pass. Ordinary delay capacity remains source-defined; it is separate from the comb/allpass millisecond cap. |
| Arithmetic | Reviewed drone expressions; audio v2 adds scalar addition and safe-division forms | DC semantic/output checks pass with bit-identical output, including the zero-divisor branch. Non-binary controls and small-divisor cases remain useful. |

The initial twelve forms across eight fixture families are in
`tests/fixtures/objects/catalog.json`. Reports under
`build/object-qualification/milestone-2/` and `remaining-2/` distinguish successful
comparisons from exact unsupported-form rejections. The first direct-input FX
run is under `build/object-qualification/fx-1/`. The later
[`float32-audio-v2` review](float32-audio-v2.md) records all twelve v2 fixtures,
combined delay-storage cases and the retained double filter conversion. These
are host results; hardware object timing and dynamic-output comparisons are
recorded separately.

## First target measurements

The first three **Main fixture** pairs passed on the connected AMOLED V2.
Each case used three alternating-order passes per variant, 512 vectors per
pass, four detached warmup vectors and the same seed. The first 32 rendered
vectors of each pass were excluded from process timing. All output samples,
including those excluded vectors, were compared. Events, input generation,
output analysis and setup are outside the process timer. I2S, UI and networking
were inactive. These are whole-fixture observations, not isolated operator costs
or real-time deadline bounds; Main fixtures include excitation oscillators.

| Fixture/case | Strict mean µs/vector | Optional mean µs/vector | Maximum output difference |
| --- | ---: | ---: | ---: |
| mtof, cached pitch | 441.05 | 140.07 | 0 |
| mtof, continuously varying pitch | 2785.62 | 387.26 | 2.98e-8 |
| mtof, fast/deep modulation | 2933.20 | 471.33 | 5.96e-8 |
| saw, default | 202.28 | 202.16 | 0 |
| saw, 10 kHz | 227.76 | 227.52 | 0 |
| reson, modulated centre | 1479.16 | 656.21 | 0 |
| reson, static centre | 858.66 | 257.71 | 0 |

The saw ELFs are byte-identical: their tiny timing difference is a control
observation, **not an optimisation benefit**. The mtof comparison covered
2,359,296 channel sample words (maximum PCM difference one LSB); saw and reson
each covered 3,145,728 words with exact float/PCM output. Every test recovered
the observed free PSRAM/internal memory and detected no running host heap or
module-local late allocation. The drone firmware was restored after every run.

[The sealed target record](../evidence/object-benchmarks-main.json) binds the
build reports, exact module/firmware identities, raw log hashes and all cases.
`host/compiler/collect_object_benchmarks.py` rejects changed logs/build reports,
missing cases, invalid timing coverage and samples outside the declared limits.
Direct-input FX fixtures remove excitation objects; their separate target
measurements below help distinguish that excitation cost.

Three **direct-input FX fixture** pairs subsequently passed on the same board,
under the same pass/warmup/exclusion settings. Their declared signals were
generated outside the process timer and cached once per case. The target log
records the actual input SHA, checked before and after each pass; a reference
output channel was checked against its input for every rendered sample. Host
and target sine-library rounding are not assumed to produce identical bytes.

| FX fixture/case | Strict mean µs/vector | Optional mean µs/vector | Maximum output difference |
| --- | ---: | ---: | ---: |
| mtof, cached pitch | 96.29 | 95.37 | 0 |
| mtof, continuously varying pitch | 2372.66 | 332.80 | 2.98e-8 |
| mtof, fast/deep modulation | 2540.10 | 348.38 | 5.96e-8 |
| saw, default | 227.67 | 227.33 | 0 |
| reson, modulated centre | 742.34 | 508.11 | 0 |
| reson, static centre | 139.74 | 138.21 | 0 |

These are complete authored FX process callbacks, including their mapping and
reference-channel expressions. They remain separate from the Main observations
and establish no universal isolated-operation cost. The saw pair again uses
identical module artifacts; its timing variation is not an optimisation gain.
The sealed [FX target record](../evidence/object-benchmarks-fx.json) retains all
twelve cases, input/generator identities, output limits and recovered-memory
observations. These target comparisons use the existing audio v1 profile;
they do not qualify execution or timing of the newly admitted v2 kernels.

## Reusable precision audit

`host/compiler/audit_precision.py` inventories generated methods, direct
`this->` reachability, ring types, recorded adaptations, potential unsuffixed
decimal promotions and uses of RNBO's integer phase-conversion macro. It can
also inspect the linked Xtensa ELF or its retained debug companion:

```sh
python3 host/compiler/audit_precision.py \
  --prepared build/user-patches/3sawsDrone3/prepared-cap40-f32audio-v1 \
  --elf build/modules/3sawsDrone3-cap40-f32audio/rnbo_s3_dynamic.app.elf.debug \
  --build-report build/modules/3sawsDrone3-cap40-f32audio/build-report.json \
  --out build/audit/precision-NEW
python3 -m unittest discover -s host/compiler -p test_audit_precision.py -v
```

Reports bind the prepared source, manifest/provenance, auditor dependencies,
ELF, reference build and GNU tool binaries/versions by hash. A debug companion
must match the reported module's mapped code/data and runtime relocations;
only the recorded zero-relocation tombstones and unmapped metadata may differ.
The audit retains disassembly locally in the ignored build tree. It commits no
generated RNBO algorithm bodies.
Inputs, helper sources, tools and reference artifacts are rechecked before the
report is written; a concurrent change fails the audit.

The resolver follows literal loads, register copies and stack spills through
a conservative control-flow join. Numeric helper calls preserve unrelated
stack facts; other calls and ambiguous writes discard them. Register-window
clobbers, overlapping stores, hardware loops, backward branches, zero-size
libgcc symbols and named ROM numeric helpers are handled. Unknown targets stay
visible. This undercounts some indirect calls; it is not a complete C++ type
analysis, call graph or proof of absence of double arithmetic.

Time conversion is context-dependent. A `MillisecondTime` argument or a name
such as `mstosamps` does not establish that double precision is needed: the
original comb calls that helper from audio processing. Generic duration
converters are marked shared/needs-review. Actual `updateTime`/`advanceTime`
caller context distinguishes block-clock work. Decimal literals are candidates,
not proof of runtime promotion; many initializers become compile-time floats.

Validated initial audits are under `build/audit/object-precision/v3/` for the
cap40 double baseline, optional float32 module and physically qualified static
drone. The strict indirect resolver finds 41 resolved audio double callsites in
the cap40 module versus 0 in the float32 module, leaving unresolved audio calls
explicitly listed. Those are static instruction locations, not invocation
counts, execution frequency, cycle cost or a complete no-doubles claim. The
float32 drone source has no remaining Float64 ring declarations; lookup tables
and scheduler definitions retain their separately recorded types.

## Next candidates

The phase macro still routes float input through `int64_t`. Six source uses
remain in the drone's five cycles. Existing active disassembly identifies six
`__fixsfdi` sites, which are integer-conversion work rather than double
arithmetic. Five frequency-increment conversions are hoisted outside their
local vector loops. The first cycle's phase-offset conversion is inside a
backward-branch loop and is conditional on a non-zero phase input. Do not rank
these as six conversions per sample. A full cycle/vector benchmark is needed.

`runtime/phase_trunc.h` is an experimental **disabled** candidate. For finite
float inputs in `[0, 2^32)`, direct unsigned conversion exactly matches the old
float-to-int64-to-unsigned result; other inputs retain the original expression.
The strict upper bound matters because float(UINT32_MAX) rounds to 2^32.
Negative zero and subnormals map to zero. The original NaN/infinity/out-of-int64
undefined domain is not newly qualified. The independent truncation/modulo
oracle checks 16,879,131 values, including every mantissa at exponent 31 and the
negative fallback counterparts. Pinned GCC 14.2 emits hardware `utrunc.s` on the
accepted path, but neither that lowering nor these tests establish a speedup.

The subsequent native-firmware conversion microbenchmark checked 798 inputs
(including repeated boundaries) and timed 1,572,864 calls per variant across
three workloads. Positive phase values improved by about 36.9% and positive
increments by 32.7%; the mixed/fallback workload was about 6.5% slower. This
candidate therefore remains **disabled**. These are indirect-function conversion
costs, not cycle-object or instrument speedups. Source, build and log hashes and
the complete measurements are in
[phase-conversion.json](../evidence/phase-conversion.json). The separate
`phase-benchmark/` application never changes generated RNBO DSP.

An isolated mtof FX fixture reserves a 65,536-float default lookup table even
when the reviewed audio helper uses direct expf: its measured arena is 262,224 B.
Table fill's double exp calls are setup work. The explicit, default-off
[`--omit-unused-mtof-table`](unused-mtof-table.md) option now admits reviewed
direct-exponential forms under the opaque module C ABI1.0 contract. It is a
memory/startup option; it does not change audio arithmetic.

A private zero-size-request experiment now preserves float output bit-for-bit
over four variants and twelve host workloads. The drone's Platform arena falls
from 361,240 to 99,088 bytes; isolated mtof FX falls from 262,224 to 72 bytes.
The probe retains DataRef indices, types and views, but resource size changes
and the absent size request suppresses its DataRefUpdated notification/event.
Current refresh handlers only touch unused views and time. Separate lifecycle
tests and an independent event trace checked the four exact reference/omitted
pairs: after filtering only the removed table events, other observed event
order, double engine/patcher times and audio bytes matched. This does not
establish generic RNBO resource/event equivalence. Admission pins the reviewed
runtime, complete callbacks and time helpers, and rejects extra aliases/readers.
The generated configuration rejects missing SDK ABI macros or versions other
than 1.0. ABI1.0 consumers must honor the opaque resource boundary; adding a
resource API requires a new ABI review/version. Local evidence is under
`build/research/mtof-table-zero/` and
`build/research/mtof-event-trace/trace-proof.json`.

The separate strict-arithmetic target FX comparison then observed zero numeric
float difference and exact PCM over 2,359,296 words with table omission alone.
Dynamic arena use fell from 262,288 to 128B, including C++ requests. Mean
create/prepare time including warmup fell from 695.420 to 0.742ms across nine
contexts per profile; loading/relocation/BIND were outside that timer. Process
totals were effectively unchanged. A separate 300-poll live drone qualification
passed with a 128KiB arena, using 99,088B and physically recovering 262,144B of
reserved PSRAM. These resource/setup observations and the silent live run's
limits are in [the omission review](unused-mtof-table.md) and
[sealed evidence](../evidence/mtof-table-omission.json). They do not extend the
opaque resource/event contract or establish an audio-processing speedup.

Further work should follow measured object costs. Float32 expf/cosf/floorf and
software float division remain valid audio operations; count or replace them
only with independent semantics, accuracy and target-cost evidence. Clock
precision and numerical stability remain requirements, not optimisation defects.

## Whole-object follow-up measurements

The disabled phase-conversion helper was also tested in a complete scalar
cycle fixture, retaining strict interpolation and audio arithmetic. Twelve
positive/negative-frequency and phase-boundary cases compared 9,437,184 finite
channel values on target with zero numerical float error and exact PCM. The
active-phase cases took about 19–24% less process time; phase zero took 2.57% more.
The helper remains disabled. These are whole-fixture observations and exclude
I2S/UI/network. See [the sealed cycle record](../evidence/cycle-phase-conversion.json).
An alternative that moves unchanged scalar conversions outside the loop is
being evaluated separately.

A scalar comb/allpass pair at a 40ms cap and gain 0.5 also passed target output
comparisons with the audio-v2 plus Float32-storage combination. All 2,359,296
compared finite channel values had zero numerical error and exact PCM. The
observed mean process reductions were 35.86% for the default impulse, 43.31% at
minimum delay and 37.20% at maximum delay. Runtime memory recovered and no late
allocation was observed. These results do not cover arbitrary allpass gains,
other input shapes or worst-case deadlines. See
[the scalar filter record](../evidence/filters-scalar-v2-storage.json).

The [second-wave coverage audit](object-coverage-wave2.md) adds independent
semantic tests for six more object groups and retains baseline precision and
seed-policy limitations as explicit failures.

Two subsequent scalar-cycle comparisons move the original conversion expressions
outside the loop, preserving the arithmetic types and rounding. Each covers
12 cases and 9,437,184 finite channel values on target with zero numerical error
and exact PCM. Against strict, active-phase process reductions are about 24–29%,
with phase zero essentially unchanged. Against the actual audio-v2 reference,
observed reductions range from 6.45% to 43.43% across the declared cases. These
are measured workload comparisons, not a universal speed bound. The distinct
reference profiles are printed by firmware and verified against the two module
manifests. See [cycle invariant evidence](../evidence/cycle-invariant-hoist.json).

The scalar filter duration-hoist experiment also passed 2,359,296 target
comparisons with zero numerical float difference and exact PCM. Total timed
callback cost fell from 7,503,863 to 5,325,609µs across 4,320 vectors (about 29.0%).
Target instruction/source mappings place both duration conversions inside
reference sample loops and outside candidate sample loops; double evaluation
is retained. Signal-rate delays are excluded. Its independent native proof
covers 32 workloads and 8,388,608 byte-identical Float32/PCM words.
[The sealed duration-hoist record](../evidence/filter-duration-hoist.json)
retains unresolved instruction targets rather than treating them as resolved
math calls. The [subsequent public option](filter-duration-hoist-compiler.md)
admits only the strict scalar context after a current-runtime refresh and exact-image binding.
