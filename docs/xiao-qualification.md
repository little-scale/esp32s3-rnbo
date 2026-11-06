# XIAO object qualification

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

The [signal-analysis and sample-clock batch](rnbo-analysis-timing.md) adds
**23 completed XIAO scenarios across 16 exact spellings**: **19 pass** and four
retain report/clock timing-policy differences, also present in native preflight.
Checks cover **235,520 output words and 506 control actions**, with exact raw
right captures, five within-limit differences and no nonfinite/zero-sign errors.
Manual peak/snapshot, threshold boundaries, zero crossings, event mean/absolute/
RMS averages, samplecount, event sample time and elapsed/reset cases pass.
The avg observer's deferred report, block-valued currentsampletime~ and host-time
origins remain explicit gaps against the original sample-position screen;
these are not four established DSP defects. Callbacks measure **75–145µs median**
(1.29–2.50%), peak 150µs, with no new CPU flag; the review queue stays **164**.
The three seven-value event averages each use **352,880 arena bytes** under an
explicit 1 MiB ceiling, a memory optimisation candidate. All images finalise and
allocation/memory gates pass; normal player and saved controls are restored.
RNBO coverage reaches **1072/1455 scoped outcomes**, including partials; Gen
remains separate and complete qualification stays active. No optimisation gain
is claimed.

The [visual Gen range/state batch](gen-visual-flow.md) covers **42 scenarios
across 33 exact visual spellings**. **39 hardware checks pass**, fractional
`ftom` retains **640 outside-screen words** (maximum 0.25 notes), and `mod`/`%`
retain native/target C++ undefined-helper failures. **40 completed XIAO runs
check 409,600 output words**, including per-sample state across 20 continuous
blocks and separately selected counter/coordinate outlets. There are 16,907
within-limit differences, 1,300 observational left zero-sign differences, exact
raw right captures and no nonfinite output. All completed images finalise and
memory/allocation gates pass. `mtof` uses 262,208 bytes in an explicit 1 MiB arena;
its native 4 KiB abort remains separate. **Two callbacks** join CPU review, now
**164**: dbtoa at 7,359µs median (**126.77%**, above the block budget), and t60
at 2,812µs (**48.44%**). All 122 earlier visual lowerings stay unchanged and retain
their own immutable snapshots. The normal player and saved controls are restored.
This adds no RNBO inventory rows: coverage stays **1056/1455 scoped outcomes**.
Other Gen/RNBO forms, coupled outlets, resources, resets and complete
qualification remain active work; no optimisation gain is claimed.

The [maths/interpolation/mixing batch](rnbo-mixing-shaping.md) adds **22 exact
spellings across 63 completed XIAO scenarios**. **61 pass**, while the generic
six-point `interp` and `interp~` constructor forms retain **10,240 outside-screen
words**, maximum error 0.4500000477, against unchanged 2e-6 limits. Their separate
inlet-driven controls pass. Checks cover **645,120 output words and 1,386 control
actions**, with 54,800 within-limit differences, no nonfinite/zero-sign errors and
exact raw right captures. Eleven initial native-only fixture amplitude omissions
are corrected using explicit signals; all 63 expected streams/limits and 52 other
modules stay unchanged. **Five callback contexts** join CPU review, now **162**:
signal cosine/cubic interpolation and three signal cosine pan/crossfade contexts.
The slowest is cosine xfade~ at 3,905µs median (**67.27%**), peak 3,989µs. All images
finalise and memory/allocation gates pass. The normal player and saved controls
are restored. RNBO coverage reaches **1056/1455 scoped outcomes**, including
partials; Gen remains separate and the complete qualification goal stays active.

The [extended list/storage batch](rnbo-list-extended.md) adds **17 exact
spellings across 32 scenarios**. **27 complete output checks pass**, one
`list.union` screen retains **1,536 policy differences**, and four original
queue/stack growth cases fault at the eighth drive with late allocations.
All four separately authored bounded FIFO/LIFO controls pass. The completed
checks cover **286,720 output words and 616 actions**, with exact raw right
captures, no nonfinite outputs and no zero-sign differences. All original 28
sources, expected streams and zero limits are unchanged; added controls do not
replace the growth faults. Held callbacks measure **75–76µs median**, peak 81µs;
setter costs remain separate. No new CPU flag triggers; the queue stays **157**.
Completed images finalise and memory/allocation gates pass; aborted probes make
no completed output/finalisation claim. Normal player and saved controls are
restored. The RNBO table reaches **1034/1455 scoped outcomes**, including
partials; Gen remains separate and the complete qualification goal stays active.

The [numeric/list routing batch](rnbo-event-routing.md) adds **30 exact
spellings across 62 source scenarios**. **58 complete XIAO output checks pass
exactly**, covering **593,920 output words and 1,276 control actions**. Positive
`list.rot 1` is separately confirmed to fault in its first target drive event;
three longer literal-message forms retain target C++ array-bounds failures.
Those gaps remain explicit, while all completed cases have zero word/sign/
nonfinite errors and exact raw right captures. Two initial no-match comparisons
were fixture omissions; documented no-match outlets are now observed explicitly,
with all 62 expected streams and zero-error limits unchanged. Held-output
callbacks measure 75–77µs median, peak 82µs; setter costs are separate and no new
callback flag triggers, leaving **157 queued contexts**. All 58 completed images
finalise and allocation/memory gates pass; the fault probe makes no such claim.
Normal player and saved controls are restored. The RNBO table reaches
**1017/1455 scoped outcomes**, including partials; Gen stays separate and the full
qualification goal remains active.

The [ordered event-state batch](rnbo-event-state.md) passes **36 hardware
scenarios across 15 exact spellings**, checking **368,640 output words and 792
control actions**. Prefix sums/products, neutral resets, latches, changed-event
observers, bounded counters/reset inputs, peak/trough outlets, event smoothing,
sample-and-hold edges and trigger ordering pass their fixed references. There
are 3,584 within-limit differences and 768 observational left zero-sign
differences; no outside-limit, nonfinite or raw-right errors occur. An explicit
arm isolates startup parameter notifications; the original native-only fixture
attempt is archived and all expected streams/limits stay unchanged. Held-output
callbacks measure 75–77µs median (1.29–1.33%), peak 81µs. Setter work is recorded
separately; no new CPU flag triggers and the queue stays **157**. All images
finalise and allocation/memory gates pass; normal player and controls are
restored. RNBO coverage reaches **987/1455 scoped outcomes**. Other modes,
resources, RNBO/Gen objects and single-sample qualification keep the full goal
active; no optimisation gain is claimed.

The [event/signal unit-conversion batch](rnbo-unit-conversions.md) executes
**36 exact spellings: 35 pass** their rational output screens and `beatstosamps~`
retains **128 rounding differences**, maximum **0.015625 samples**, against its
unchanged zero-tolerance screen. The native preflight retains the same finding.
Across **368,640 output-word checks and 756 ordered parameter actions**, every
raw right capture matches and no nonfinite output occurs. Signal inputs vary
inside each block; transport remains at the default 120 BPM/480 PPQ. One new
CPU context, `mstobeats~` at **1,111.5µs median (19.15%)**, brings the review queue
to **157**. All images finalise and allocation/memory gates pass. The normal
player and saved controls are restored. The RNBO dashboard now contains
**972/1455 scoped outcomes**, including partial results; complete RNBO/Gen
qualification remains active and no optimisation gain is claimed.

The [visual Gen maths/constant batch](gen-visual-math.md) runs **101 exact
spellings**: **99 pass and two intentional approximations retain outside-screen
numerical differences**, across **1,034,240 output-word checks**. Every raw
right-lane capture matches; there are no nonfinite outputs. Five logarithm/
exponential callback contexts join the CPU queue, now **156**; exp2 is highest
at 3,777µs median (**65.06%** of the block period). All 101 images finalise and
runtime allocation/memory checks pass. Historical core evidence resolves its
immutable lowerer snapshot, with all 21 old lowerings unchanged. The normal
player and original controls are restored. The RNBO table remains **936/1455
scoped entries**; the 101 visual spellings have a separate operator report.
Remaining RNBO/Gen operators, structures, modes and resources keep the full
goal active. No optimisation gain is claimed.

The [embedded visual Gen core](gen-visual-core.md) now imports actual
`genpatcher.patcher` graphs and passes **21 XIAO scenarios / 215,040 output-word
checks**, including single-sample histories, coupled feedback and state rotation.
There are 5,422 within-limit differences (maximum 1.192e-7) and no outside-limit
or nonfinite outputs. Complete callbacks measure 40–100µs median (0.69–1.72% CPU),
peak 104µs; no CPU flag triggers and the queue stays 151. All images finalise and
memory/allocation checks pass. Original sources, compiler lowering, references
and target artifacts are bound separately. The normal player and original
controls are restored. The dashboard adds only `gen~`, reaching **936/1455 scoped
RNBO entries**. Remaining visual operators/forms, resources, params/reset,
codeboxes and external files remain active work; full qualification is incomplete.

The [event-rate maths batch](rnbo-event-math.md) compiles and runs **44 exact
source forms**: **41 pass and three intentional approximations retain
outside-screen numerical differences**, across **450,560 output-word checks**
and 924 parameter actions. Independent raw right-lane hashes match throughout.
Complete callbacks take 75–77µs median (1.29–1.33% of the block period); actual
setter/routing timings are separate, led by dbtoa at 777µs across 21 actions and
112µs peak. No callback CPU flag triggers; the queue remains 151. All images
finalise and memory/allocation gates pass after settling the observer's measured
288-byte first-use checksum cost. Initial setup and failed-gate attempts remain
separate; no numerical or memory limit was relaxed. The normal player and saved
controls are restored. RNBO coverage is **935/1455 scoped entries**, including
partial/rejected outcomes; the full goal remains active and Gen stays separate.

The [event-comparison/range/state batch](hardware-smoke.md#rnbo-event-comparisons-ranges-and-event-delta)
adds **22 passing XIAO scenarios**, **225,280 output-word checks** and 462 actual
parameter actions, including ordered previous-event delta state. All numerical
outputs and raw right-channel words agree; 512 left signed-zero differences
remain diagnostic. Complete callbacks take 75–76µs median (**1.29–1.31% CPU**),
with event setter/routing timing separate and **no new CPU flags**. The queue
remains 151. All images finalise and allocation/memory checks pass. The normal
player and saved controls are restored. RNBO coverage is **891/1455 scoped
entries**, including earlier mismatches/rejections, not 891 full qualifications;
Gen remains separate and the complete goal remains active.

The [global list-function batch](hardware-smoke.md#rnbo-list-function-call-forms)
adds ten device runs: nine passes and one duplicate-policy mismatch, with
102,400 output checks. Seven C++ rejections, sixteen frontend rejections and
one native-preflight rotation fault remain separately recorded. The faulting
native case is not flashed. Two passing callbacks join the CPU queue, now 101;
the RNBO table maps 727 exact entries with scoped outcomes. The quiet global
list-function test application is currently installed, and qualification remains active.

The next [Gen control and language batch](hardware-smoke.md#gen-control-declarations-and-language-structures)
passes **19 programs and 194,560 numeric checks**, with 33,360 signed-zero word differences
saved separately. It checks predicate pass-through aliases, defaults, elapsed
sample counting, independent function-local histories and bounded loops.
Five C++ forms and two frontend forms reject; no new CPU flag triggers.
The complete RNBO/Gen/structure goal remains active, and the quiet Gen test
application is now installed. Gen cases do not inflate the RNBO table count.

Qualification resumed on 5 November after the physical-input/MIDI tangents.
The [codebox list/array batch](hardware-smoke.md#rnbo-codebox-lists-and-fixed-arrays)
adds **26 passing device scenarios and 266,240 exact output checks**, including
all seventeen fixed-array constructor spellings and nine list methods. Two
length-return source forms fail compilation; five whole callback costs are
queued for review, bringing the backlog to 99. The dashboard maps 693 exact
entries with scoped outcomes, not full qualification. The XIAO is currently
quiet with the completed smoke test application installed. External MIDI tests
remain deferred; broader RNBO, Gen and structure coverage remains active work.

## Fast coverage runs

The [direct Gen partition probe](gen-direct-partitions.md) now passes **78
XIAO renders** of three exact history programs and two stimuli. It checks
**638,976 numerical output words** and **589,824 bit-exact partition comparisons**
across 1-, 2-, 7-, 255-, 256-frame and mixed calls, clipped at fixed reset/prepare
samples. All 78 native/device capture hashes agree. This qualifies a separate
variable-frame generated-producer route; the player/module ABI stays fixed at
256 frames. Processing and observed reset/prepare calls allocate/free no heap.
PSRAM returns to baseline; an unexplained **288-byte internal heap decrease**
remains a lifecycle/first-use follow-up. Eight small-call CPU contexts bring the
queue to **151**, including expected per-call dispatch cost. The normal player
and saved controls are restored. RNBO coverage remains **869 scoped entries**;
other Gen operators/forms, resources/modes/events and visual Gen remain, so the
full goal is still active. No variable-frame production API is claimed.

The [Gen routing/causal-state batch](hardware-smoke.md#gen-routing-calls-and-causal-state-structures)
records **26 source forms: 15 execute and all 15 pass, ten fail C++ compilation
and one fails the frontend**, with **153,600 output-word checks**. Three-stage
histories, fanout, coupled feedback, read/write ordering, three-state rotations,
conditional histories and loop/function feedback pass their independent
references. The rejected final-if form is retained alongside separately passing
following-statement and ternary forms. Loop feedback adds one CPU review context
at 742.5µs median (12.79% of the block period), taking the queue to **143**.
All loaded images finalise and memory/allocation checks pass; the normal player
and saved controls are restored. RNBO coverage stays **869 scoped entries**.
The new [Gen source-route ledger](gen-registry-routes.md) records authored
scenarios for **212/212 registry entries**, which is **not 212 hardware passes**
or complete Gen qualification. Visual Gen, external/resource/mode/event and
one-frame target-call work remains; the full goal stays active.

The [phase/ramp/transition/pitch member batch](hardware-smoke.md#rnbo-codebox-phase-ramps-transitions-and-pitch-members)
compiles and executes **all 36 sources: 28 pass and eight retain comparison
mismatches**, across **368,640 output-word checks**. Positive phase wraps, the
input-reset source, falling-edge latency and bline trajectories retain their
original differences; secondary native sample witnesses explain observations
without replacing references. Six complete callback CPU contexts bring the
queue to **142**, led by mtof reset at 2.757 ms median (47.49% of the block
period). The dashboard maps **869 exact RNBO entries with scoped outcomes**.
All 36 images finalise and allocation/memory gates pass. The normal player,
saved Main and live controls are restored; USB/audio progress and zero runtime
faults are checked. The complete RNBO/Gen qualification goal remains active.

The [context/unit/alias batch](hardware-smoke.md#rnbo-codebox-context-units-and-exact-aliases)
records **51 sources: 43 execute, 40 pass, three retain clock comparison
mismatches and eight remain frontend rejections**, across **440,320 output-word
checks**. A secondary native diagnosis is consistent with callback-held clock
queries; it does not replace the original per-sample expectations. Thirteen
conversion CPU contexts bring the queue to **136**, led by mstobeats at 2.104 ms
median (36.25% of the block period). The dashboard now maps **837 exact RNBO
entries with scoped outcomes**, including gaps and unverified forms. Auxiliary
lexical state syntax is separate from rejected constructor aliases. All loaded
images finalise and allocation/memory checks pass. The normal player and saved
controls are restored, with USB frame progress and zero runtime faults checked.
An initial harness-limit stop is retained separately from the identical-plan
successful rerun. The complete RNBO/Gen qualification goal remains active.

The latest [signal-stateful and miscellaneous codebox checks](hardware-smoke.md#rnbo-signal-state-across-callback-boundaries)
execute 37 scenarios: 36 pass, while `downsamp~` differs from the declared first-
capture phase policy. They check 378,880 values and add five passing CPU-review
contexts, bringing the queue to 92. Memory/allocation gates pass. Native evidence
for `delta~`, `sah~` and `slide~` remains; `slide~` keeps its partial status despite
this short XIAO pass because its broader native failure is retained. Twelve new
signal owners and 22 codebox owners bring the main table to 556 mapped entries
out of 1,455, with no Gen additions. The original qualifications, optimisation
records and 154 timing measurements remain intact.

The earlier [direct signal and codebox filter checks](hardware-smoke.md#rnbo-codebox-filters-and-default-delay-resources)
execute 49 scenarios: 46 pass and three retain signal comparison mismatches,
checking 501,760 output values. All twelve filter/delay streams pass their full
twenty-block references. Eleven passing contexts add CPU flags, bringing the
queue to 87. All images finalise and memory/allocation gates pass. Default
Float64 resources remain intact; an explicit 2 MiB smoke-only arena tier fits
the original comb/allpass rings, while ordinary benchmark hosts keep their
1 MiB default. Capacity and measured use are separately reported. Those batches brought the main
table to 522 exact entries out of 1,455; no Gen rows are added.

The [direct signal range/window batch](hardware-smoke.md#rnbo-signal-ranges-routes-windows-and-constants)
executes 37 scenarios and checks 378,880 values: 34 pass, `step~` retains its
ordering mismatch, and two fast approximations exceed their predeclared quality
screens. Six passing contexts trigger CPU review; `blackman~` has a 7.763 ms
median against the 5.805 ms block period. Memory/allocation gates pass. These
signal observations remain separate from matching codebox and Gen results.

The earlier [codebox shaping and stateful checks](hardware-smoke.md#rnbo-codebox-continuous-state-instances)
execute 51 scenarios: 48 pass and three retain mismatches, checking 522,240 output
values. Two bounce curves retain their fixed-limit exceedances; `downsamp`
differs from its declared capture-phase reference. The history class source
fails C++ compilation, while a separate port-invalid autonomous-counter fixture
does not invalidate the passing input-driven counter form. All eleven executed
stateful cases retain full twenty-block continuous references. Eighteen passing
shaping contexts add CPU flags, bringing the queue to 76. Memory/allocation gates
pass. Those batches brought the main table to 473 exact entries out of 1,455, preserving previous
records and adding no Gen rows.

The [RNBO codebox shaping batch](hardware-smoke.md#rnbo-codebox-shaping-windows-and-integer-helpers)
executes 40 scalar forms and checks 409,600 values: 38 pass, while two bounce
curves exceed their unchanged 2e-6 reference limit by a small amount. Eighteen
passing contexts trigger CPU review, bringing the queue to 76 before the
separate stateful batch. Blackman and three elastic fixture medians exceed the
block period. Memory/allocation gates pass; no optimisation has been applied.

The earlier [codebox range and Gen constant batches](hardware-smoke.md#rnbo-codebox-range-routing-and-conversion-forms)
execute 72 scenarios: 68 pass and four retain comparison mismatches, checking
737,280 output values. Seven codebox source attempts are rejected before
execution; separate valid `mtof`/`ftom` state-instance forms both pass. Six new
CPU flags bring the queue to 58 contexts. All executed images finalise and
memory/allocation gates pass. These add 45 exact RNBO codebox entries, bringing
the main table to 421 mapped entries out of 1,455; Gen adds no main-table rows.

The [Gen named-constant batch](hardware-smoke.md#gen-named-constants-and-configuration-values)
passes all 32 bare-value scenarios and 327,680 bit-exact output checks. It covers
28 mathematical spellings plus sample-rate/vector-size names at 44,100 Hz/256
frames, with 37 µs medians, peak 42 µs and no CPU-review flags. These separate
Gen results do not add RNBO main-table mappings.

The earlier RNBO codebox numeric and [Gen range checks](hardware-smoke.md#gen-range-routing-and-conversion-calls)
execute 72 scenarios: 65 pass and seven retain comparison mismatches, checking
737,280 output values. One additional Gen `gate` syntax form is rejected before
execution. Twenty new CPU flags bring the separate review queue to 52 contexts.
Gen's three fast-function exceedances are approximation-quality screens, not
universal malfunction findings; `ftom` retains its continuous-pitch mismatch.
All executed images finalise and memory/allocation gates pass. Gen adds no RNBO
main-table entries; the 43 new RNBO codebox entries bring that table to 376
mapped exact spellings out of 1,455.

The [RNBO codebox numeric batch](hardware-smoke.md#rnbo-codebox-numeric-and-mathematical-calls)
adds 43 executed calls and 440,320 output checks: 40 pass and three retain round/
denormal mismatches. Fourteen callback costs are queued for CPU review;
`exp2()` has a 7.499 ms median against the 5.805 ms block period. No optimisation
is applied or saving claimed. These 43 exact codebox entries are separate from
matching patcher and Gen names.

The [RNBO codebox batches](hardware-smoke.md#rnbo-codebox-arithmetic-and-named-constants)
add 83 passing device scenarios and 849,920 output checks: 43 arithmetic/logic
forms and 40 named-value constants. The constants are bit-exact; arithmetic
retains 2,880 allowed operation zero-sign differences. Named `mod(a,b)` and
`^^` infix remain unverified after compilation/frontend rejection respectively,
with no device execution. No CPU-review flags trigger. These add 85 mapped
codebox entries; older patcher, Gen and measured optimisation records are preserved.

Two additional [event/constant batches](hardware-smoke.md#additional-events-and-signal-constants)
execute 61 scenarios: 56 pass, with five retained event mismatches (`isdenorm`,
`fixdenorm`, `rmod`, `!%`, `step`). They add 624,640 output checks and 840 parameter
updates/readbacks, with no CPU-review flags. All 21 constant scenarios are
bit-exact. The main table gains 60 mapped exact spellings; existing `sig~`
composition status is preserved with its separate initial-value evidence.
These short observations do not qualify every mode or within-block scheduling.

The current priority is short hardware functionality checks with CPU timing,
batching many objects into one upload and leaving the test firmware installed
between batches. The [parameter-driven event batch](hardware-smoke.md#rnbo-parameter-driven-event-batch)
passes all 35 exact event spellings,735 updates/readbacks and 358,400 output checks.
It verifies supplied boundary ordering and a raw-bit audio observer, with no new
CPU flags. The [function/conversion batch](hardware-smoke.md#rnbo-functions-and-conversions-batch)
executes 35 RNBO forms: 34 pass their declared limits, `fasttan~` exceeds the
selected approximation threshold, and eleven CPU costs are queued. The default
`mtof~` shared lookup is preserved and peaks at 262,416 arena bytes.
The [earlier numeric batch](hardware-smoke.md#rnbo-numeric-and-maths-batch)
checks 33 RNBO signal forms: 30 pass, three have output mismatches, and eight
trigger CPU review. The previous arithmetic/logic batch checks 36 spellings:
all pass. The earlier numeric Gen batch
records 15 device scenarios (10 pass, 5 output mismatches) and one compilation
rejection.
[CPU outliers are queued](cpu-review-backlog.md) for future optimisation.
The subsequent [Gen mathematical batch](hardware-smoke.md#gen-mathematical-batch)
adds 27 device passes within declared limits, four C++ compilation failures and
three parser rejections, with thirteen CPU-review flags. RNBO and Gen outcomes
remain separate. The [new stateful Gen batch](hardware-smoke.md#gen-stateful-and-per-sample-batch)
passes twelve programs/nine exact names, checking 122,880 values with continuous
state across all twenty callbacks. No additional CPU-review flags trigger.
These smoke checks are distinct from the deeper historical
tests below.

The active goal is to test every inventoried RNBO object, operation and structure
on the XIAO ESP32-S3 and record compatibility, resource use and performance.
The user has also explicitly included Gen/`gen~` operators and single-sample
processing; see the [full qualification scope](qualification-scope.md). Gen
hardware qualification is separate: the first three history programs now pass,
and fifteen [GenExpr arithmetic spellings](gen-arithmetic-qualification.md) have
their own output/timing/memory checks. Twenty additional
[comparison/logic forms](gen-logic-qualification.md) pass; `step` has a retained
documented-order mismatch. The broader operator inventory remains pending.
The first hardware batch passed on 4 November 2026. The drone was restored,
unpaused at 50%, with all eight compiled parameter defaults after each run.
A final 4,096-frame internal stereo capture contained nonzero output.

The [complete pending-work snapshot](../evidence/xiao-qualification-plan.json)
maps all 1,455 dashboard entries: 1,209 installed exact spellings, 238 codebox
members/types/hooks, one reference-only name and seven host/editor entries.
It also identifies 22 structure-testing axes. Five host/editor entries are
not applicable to device DSP. Each alias and codebox surface needs its own
execution evidence; whole-drone presence does not qualify an individual object.

## First hardware results

| Authored fixture | Output comparison | Mean callback time per 256 frames | Processing time saved |
| --- | --- | --- | --- |
| `cycle-scalar`, four frequency/phase cases | 3,145,728 samples; zero Float32 and PCM differences | 472.68 / 472.98 µs | Not applicable: identical-module control |
| `filters-scalar`, impulse and 0–40 ms delay cases | 2,359,296 samples; zero Float32 and PCM differences | 1,736.12 / 1,232.09 µs | 29.03% |
| `biquad-response`, three stereo FX cases | 2,359,296 pair comparisons; 4,718,592 independent-model checks | 84.43 / 84.42 µs | Not applicable: identical-module control |

The filter comparison changes duration-conversion hoisting only. Both modules
retain Float64 delay storage and the same strict numerical profile. This is a
matched measurement of the complete comb/allpass test graph, including its
excitation code. It is not a separate cost for either filter, or an improvement
measurement for the live drone. The oscillator control measures repeatability;
its timing difference is not an optimisation gain.

The first two Main runs each loaded and finalised four module images, recovered internal RAM and
PSRAM to the recorded baselines, and reported no callback heap operations or
late module allocations. These are dynamic Main-module observations on XIAO.
Other FX forms, MIDI, live replacement and other object/mode combinations need
separate qualification.

These first Main tests compare complete on-device reference/candidate outputs
and check finite values, PCM differences, lifecycle and resources. They do
**not** run an independent waveform model on the board: both logs explicitly
record zero semantic-oracle checks. Existing native mathematical tests remain
separate evidence. The subsequent biquad FX batch below adds independent target output truth.
Further batches cover arithmetic/comparison spellings, codebox state and
language structures. A matching pair alone cannot establish that both outputs
are mathematically correct.

## Independent biquad FX check

The next hardware batch exercises `biquad~` with disjoint stereo input planes
and default, identity and slow-pole coefficient cases. A fresh Float64 difference
equation generates a separately cached Float32 expected output. Both module
passes are checked against this model, including the cache-rounding error bound.
All 4,718,592 semantic sample checks and 18 settled-level checks pass the declared
3e-6 tolerance. The largest observed conservative model-error bound is
1.416e-7. Reference/candidate output comparisons also have zero numerical and
PCM differences.

The two passes use the same module, so their approximately 84.43 µs callback
time is an absolute fixture measurement, with no optimisation gain claimed.
Four images are finalised, internal RAM/PSRAM return to baseline, and callback
heap/late allocation counters stay zero. The drone is restored at 50%.
This qualifies the declared strict two-channel FX form and three coefficient
cases. Other coefficients, overloads, modes, reset paths and related exact
spellings remain separate pending work. See [the complete model and raw target
observations](../evidence/xiao-biquad-control.json).

## Arithmetic and RNBO codebox results

All 13 [original wave4 fixtures](../tests/fixtures/objects/wave4/README.md)
passed on XIAO: 39 case programs, 3,833,856 exact pair comparisons and
7,667,712 independent model checks. Numerical, PCM and raw-word differences
were all zero. The stateful delta program also passed 294,912 exact raw-bit
checks on its unchanged right-channel observer. Its previous-input state
continues across vector boundaries and is reconstructed fresh per pass.

| Exact authored form | Mean callback µs, reference slot |
| --- | ---: |
| `abs~` | 68.37 |
| `minimum~` | 53.52 |
| `min~` | 53.57 |
| `maximum~` | 53.41 |
| `max~` | 53.41 |
| `sub~` | 55.58 |
| `-~` | 55.55 |
| `eq~` | 55.62 |
| `==~` | 55.57 |
| `lt~` | 55.64 |
| `<~` | 55.61 |
| RNBO codebox `+`, `-` | 45.72 |
| RNBO codebox `delta`, `delta.next` | 46.86 |

These are strict identical-module controls; no optimisation gain is claimed.
Times belong to each complete stereo FX fixture: patcher graphs contain two
operator instances, while codebox arithmetic emits sum/difference and the
delta program contains one stateful operator plus an observer. They are not
isolated per-operator costs. Each case has 64 rendered vectors, four zero-input
warmup vectors and three paired rounds; the first 32 rendered vectors per pass
are excluded from timing. This is a short observed workload, not a deadline or
worst-case bound.

The three shared deterministic input programs cover bounded binary32 values in
`[-1,1]`, subnormals, signed zero, equality/adjacent values and vector edges.
The host independently regenerates complete input and expected-output cache
hashes and matches the actual target hashes. Repeated passes are not millions
of distinct inputs. Zero signs of operation outputs have a separate diagnostic
policy; the unchanged observer and identical-module pair require exact bits.
No unsupported rounding mode, arbitrary domain or overload is established.

All 52 loaded images were finalised, internal RAM/PSRAM recovered, and callback
heap/late allocation counts stayed zero. Each isolated run restored the drone
at 50% with its eight compiled defaults. Full records, per-case timing/resource
profiles and raw serial logs are in [the XIAO wave4 evidence](../evidence/xiao-wave4.json).
The earlier native O3/UBSan corpus separately passed 5,111,808 model checks;
those host checks are not counted as XIAO execution.

RNBO codebox is distinct from GenExpr. See the [separate Gen work](gen-qualification.md)
for the first native single-sample tests and the remaining Gen hardware scope.

## Measurement and recovery method

The device is the identified XIAO ESP32-S3, public label `xiao-test-device-01`, with
8 MiB flash and 8 MiB PSRAM. Firmware uses ESP-IDF 5.5, GCC 14.2, a 240 MHz CPU
and 80 MHz octal PSRAM. Tests use 44.1 kHz, 256-frame blocks, four warmup blocks,
512 blocks per case/pass, three paired rounds and seed `0x12345678`.
Timing excludes the first 32 blocks of each pass. The complete callback is timed;
preparation and event application have separate counters. I²S, display and
network are absent from the isolated benchmark.

The runner verifies the exact USB identity, backup hash, executable flash-size
header, application partition, build artifacts and current drone source/ELF.
It checks live defaults and 50% playback before muting, waits for muted readiness,
then writes only the application partition. Restoration is attempted even after
a failed test or lost acknowledgement. Startup50 recovery verifies the compiled
defaults directly, without replaying parameter changes while audible. A failed
restore verification attempts to mute and reports failure. Oscillator/filter
phase is restarted rather than restored.

The unique device identity and original full-flash backup stay private. Public
records use a stable device label and omit the recovery-backup digest. No bootloader or data partition
was written. The [public batch evidence](../evidence/xiao-object-batch1.json)
contains complete comparator summaries, raw serial logs, recovery records and
artifact hashes. Full float output buffers were compared internally; the
benchmark does not download those complete buffers. The retained final drone
capture checks post-restoration signal presence, not benchmark waveform truth.

The [main dashboard](https://little-scale.github.io/esp32s3-rnbo/) now includes
these 15 exact XIAO working-status entries with their board and mode scope in
the row details. Its prior timing percentages remain AMOLED measurements;
XIAO callback times and controls are recorded here without merging measurements.
Gen has its own inventory and native test record.

## Event and parameter interface limits

The current [event structure](../module-sdk/include/rnbo_s3_module.h) has no
sample timestamp or offset. The [dynamic wrapper](../module-sdk/dynamic/rnbo_s3_dynamic.cpp)
dispatches parameter/MIDI events at `RNBO::TimeNow`, advertises boundary events,
and accepts only 256-frame process calls. Ordinary parameter control exists in
the runtime and older parameterised fixtures. The fast batch compiler now admits
zero to 32 ordinary numeric parameters, and the new event batch verifies a single
linear/unstepped control at full-block boundaries across two batches of75 exact event graphs.

Those facts do not establish within-block host-event accuracy. A timed-event
interface or a separately admitted scheduled-kernel route is required before
such tests can qualify sample-offset controls; splitting this ABI into one-frame
calls would be rejected rather than prove sample accuracy. Further parameter modes and a timed-event extension remain pending work within the goal.
