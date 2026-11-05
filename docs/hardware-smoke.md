# Fast hardware functionality checks

Coverage now starts with a short device check. Each object gets a small input
vector with known expected outputs, a few warmup calls, and 16 timed callbacks.
Multiple modules share one firmware upload. An output mismatch is recorded and
the batch continues; a loader, process or memory fault stops the run.

These results mean **checked on hardware in the listed scenario**, not complete
mode/domain qualification. Deeper investigation is reserved for failures and
CPU-review flags. Existing, more extensive qualification records remain separate.

The test firmware is quiet after completion and does not run I²S audio, a display
or networking. Earlier batches sometimes left it installed, as their records
state. Current batches restore the normal player, saved Main and live controls,
then verify USB replies, advancing audio frames and runtime counters. This
prevents Studio reconnects from being stranded on a test-only application.

Before the resumed container batch, the MIDI-capable player ran the saved Main
patch. Its settings were saved privately, audio was muted and paused, and USB
was released before installing the quiet test application. The container smoke
firmware was left installed at that checkpoint; subsequent Gen, list-function
and codebox structure batches have since replaced it. Main package storage and Wi-Fi settings were
not erased. Earlier run records retain their own restoration/installation state.

## RNBO codebox context, units and exact aliases

51 exact sources run in two fixed partitions. **43 execute, 40 pass, three
retain per-sample clock comparison mismatches and eight are frontend rejections**,
with **440,320 output-word checks**. Four pass predicates, ternary/subtraction,
stateful named aliases, lexical compound assignments, context defaults and
fifteen conversions pass their exact bounded checks. MC values only pass a
finite integer screen in a non-MC patch; no exact MC semantics follow.

The currenttime, sampleoffset and currentsampletime primary references expect
per-sample values. Each retains 5,100 outside-limit differences. Separate native
SDK captures are consistent with callback-origin held values; sampleoffset is
zero. This diagnosis preserves all original mismatches and limits, and does
not assert an RNBO clock defect. Samplecount passes its callback-origin model.
Transport/conversion checks use fresh stopped 120 BPM, 4/4 and 480 PPQ defaults;
changed tempo/meter and host/MIDI clock events remain unqualified.

The rejected forms are exact infix `==p`, `!=p`, `!-`, `!/`, `!%`, `^^` and
`new +=()` / `new *=()` constructors. The two independently passing lexical
compound state programs do not qualify those constructor aliases. Their
auxiliary language checks do not add dashboard object rows. Preserving existing
`^^` evidence and adding 48 exact IDs brings the table to **837 scoped entries**.
Neither passing nor rejected spellings inherit across RNBO/Gen/patcher surfaces.

Every successful image finalises; all heap/allocation gates pass and arena
high-water is zero. References remain continuous for twenty 256-frame calls,
with zero automatic warmup and strict Float32 modules/original storage. Lossless
reference pooling stores 90/15 unique blocks and reconstructs the same complete
streams. There are 15,300 outside-limit differences, 16,005 within-limit
differences and 7,680 signed-zero differences, retained separately.

An initial second-partition run stopped at a device harness tolerance guard,
after 15 CASE lines and before hztoticks processing. The original per-case
0.002 output-unit limit exceeded the harness's 0.001 ceiling. The repair retains
that default for existing families and generates 0.002 only for this pinned
family. The rerun plan/modules/references/limits are identical; no primary
oracle is fitted. Stopped-run hashes remain in the native record, and partial
CASE lines supply no published completed-run measurements.

Thirteen conversion contexts exceed the median CPU budget, taking the queue
to **136**; no peak-spike rule triggers. mstobeats measures 2,104 µs median,
2,108 µs peak (36.25% of the block period). These are complete offline callback
costs, not isolated operation timings or measured optimisation gains. The
normal player, same saved Main and live controls are restored and checked.

See [part 1](../evidence/xiao-smoke-rnbo-codebox-context-aliases-part1.json),
[part 2](../evidence/xiao-smoke-rnbo-codebox-context-aliases-part2.json),
[native and stopped-run record](../evidence/rnbo-codebox-context-aliases-native.json),
[original sources/reference](../tests/fixtures/smoke/rnbo-codebox-context-aliases/README.md)
and [player restoration](../evidence/xiao-context-aliases-player-restoration.json).

## Extended Gen tables, sample access and boundaries

Thirty-one original GenExpr sources run in two fixed sixteen/fifteen-source
partitions. **24 execute on XIAO: 17 pass and seven retain output mismatches**,
across **245,760 output checks**. Three C++ rejections, two Gen frontend
failures and two external-resource adapter-preparation rejections stay separate
and are not executed. Gen evidence is separate from the 778 RNBO table mappings.

The programs cover wave/lookup forms, builtin and local-table cycle forms,
weighted splat writes, index/channel modes, returned indices, registered
read/write spellings and declaration forms. Tables are initialized explicitly;
original Float32 Data storage is preserved. The long oscillator uses 512/1024-
sample periods so a host reset at 256 samples changes the expected output.
Splat accumulation uses absolute prefix sums across all 20 callbacks; half mix
uses an ideal recurrence. Both those write-state cases pass their full streams.

| Exact authored scenario | Result | Median µs | Peak µs | Numerical mismatches |
| --- | --- | ---: | ---: | ---: |
| `wave-section` | Output mismatch | 188 | 188 | 9620 |
| `lookup-signal` | Pass | 807 | 811 | 0 |
| `lookup-samples` | Pass | 150 | 151 | 0 |
| `cycle-phase` | Pass | 554 | 556 | 0 |
| `cycle-frequency` | Pass | 328.5 | 330 | 0 |
| `cycle-local-name` | Output mismatch | 563 | 566 | 10240 |
| `splat-isolated` | Pass | 367 | 371 | 0 |
| `splat-accum` | Pass | 195 | 200 | 0 |
| `splat-mix-half` | Pass | 200.5 | 205 | 0 |
| `splat-phase` | Pass | 378 | 383 | 0 |
| `peek-bound-ignore` | Pass | 91 | 95 | 0 |
| `peek-bound-wrap` | Pass | 258 | 263 | 0 |
| `cycle-frequency-long-period` | Pass | 410 | 436 | 0 |
| `peek-bound-clamp` | Pass | 96 | 100 | 0 |
| `peek-bound-fold` | Output mismatch | 175.5 | 180 | 5120 |
| `peek-bound-mirror` | Pass | 175 | 180 | 0 |
| `peek-channel-ignore` | Pass | 72 | 76 | 0 |
| `peek-channel-wrap` | Pass | 91 | 96 | 0 |
| `peek-channel-clamp` | Output mismatch | 82 | 86 | 1600 |
| `peek-channel-fold` | Output mismatch | 89 | 93 | 5120 |
| `peek-channel-mirror` | Output mismatch | 88.5 | 94 | 2240 |
| `peek-return-index` | Pass | 89 | 93 | 0 |
| `sample-return-index` | Output mismatch | 171 | 176 | 1400 |
| `data-lowercase` | Pass | 58 | 63 | 0 |

The batch retains 35,340 numerical mismatches, 8,296 within-tolerance differences
and 1,920 signed-zero differences. No input, tolerance or reference is fitted
after target output. Wave section, named local-table cycle, index fold,
channel clamp/fold/mirror and returned wrapped phase indices retain gaps against
the declared reference policies. Builtin cycle, long-period sample state,
lookup, weighted splat writes, index ignore/wrap/clamp/mirror, channel ignore/
wrap on XIAO, returned sample indices and lowercase data dimensions pass.

**Five negative-channel cases differ between native and target execution.**
Generated channel arguments convert floating values to unsigned Index before
boundary handling. A separate host UBSan/float-cast-overflow run stops on -2
converting to unsigned int. This is an evidenced portability issue; native
results are not substituted for the device oracle. Channel ignore/wrap pass
on this XIAO image while failing the native screen; clamp does the reverse.
Fold/mirror policies and signed conversion still require qualification/repair.
The sanitizer run is a host diagnostic, not target sanitizer coverage.

The failed source forms are explicit. Wave sample/phase constructors fail
frontend boundmode handling. Positional local-table cycle passes a buffer
reference to a numeric oscillator argument. Standalone read/write emit an
undeclared Delay identifier; write also retains an unreviewed bool-compare
warning. Upper/lower Buffer declarations reject externalDataRefs during normal
adapter admission, so no real external buffer binding is claimed.

Only signal-indexed lookup triggers CPU review: 807 µs median, 811 µs peak,
**13.90%** of the audio period. The queue rises to **111 contexts**. Other
medians span 58–563 µs and no peak-spike rule triggers. These are complete
callbacks, without I²S/network/display work or an optimisation comparison.
Data programs observe 128 bytes arena high-water, builtin oscillator pairs
65,648 bytes and the named-table cycle program 65,776 bytes. The 2 MiB arena is
only a test ceiling. All 24 images finalise and memory/allocation gates pass.
Quiet part 2 firmware remains installed.

See [original sources and reference policy](../tests/fixtures/smoke/gen-data-extended/README.md),
[target part 1](../evidence/xiao-smoke-gen-data-extended-part1.json),
[target part 2](../evidence/xiao-smoke-gen-data-extended-part2.json) and
[native/sanitizer and rejection diagnostics](../evidence/gen-data-extended-native.json).
Remaining Gen modes, resources, visual forms and one-frame production calls
stay in the full goal.

## Delay resources and member operations

Thirty-three original sources cover thirteen exact delay/comb/allpass member
IDs. **22 programs execute on XIAO: 17 pass and five retain output mismatches**,
across **225,280 output checks**. Eleven string-enum read-call programs reject
in C++; numeric-enum counterparts are distinct sources. Rejections in the
write/step programs occur at their accompanying read argument, rather than
showing a write/step primitive failure. Source and log hashes remain recorded.

The bounded delay requests 16 samples. Comb/allpass keep default storage.
Observed arena high-water is 192 bytes and 1,048,704 bytes respectively, within
the 2 MiB test arena reservation. All 22 loaded images finalise, free internal/
PSRAM totals return unchanged and no late-allocation/process fault occurs.
This strict unchanged-storage screen makes no Auto Float32 gain claim.

| Exact scenario | Result | Median µs | Peak µs | Median / audio period | CPU review |
| --- | --- | ---: | ---: | ---: | --- |
| `delay-next-integer` | Pass | 243 | 248 | 4.19% | — |
| `delay-clear-integer` | Pass | 292 | 297 | 5.03% | — |
| `delay-reset-integer` | Pass | 309 | 310 | 5.32% | — |
| `delay-size-capacity` | Pass | 47 | 47 | 0.81% | — |
| `comb-next-integer` | Pass | 753 | 757 | 12.97% | Queued |
| `comb-clear-integer` | Pass | 43960.5 | 43963 | 757.29% | Queued |
| `comb-reset-integer` | Pass | 43971 | 43973 | 757.47% | Queued |
| `allpass-next-integer` | Pass | 984.5 | 989 | 16.96% | Queued |
| `allpass-clear-integer` | Pass | 44187 | 44193 | 761.19% | Queued |
| `allpass-reset-integer` | Pass | 44189 | 44194 | 761.22% | Queued |
| `delay-next-linear-half` | Output mismatch | 243 | 248 | 4.19% | — |
| `delay-read-integer-numeric-enum` | Pass | 184 | 189 | 3.17% | — |
| `delay-write-overwrite-numeric-enum` | Pass | 218 | 223 | 3.76% | — |
| `delay-step-double-numeric-enum` | Pass | 190 | 194 | 3.27% | — |
| `delay-read-linear-numeric-enum` | Pass | 259 | 263 | 4.46% | — |
| `delay-read-cosine-numeric-enum` | Pass | 1418 | 1422 | 24.43% | Queued |
| `delay-read-cubic-numeric-enum` | Output mismatch | 1454 | 1454 | 25.05% | Queued |
| `delay-read-fastcubic-numeric-enum` | Output mismatch | 361 | 366 | 6.22% | — |
| `delay-read-spline-numeric-enum` | Output mismatch | 1533 | 1537 | 26.41% | Queued |
| `delay-read-spline6-numeric-enum` | Output mismatch | 550.5 | 553 | 9.48% | — |
| `delay-read-step-numeric-enum` | Pass | 203 | 207 | 3.50% | — |
| `delay-read-none-numeric-enum` | Pass | 202.5 | 207 | 3.49% | — |

All 17 passing programs have zero numerical mismatches. The complete batch
retains 25,591 numerical mismatches, 4,858 within-tolerance differences and zero
signed-zero differences. No reference or tolerance was changed after output.
Integer next/read, overwrite-before-step, double physical step, size 16,
clear/reset and comb/allpass feedback recurrences pass. Explicit linear/cosine
fractional reads and numeric step/none modes also pass.

The five mismatches remain scoped: fractional next emits an integer size
parameter, while explicit read accepts fractional size. Four higher-order read
windows differ from the predeclared centered Lagrange/Hermite/B-spline physical
alignment. This requires delay/window-alignment follow-up; it does not reject
the separately checked scalar interpolation kernels. The original references
and both call forms remain available for reproduction.

**Nine CPU contexts join the queue, bringing it to 110.** In particular,
default comb/allpass clear/reset scenarios take 43.96–44.19 ms per 256-frame
callback, roughly 7.6 times the 5.805 ms audio period. Their authored schedules
usually clear roughly 1 MiB of buffer state twice per block. These are offline
checks, with no I²S deadline claim. Review storage settings and reset scheduling
before considering a semantics-preserving clearing optimisation. Baseline
comb/allpass next and cosine/cubic/spline read costs are also queued.
No separate peak-spike rule triggers and no optimisation gain is claimed.

The dashboard now maps **778 exact entries with scoped outcomes**; delay next
and read retain partial labels. Other capacities/taps, resource sharing,
helper return values, arbitrary parameter/rate/vector-size domains, aliases,
Gen and complete alignment semantics remain pending. Quiet resource-test
firmware stays installed.

See [sources and detailed contract](../tests/fixtures/smoke/rnbo-codebox-delay-members/README.md),
[hardware results](../evidence/xiao-smoke-rnbo-codebox-delay-members.json) and
[native, enum and compiler diagnostics](../evidence/rnbo-codebox-delay-members-native.json).

## Explicit stateful members and reset/clear

Thirty-six authored sources run in two fixed eighteen-source partitions.
**35 execute on XIAO: 27 pass, eight retain output mismatches**, across
**358,400 output checks**. `history.reset()` fails C++ compilation and is not
executed. These exact member observations are separate from owner constructors,
aliases and Gen. An existing detailed `delta.next()` qualification is retained;
35 additional member entries bring the RNBO table to **765 scoped mappings**.

Two independent instances step bounded inputs. Reset/clear cases use different
per-channel schedules, including consecutive calls and resets at absolute
samples 255/256 and 511/512. They compare 20 continuous callbacks without an implicit
host-boundary reset. Ideal mathematical filter/slide references use the original
predeclared 2e-6 limit; other cases use zero tolerance. Inputs, references and
limits were fixed before native/target output. The results separately retain
**43,712 numerical mismatches, 42,569 within-tolerance differences and 1,292
signed-zero differences**.

| Authored scenario | Result | Median µs | Peak µs | Numerical mismatches |
| --- | --- | ---: | ---: | ---: |
| `delta.next()` | Pass | 58 | 63 | 0 |
| `delta.reset()` | Pass | 141 | 145 | 0 |
| `change.next()` | Pass | 73 | 78 | 0 |
| `change.reset()` | Pass | 165 | 170 | 0 |
| `latch.next()` | Pass | 67 | 68 | 0 |
| `latch.reset()` | Pass | 152 | 156 | 0 |
| `sah.next()` | Pass | 84 | 89 | 0 |
| `sah.reset()` | Pass | 164 | 168 | 0 |
| `slide.next()` | Pass | 402 | 402 | 0 |
| `slide.reset()` | Pass | 500.5 | 503 | 0 |
| `dcblock.next()` | Pass | 70 | 71 | 0 |
| `dcblock.reset()` | Pass | 152 | 157 | 0 |
| `accum.next()` | Pass | 61 | 61 | 0 |
| `accum.reset()` | Pass | 145 | 150 | 0 |
| `counter.next()` | Pass | 71 | 71 | 0 |
| `counter.reset()` | Pass | 166 | 171 | 0 |
| `deltaclip.next()` | Pass | 74 | 74 | 0 |
| `deltaclip.reset()` | Pass | 162 | 167 | 0 |
| `downsamp.next()` | Output mismatch | 104 | 108 | 7290 |
| `downsamp.reset()` | Output mismatch | 194 | 199 | 7308 |
| `zerox.next()` | Output mismatch | 73 | 78 | 640 |
| `zerox.reset()` | Output mismatch | 166 | 171 | 659 |
| `zerox_count.next()` | Output mismatch | 118 | 123 | 3840 |
| `zerox_count.reset()` | Output mismatch | 207 | 212 | 3785 |
| `onepole.next()` | Pass | 122.5 | 126 | 0 |
| `onepole.reset()` | Output mismatch | 221 | 225 | 10095 |
| `onepole_lin.next()` | Pass | 106.5 | 111 | 0 |
| `onepole_lin.reset()` | Pass | 190 | 195 | 0 |
| `biquad.next()` | Pass | 91 | 95 | 0 |
| `biquad.reset()` | Pass | 172 | 173 | 0 |
| `elapsed.next()` | Pass | 56 | 60 | 0 |
| `elapsed.reset()` | Pass | 140 | 144 | 0 |
| `onepole.clear()` | Output mismatch | 221 | 226 | 10095 |
| `onepole_lin.clear()` | Pass | 192 | 196 | 0 |
| `biquad.clear()` | Pass | 172 | 176 | 0 |
| `history.reset()` | C++ rejection; not executed | — | — | — |

The compatibility follow-ups remain explicit. Downsample capture phase differs
from the declared capture-at-age-zero convention. Zero-crossing and windowed
counts differ on zero-containing inputs from the strict opposite-nonzero policy.
One-pole reset/clear produces zero output at unchanged cutoff: source inspection
shows coefficients are cleared while cached cutoff/update state is preserved,
so the next call does not recompute them. Its first left numerical discrepancy
is at frame 38, with maximum error about 0.67885. The documented history member
fails because generated C++ references missing history instance fields.

All 35 images finalise and pass memory/allocation gates, with zero arena
high-water. Medians span 56–500.5 µs (**0.96–8.62%** of the block period), with
largest peak 503 µs. **No new CPU flag** triggers, leaving 101 contexts queued.
Whole callbacks include scheduling/modulo/branch work and occasional reset
calls; these are not isolated member costs or optimisation gains. The second
quiet member-test firmware stays installed. No DSP repair is made in this batch.

See [original sources and detailed policy](../tests/fixtures/smoke/rnbo-codebox-members/README.md),
[target part 1](../evidence/xiao-smoke-rnbo-codebox-members-part1.json),
[target part 2](../evidence/xiao-smoke-rnbo-codebox-members-part2.json) and
[native diagnostics](../evidence/rnbo-codebox-members-native.json).

## RNBO codebox structures and lifecycle

All **24 original language/lifecycle programs pass on XIAO**, with
**245,760 output checks**, zero finite numerical mismatches and no nonfinite
outputs. Native preflight and hardware agree on the complete reference streams
and **3,700 signed-zero differences** in five loop programs. These differences
remain diagnostic; the batch establishes scoped numeric equality, not bit identity.

The corpus checks declaration forms and lexical scope, precedence, if/else,
ternary and logical short-circuit side effects, switch/default/fall-through,
bounded for/nested-for/while/do-while/break/continue, scalar/list-return functions,
sample delay, separate state fields, internal parameter defaults and lifecycle
hooks. Loop counts include zero through five; sample-state checks cross all
20 callbacks. References were fixed before compilation and use independent
closed-form sums, prefix counts and sample age.

| Exact authored scenario | Median µs | Peak µs | Signed-zero differences |
| --- | ---: | ---: | ---: |
| `declarations` | 47 | 51 | 0 |
| `typed-declarations` | 47 | 51 | 0 |
| `lexical-shadow` | 47 | 51 | 0 |
| `precedence` | 48 | 52 | 0 |
| `if-else` | 56 | 61 | 0 |
| `ternary-state` | 59 | 63 | 0 |
| `logical-and-state` | 57 | 62 | 0 |
| `logical-or-state` | 59 | 59 | 0 |
| `switch` | 53 | 57 | 0 |
| `switch-fallthrough` | 56 | 60 | 0 |
| `for-bounded` | 75 | 80 | 740 |
| `for-nested` | 84 | 89 | 740 |
| `for-break-continue` | 86 | 91 | 740 |
| `while-bounded` | 77 | 82 | 1160 |
| `do-while-bounded` | 74 | 75 | 320 |
| `function-scalar` | 47 | 51 | 0 |
| `function-list` | 41.5 | 46 | 0 |
| `state-delay` | 42 | 43 | 0 |
| `state-independent` | 47 | 51 | 0 |
| `param-default` | 45 | 49 | 0 |
| `hook-init` | 44 | 48 | 0 |
| `hook-startup` | 43.5 | 44 | 0 |
| `hook-dspsetup` | 43.5 | 44 | 0 |
| `hook-combined` | 45 | 49 | 0 |

These complete 256-frame callbacks at 44.1 kHz measure **0.71–1.48%** median
CPU, with no new CPU-review flag. The queue remains **101 contexts**. All 24
images finalise, with zero arena high-water, no late-allocation faults and
unchanged internal/PSRAM totals. The quiet structure-test firmware remains
installed. No DSP optimisation or percentage performance gain is claimed.

The lifecycle check observes one call to each hook during fresh initialize/
prepare, and startup observing init's state. Later DSP restarts, repeated prepare,
reset/reconstruction and sample-rate/vector-size changes remain untested.
The internal parameter test covers only its default value. Arbitrary programs,
integer conversion endpoints, event codebox, recursion and Gen are separate
scope. The three exact lifecycle entries enter the RNBO table; other structures
update the qualification plan. The table now maps **730 entries with scoped
outcomes**, not 730 fully qualified objects.

See [original sources and execution policy](../tests/fixtures/smoke/rnbo-codebox-structures/README.md),
[hardware results](../evidence/xiao-smoke-rnbo-codebox-structures.json) and
[native preflight](../evidence/rnbo-codebox-structures-native.json).

## RNBO list-function call forms

Thirty-four original sources cover flattened global list functions, dotted
registry call forms and separate helper functions. **Ten execute on XIAO:
nine pass and one retains a reference mismatch**, across **102,400 output
checks**. Seven sources fail C++ array-bounds warning checks. Fifteen dotted
member-call sources and the full scramble-validation program reject in the
frontend. A wide rotation vector fails native preflight and is not flashed;
its source, actual fault and untested hardware status remain explicit.

The nine passing functions are `listindexmap`, `listjoin`, `listlace`, `listlen`,
`listsum`, `listswap`, `listthin`, `listunion` and `listswapelements`. Length-
sensitive weighted fingerprints expose bounded values/indices. `listsect`
differs in all 5,120 left fingerprints from the declared duplicate-preserving
intersection reference; its right pilot matches. The first witness, 208 versus
314, is consistent with unique-set behavior, but is not a full list capture or
a settled duplicate-policy contract. The reference and zero tolerance remain.

All executed images finalise with memory/allocation gates passing. Medians
span 40–917 µs, largest observed peak 917 µs. `listswap` at 917 µs and `listunion`
at 861 µs exceed the median CPU threshold, bringing the backlog from 99 to
**101**; no peak-spike flags trigger. These complete callbacks include list
construction/copies/fingerprints and claim no optimisation gain. The dashboard
maps **727 exact entries**; a rejected spelling remains unverified.

The native rotation fault is a first-class admission outcome, not a failed
target run or a compilation failure. Its log/source/vector/harness identity
is verified before the shared target payload omits it. The newly explicit
native diagnostic returns process statistics instead of aborting at an opaque
assertion. Dotted inventory spellings do not inherit the separately documented
flattened function's result. Scramble's minimal call exports, while the full
invariant program rejects; no random-quality/device claim follows.

See [target results](../evidence/xiao-smoke-rnbo-codebox-list-functions.json),
[native checks and rejection diagnostics](../evidence/rnbo-list-functions-native.json)
and [original sources, policy limits and timing table](../tests/fixtures/smoke/rnbo-codebox-list-functions/README.md).

## Gen control, declarations and language structures

Nineteen programs execute and **all pass their zero-numeric-tolerance screen**,
checking **194,560 output values** over twenty continuous callbacks each.
Twelve GenExpr pass-gate spellings (`eqp`/`==p`, `neqp`/`!=p`, `ltp`/`<p`,
`ltep`/`<=p`, `gtp`/`>p`, `gtep`/`>=p`) are independently authored. Uppercase
`Param` default gain, lowercase `elapsed`, lowercase `history`, a function with
two independent local-History instances, and bounded for/while/break/continue
also pass. Delay samples and elapsed ordinals cross all host callback edges.

Both native and target retain **33,360 signed-zero word differences**, with
matching per-case counts and zero finite numerical error. Those differences
are outside the numeric zero gate and remain visible; no bit-identity claim,
tolerance relaxation or target-fitted reference follows. All images finalise
and memory/allocation checks pass, with zero arena high-water and unchanged
free internal/PSRAM totals. The context is 12,720 bytes for every program.

Five source forms fail C++: lowercase `param` declaration, uppercase `ELAPSED`,
bare `voice` and `VOICE`, and `constant(...)`. A multiple-return custom function
and an if/else-if History program are rejected by the Gen frontend before C++.
These exact forms keep their source/rejection hashes; their outcomes do not
qualify or reject another alias, visual Gen operator or language construct.

Medians span 42–94.5 µs (at most 1.63% of the block period), peak 99 µs
(1.71%). No CPU flag triggers, so the backlog remains 99. Whole callback
timings are not isolated opcode costs or speedups. All sources keep their
original strict storage/processing policy. Host parameter updates, voice
polyphony, visual Gen, one-frame production calls and broader domains remain
pending within the active goal.

See [target evidence](../evidence/xiao-smoke-gen-control-structures.json),
[native checks and diagnostics](../evidence/gen-control-structures-native.json)
and [original programs, models and timing table](../tests/fixtures/smoke/gen-control-structures/README.md).

## RNBO codebox lists and fixed arrays

The resumed batch covers all seventeen installed fixed-array constructor names
and eleven documented list member names. **26 executable cases pass**, with
**266,240 bit-exact output checks** across twenty continuous callbacks. Both
native preflight and target use the same input and full expected-stream hashes.
Zero automatic preparation blocks preserve the constructor epoch, followed by
four checked warmups and sixteen timed callbacks. All images finalise and pass
allocation/memory gates; fixed arrays preserve their requested original types.

Each sample-dependent list exposes the returned scalar/list plus original-list
mutation through weighted checksums. Five-cell arrays expose current writes,
initial values and four-sample-old cells across every host block boundary.
Explicit list result types follow the codebox guide. The `push` and `unshift`
length-return programs reach C++ but fail because their generated runtime calls
return `void`; they are compile failures, with no device or CPU claim.

List medians range from 58 to 865.5 µs, peaks from 63 to 866 µs. `shift`,
`concat`, `fill`, `splice` and `reverse` exceed the 10%-of-block review threshold,
bringing the CPU queue from 94 to **99**; no peak-spike rule triggers. Array
medians are 97–258.5 µs, peaks 101–263 µs, with no flags. All timings cover the
authored callback and its construction/copy/checksum or indexing work, not an
isolated method or optimisation comparison. The dashboard maps **693 exact
entries**, with the two rejected source forms kept unverified.

Earlier native-only constant-list experiments retain a separate vector-hoisting/
empty-list follow-up; no unsafe prototype was flashed. Arbitrary growth,
dimensions, integer overflow, mutation-only push/unshift, generic language
structures and Gen remain outside this scoped result.

See [target evidence](../evidence/xiao-smoke-rnbo-codebox-containers.json),
[native evidence](../evidence/codebox-containers-native.json),
[original sources and detailed table](../tests/fixtures/smoke/rnbo-codebox-containers/README.md)
and [CPU review backlog](cpu-review-backlog.md).

The latest signal routing and interpolation batch passes **all 20 scenarios**,
checking **204,800 output values**. `cubicinterp~` takes 3,367 µs median
(58.00% of the audio block period) and is queued for later CPU review, bringing
the queue to 93. Numerical differences remain separate; no optimisation gain
is claimed.

The earlier signal-stateful and miscellaneous codebox batches execute **37
scenarios: 36 pass and one retains a declared capture-phase mismatch**, across
**378,880 output values**. Five passing callback contexts add CPU-review flags,
bringing the queue to 92. References and limits remain unchanged; no DSP
optimisation or measured gain is claimed.

The earlier direct signal range and codebox filter/delay batches execute **49
scenarios: 46 pass their declared references and three retain signal mismatches**,
across **501,760 output values**. Every source compiles and executes. Eleven new
passing CPU-review contexts bring the queue to 87; no DSP optimisation or
measured gain is claimed.

The earlier RNBO codebox shaping and stateful batches execute **51 scenarios:
48 pass their declared references and three retain mismatches**, across
**522,240 output values**. Two additional source forms are rejected before
execution. Eighteen passing shaping contexts triggered CPU review, bringing the queue to
76 at that stage. No DSP optimisation or measured gain is claimed.

The earlier RNBO codebox range and Gen named-constant batches execute **72
scenarios: 68 pass their declared comparisons and four retain mismatches**,
checking **737,280 output values**. Seven additional codebox source forms are
rejected before execution. Six new CPU-review contexts bring the queue to 58;
no DSP change or optimisation gain is claimed.

The earlier RNBO codebox numeric and Gen range batches execute **72 scenarios:
65 pass their declared comparisons and seven retain mismatches**, across
**737,280 output checks**. One additional Gen `gate` source is rejected before
execution. Twenty new CPU-review contexts bring the queue to 52; no DSP change
or optimisation gain is claimed. RNBO codebox and Gen results remain separate.

## Gen local Data and indexed storage

All **eight programs pass**, checking **81,920 output values** across fresh
preparation and twenty continuous 256-frame callbacks. They exercise a local
`Data(7,2)` declaration and the separate `dim`, `channels`, `peek`, `poke`,
`nearest` and `sample` function forms. Declaration evidence does not qualify a
similarly named standalone operator or alias.

The independent references check dimensions 7/2, zero-based channels, explicit
sample indices, read-before-write seven-frame rings and same-sample write/read
visibility. Two initialized tables support integer nearest reads and bounded
quarter-sample linear interpolation; their authored initialization writes the
14 cells only at the first sample. A separate seven-sample feedback program
uses an independent 64-term input convolution. No automatic preparation blocks
precede four checked manual warmups and sixteen timed callbacks.

The seven non-feedback cases are raw-word exact, including zero signs. Feedback
passes its unchanged 2e-6 limit with 2,178 within-limit word differences and
maximum error 2.9802322387695312e-8. No reference, input or limit is fitted to
the measured output.

This producer lowers local Data to `SampleBuffer<SampleValue>`. In the ordinary
Float32 backend its 7×2 cells contain 56 logical payload bytes; generic Gen
64-bit prose is not a storage-equivalence claim for this export. The original
producer representation is preserved, with no narrowing adapter. Each program
measures 128 bytes of arena high-water under a 4 KiB ceiling, separately from
its 12,784-byte opaque context. All eight images finalise and pass memory/
allocation checks, with no external Buffer resource.

Medians span 48–687 µs, peaks 52–688 µs. The whole Data feedback program is
queued for CPU review at 687/688 µs, or 11.83%/11.85% of the block period. The
queue reaches 94 contexts; this is not isolated Data-access cost or a measured
optimisation gain. Variable sizes, arbitrary bounds/interpolation, overdub modes,
external Buffer, visual Gen and a one-frame host ABI remain unqualified.

See [the complete results](../evidence/xiao-smoke-gen-data-indexed.json) and
[original programs, references and storage notes](../tests/fixtures/smoke/gen-data-indexed/README.md).

## RNBO character constants

All **85 remaining bare character-constant names pass** on XIAO, split into
43/42-module uploads. The two batches check **870,400 output words**, all exact:
435,200 constant outputs and 435,200 right-input copies, including zero signs.
The ten digit constants already have separate passing hardware evidence, so
all 95 printable-ASCII names now have scoped bare-value observations.

Primary metadata defines these as numeric codebox values rather than published
patcher objects. Each original program assigns the exact `CHAR_*` name to its
left output and copies `in2` to the right. Independent name-to-character
`ord()` references cover ASCII 32–126; case-safe file IDs distinguish uppercase
and lowercase names. The sparse `in2` codebox name exposes physical inlet 0,
which is explicitly wired and checked by the dedicated source guard.

Zero numeric tolerance and a strict right-channel zero-sign mask enforce raw
pilot equality. No automatic preparation blocks precede four checked manual
warmups and sixteen timed callbacks. Medians span 40–40.5 µs, peak 45 µs;
no CPU flag triggers. All images finalise and pass memory/allocation checks,
with zero arena high-water under a 4 KiB capacity. No optimisation comparison,
function-call syntax, string/list behavior or cross-surface qualification follows.

See [part one](../evidence/xiao-smoke-rnbo-character-constants-part1.json),
[part two](../evidence/xiao-smoke-rnbo-character-constants-part2.json) and
[original programs and independent references](../tests/fixtures/smoke/rnbo-character-constants/README.md).

## Further RNBO signal state

Seven configured programs execute **71,680 output checks: six pass and one
retains a mismatch**. Four exact owners are covered: `onepole_lin~`, `onoff~`,
`counter~` and `normalize~`. Zero automatic preparation blocks precede four
checked manual warmups and sixteen timed callbacks, with full twenty-block
continuous references and no boundary state resets.

Two onepole programs check fixed 0.25/0.5 linear coefficients and a signal
coefficient with a copied pilot. Both pass 2e-6; maximum error is
7.450580596923828e-9, with 5,628 within-limit word differences. Two counter
graphs observe count, flag and carry count across reset and wrap at limits
0/7. Only 0/1 increments are supplied, so overshoot behavior is unqualified.
Two normalization graphs check current-inclusive persistent absolute peak,
fixed or signal maxima and the documented minimum denominator. All counter
and normalization outputs match exactly, including zero signs.

`onoff~` differs from the unchanged DSP-block toggle reference in 5,120 words.
The first difference is callback 0, interleaved word 2: actual 0 versus expected
1. Source review finds the boolean toggled inside every sample iteration;
primary documentation describes one toggle per DSP block. This is a vector-
granularity compatibility follow-up, rather than an initial-state or CPU issue.
The source-derived pattern explains the saved count and witness, without
replacing the independent reference or claiming a complete target capture.

Callback medians span 46–189 µs, peaks 50–194 µs. No CPU flag triggers; all
seven images finalise and pass memory/allocation checks with zero arena
high-water use. No performance gain is claimed. `updown~` was omitted before
export because its adaptive transient lacked an independently justified
pointwise reference; it remains reference-design-pending.

See [the hardware results](../evidence/xiao-smoke-rnbo-signal-state-followup.json),
[separate source review](../evidence/rnbo-signal-state-followup-review.json)
and [original graphs and references](../tests/fixtures/smoke/rnbo-signal-state-followup/README.md).

## Gen Delay compilation repair and rerun

The two previously blocked Gen `Delay(16)` declaration/method programs now
pass **20,480 output checks** with their original inputs, limits and continuous
twenty-block references. One- and three-sample FIFO outputs are raw-word exact;
the feedback case passes 2e-6 with maximum error 7.450580596923828e-9.
Three guarded integer casts resolve the generated-code warning without
disabling it or changing numerical semantics, Float64 rings or state order.

Medians are 318/411 µs and peaks 320/415 µs, with no CPU flags. Both modules
finalise and pass memory/allocation checks. This validates the tested per-sample
delay inside fixed-256 callbacks, rather than a one-frame host API. The original
failed builds and five other Gen mismatches remain preserved. See
[the scoped repair and results](gen-delay-bool-clamp.md),
[marked rerun](../evidence/xiao-smoke-gen-delay-boolcast.json) and
[transformation evidence](../evidence/gen-delay-bool-clamp.json).

## Bounded Float32 dbtoa comparison

The separately scoped [Float32 dbtoa experiment](dbtoa-float32.md) passes all
48 matched target runs and 491,520 independent output checks. Four input vectors
run in three ABBA rounds, with identical graph/compiler/SDK/ABI/arena limits.
Across 384 timed callbacks per profile, mean time falls from 15,869.50 to
1,326.51 µs: **91.64% less callback time**, or 273.38% → 22.85% of the audio
block period. The maximum candidate numerical error is 1.1920928955078125e-7;
changed rounding remains explicit. Native pairwise PCM identity is separate
from target accuracy; no direct target A/B float/PCM comparison is claimed.

This exact-graph CLI experiment does not change Studio Auto or qualify other
objects, modes or surfaces. Its repeated CPU screens are not 48 new object
contexts. See [all target case timings](../evidence/xiao-smoke-dbtoa-f32-comparison.json)
and [combined evidence](../evidence/dbtoa-float32.json).

## Gen clock, reset and delay boundaries

Eight authored Gen programs are retained: **six compile and execute; one
passes its declared reference and five retain output mismatches. Two delay
programs fail C++ compilation before execution.** The six executed programs
check 61,440 output values, using fresh preparation, zero automatic warm blocks
and twenty continuous callbacks. No numerical limits are changed after output.

| Program | Declared comparison result |
| --- | --- |
| Free dyadic `phasor` pair | Six differences; first at callback 4, word 0: actual 1 versus expected 0. |
| Signal-reset `phasor` pair | One difference; first output is 0 versus the reference's initial phase 0.125. |
| Odd-period `train` pair | 2,392 differences; first at callback 0, word 6: actual 0 versus expected 1. |
| `train` with onset and changing widths | 2,667 differences; first at callback 0, word 12: actual 1 versus expected 0. |
| Sync-off `rate`, multipliers 8/16 | 18 differences; first at callback 2, word 0: actual 1 versus expected 0. |
| Nonzero-initialised `mulequals`, with resets | All 10,240 checks pass the zero-error reference. |

The phase references declare capture, reset and wrap-endpoint policies; these
failures do not by themselves prove state resets or broken objects. Their
reference streams and first witnesses remain saved for separate review.
Source review explains the phasor/rate endpoint samples as wrapping only above
1, and the reset phasor's first sample as constructor phase 0 despite its
configured phase attribute. The latter remains a possible initial-attribute
semantic gap because primary documentation calls it an initial phase. Train
increments before threshold/capture, and width endpoints bypass phase advance.
A source-derived replay reproduces the five counts and first witnesses; this
is a diagnosis, not a replacement independent oracle or full target capture.
The [separate source-review record](../evidence/gen-state-boundaries-review.json)
binds those observations to the actual prepared source and saved target results.
`rate` multipliers were resolved from primary documentation and changed to
8/16 before any DSP execution, giving dyadic 512-sample phase periods. Train
periods 7/11 are explicitly in samples in the Gen documentation.

Both explicit maximum-16-sample `Delay` declaration/method programs export and
prepare, but generated constant-versus-boolean delay clamps trigger GCC
`-Werror=bool-compare`. Their unchanged compiler failures are retained. There
is no hardware one-sample delay or feedback-delay pass from this batch, and no
standalone `delay`, `read` or `write` operator qualification follows.

Executed callback medians span 90–161 µs, with peaks 94–166 µs; no CPU-review
flag triggers. All six images finalise and pass memory/allocation checks,
with zero measured arena high-water use. Fixed-256 processing remains distinct
from a one-frame host ABI. See [the saved results](../evidence/xiao-smoke-gen-state-boundaries.json)
and [original programs and predeclared references](../tests/fixtures/smoke/gen-state-boundaries/README.md).

## RNBO signal routing and interpolation

All **20 exact spellings pass** their independent references on XIAO. The six
routing forms cover `gate~`, `selector~` and four named send/receive spellings.
Gate and selector choices change within the block among 0/1/2; the gate fixes
its ramp to zero. Named buses connect distinct stereo names inside one RNBO
graph. Other bus scopes, feedback routes and fractional choices remain open.

The four interpolation forms use asymmetric literal keyframes and Float32
phases in [0,1], including endpoint and midpoint neighbours. References
distinguish Lagrange, full-slope Hermite, Catmull–Rom and six-point quintic
B-spline equations. Ten further signal spellings check pass comparisons,
boolean aliases, subtraction and conditional selection independently.

Zero automatic preparation warm blocks precede four checked manual warmups
and sixteen timed 256-frame callbacks per source. All 204,800 output checks
pass their predeclared limits: zero for routes/comparisons and 2e-6 for
interpolation. There are 10,240 interpolation word differences, with maximum
absolute error 5.960464477539063e-8, and 3,520 gate zero-sign differences.
These remain diagnostics; the whole batch is not bit-exact.

Callback medians span 47–3,367 µs. `cubicinterp~` is the sole CPU-review flag,
at 3,367 µs median/3,371 µs peak (58.00%/58.07% of the block period).
These are complete stereo fixture costs, not isolated operator timings.
Every module finalises and passes memory/allocation checks; all reserve a
4 KiB arena and report zero arena high-water use. The quiet test firmware
remains installed. No Gen, one-frame host ABI or optimisation gain follows.

See [the complete routing results](../evidence/xiao-smoke-rnbo-signal-routing.json),
[the original graphs and references](../tests/fixtures/smoke/rnbo-signal-routing/README.md)
and [CPU review queue](cpu-review-backlog.md).

## RNBO signal state across callback boundaries

All **15 signal scenarios execute: 14 pass and one retains a phase-policy
mismatch**, across 153,600 output checks. Each uses zero automatic preparation
warm blocks, four checked manual warmups and sixteen timed callbacks. The full
twenty-block references cover 5,120 continuous frames without resets at vector
boundaries, including accumulation, held values, window reports and previous-
sample history. Explicit DC gains, rates, thresholds and windows remain scoped.

| Retained comparison | Observation |
| --- | --- |
| `downsamp~`, factors 3/5 | 7,290 mismatches; maximum error 2 against the unchanged first-capture-at-ordinal-0 reference. First difference: callback 0, interleaved word 4, actual 0.25 versus expected 0. |

Primary prose does not specify first-capture phase. A source review explains
the difference as first captures at samples 2/4 for factors 3/5, then every N
samples. The period remains N; this is a declared phase-policy observation,
not a universal broken-object or state-reset verdict. The reference is retained
rather than shifted to fit output. The 640 operation zero-sign differences
remain diagnostics; the whole batch is not bit-exact.

`delta~` and `sah~` now have separate short XIAO observations alongside their
broader native evidence. `slide~` passes this fixed 2/4-rate scenario but retains
its partial status because the earlier long signed-rate native failure remains.
All original qualification, optimisation and performance records are preserved;
canonical `sah`, codebox and Gen forms inherit nothing from the alias result.

Medians span 50–743 µs, peak 748 µs. The two passing average variants trigger CPU
review: `average_absolute~` at 597 µs median/603 µs peak and `average_rms~` at
743/748 µs. Their original dual Float64 buffers remain, with 705,760-byte measured
high-water use under a 1 MiB reserved capacity. Other cases record zero arena
high-water use. Every image finalises and memory/allocation gates pass. No
one-frame host API, reset-method or arbitrary-control claim follows.

See [the signal-stateful results](../evidence/xiao-smoke-rnbo-signal-stateful.json)
and [original graphs/reference](../tests/fixtures/smoke/rnbo-signal-stateful/README.md).

## Miscellaneous RNBO codebox APIs

All **22 scenarios pass**, checking **225,280 output values**. The source set
covers bounded safe arithmetic and integer operations, complex tuple outputs,
asymmetric-point interpolation, phase shapes, the Float32 number maximum and
three configured class APIs. Independent references and zero/2e-6 numeric
limits precede output; 13,520 differing words lie within the declared nonzero
limits. The overall result is not bit-identity or full-domain qualification.

Interpolation models explicitly distinguish four-point Lagrange, full-slope
Hermite, half-slope Catmull–Rom and the centered six-point quintic B-spline.
Safe/cast/shift checks avoid undefined overflow and use only their declared
bounded guard cases. `rint` uses a declared nearest/even half-tie policy.
`number_max` is a bare finite Float32 constant, not a time-generator substitute.

`ease` and `easexfade` use separate left/right instances, fixed In_quadratic
enum 7, syncupdate 0 and unit phase. Their selected outputs are pointwise despite
internal history bookkeeping; changing/synchronized modes and resets remain
untested. `xfademul` uses one default two-channel phase/wrap/equal-power instance
for channel 0/1 calls. Other options and general class behavior are not inferred.

Zero automatic preparation warm blocks precede four checked manual warmups and
sixteen timed callbacks. Medians span 37–2,191.5 µs, peak 2,196 µs. `safepow`,
`cubicinterp` and the configured `easexfade` case trigger CPU review; all pass
their output limits. Every image finalises, with zero arena high-water use and
passing memory/allocation gates. Complete callback costs remain separate from
signal/Gen contexts and claim no optimisation gain.

See [the miscellaneous codebox results](../evidence/xiao-smoke-rnbo-codebox-misc.json),
[original programs/reference](../tests/fixtures/smoke/rnbo-codebox-misc/README.md)
and [CPU review queue](cpu-review-backlog.md).

## RNBO codebox filters and default delay resources

All **twelve class-instance scenarios pass**, checking **122,880 output values**
against full twenty-block continuous references. Zero automatic preparation
warm blocks precede four checked manual warmups and sixteen timed callbacks.
Each case spans 5,120 frames without a reset at 256-frame boundaries. This is
still the production fixed-256 ABI, not a one-frame host API or reset-method test.

The sources specify a two-sample delay; two-/three-sample-equivalent comb/allpass
settings; dyadic biquad coefficients; onepole cutoffs 1,000/2,000 Hz and linear
coefficients 0.25/0.5; mean/absolute/RMS windows 8/16; ramp counts 4/8 and 8/4;
and positive-edge/hysteresis triggers. Independent equations and fresh-window
`fsum` references use predeclared zero or 2e-6 numeric limits. The 320 operation
zero-sign differences remain diagnostics; the full batch is not bit-exact.

Delay, comb and allpass each use one left-channel instance with a copied right
input; the other cases use separate left/right instances. That copy lane is
checked under the common case tolerance, with no separately enforced raw-word
or signed-zero observer claim. Clear/reset methods, other coefficients and
delays, changing windows/controls and other surfaces remain unqualified.

Default storage is preserved: the numerical profile is unchanged and the
original delay/average buffers remain **Float64**. A default comb or allpass has
two 65,536-element rings: 1,048,576 payload bytes before metadata, so 1 MiB is
insufficient. An explicit **2 MiB smoke-only caller tier** admits these images;
the ordinary benchmark host still defaults to 1 MiB. The existing SDK limit,
DSP code and defaults are unchanged. The fast build cache's original 4 KiB
control still produces the exact original whole ELF; reused support objects
remain unchanged.

| Authored program | Arena capacity | Observed high-water bytes |
| --- | ---: | ---: |
| Mono delay + copy lane | 2,097,152 | 524,352 |
| Mono comb + copy lane | 2,097,152 | 1,048,704 |
| Mono allpass + copy lane | 2,097,152 | 1,048,704 |
| Each dual mean/absolute/RMS program | 2,097,152 | 705,760 |
| Each of the other six programs | 2,097,152 | 0 |

Capacity is reserved space, not measured consumption. Small active delays and
windows do not shrink the original buffers. Every image finalises, and module/
global memory and allocation gates pass.

Callback medians span 67–982 µs, peak 988 µs. Comb, allpass and all three average
variants trigger CPU review; all five pass their output limits. These are
complete fixture callback costs, with mono-plus-copy and dual-instance contexts
kept explicit. No isolated function cost or performance gain is inferred.

See [the complete filter results](../evidence/xiao-smoke-rnbo-codebox-filters.json),
[the original programs/reference and resource notes](../tests/fixtures/smoke/rnbo-codebox-filters/README.md)
and [CPU review queue](cpu-review-backlog.md).

## RNBO signal ranges, routes, windows and constants

All **37 direct signal scenarios execute: 34 pass and three retain mismatches**,
across 378,880 output checks. They use the actual patcher inlet roles and source
wiring, independently from similarly named Gen or RNBO codebox forms.

| Exact signal form | Retained comparison |
| --- | --- |
| `step~` with threshold 0 | 8,960 outputs differ, maximum error 1, against the unchanged first-input >= threshold reference. |
| `fastpow~` | 9,400 outputs exceed the predeclared 1e-3 ideal-function screen; maximum error 0.23720312118530273. |
| `fastexp~` | 10,240 outputs exceed that screen; maximum error 0.06756162643432617. |

The fast screens are approximation-quality checks, not documented accuracy
guarantees. `cosineinterp~` passes the same 1e-3 screen with maximum error
0.00015687942504882812. Other references use zero numeric tolerance for simple
dyadic/constant operations or 2e-6 for ordinary math. The 1,320 operation
zero-sign differences remain diagnostics; the entire batch is not bit-exact.
No input domain, mathematical convention or limit is changed after execution.

The source set checks edge-first `smoothstep~`, both Cartesian/polar tuple
outputs, fixed conditional/payload routing, window functions, separate constant
aliases and fixed phase/quantization shapes. `quantize~` uses quantum 4/8 with
a declared upward half-tie policy. `t60time~` inputs stay between 0.125 and 0.5,
with results in samples. These observations do not qualify arbitrary controls,
nonfinite inputs or stateful oscillators.

Zero automatic preparation warm blocks precede four checked manual warmups and
sixteen timed callbacks. Medians span 37–7,763 µs, peak 7,764 µs. Six passing
contexts trigger CPU review: `cosineinterp~`, `hann~`, `hamming~`, `blackman~`,
`t60~` and `triangle~`. The `blackman~` median is 7.763 ms against the 5.805 ms
block period. These are complete callback costs; no optimisation is applied.
Every executed image finalises and memory/allocation gates pass. These six
flags precede the five separately listed filter/delay additions.

See [the complete signal results](../evidence/xiao-smoke-rnbo-signal-range.json),
[the original graphs/reference](../tests/fixtures/smoke/rnbo-signal-range/README.md)
and [CPU review queue](cpu-review-backlog.md).

## RNBO codebox continuous-state instances

Of 13 authored source forms covering 12 class names, **eleven execute: ten pass
and one retains a declared capture-phase mismatch**, across 112,640 output
checks. The supplied `history` read/write class source fails C++ compilation
and is not executed. An original autonomous `counter` fixture fails port
validation for its unused declared inputs; the separately authored input-driven
counter program compiles, executes and passes. The latter qualifies the owner
row without turning the earlier fixture rejection into a counter API ban.

| Retained comparison | Observation |
| --- | --- |
| `downsamp.next()` with factors 3/5 | 7,290 outputs differ, maximum error 2, against the fixed first-capture-at-ordinal-0 policy. The first difference is in callback 0, interleaved word 4: actual 0.25 versus expected 0. |

Each accepted source declares independent left/right state instances. Zero
automatic preparation blocks precede four checked manual warmups and sixteen
timed callbacks: **all twenty reference blocks remain continuous**, covering
5,120 frames per case without resetting at 256-frame boundaries. Vectors
deliberately exercise accumulation, downsample factors 3/5, counting/report
windows 7/5 and initial-state transitions across callbacks. The 640 operation zero-sign differences remain
diagnostics; the batch is not bit-exact.

Slide uses explicit rise/fall factors 2/4 and 4/2; DC blocking uses explicit
gains 0.5/0.75. Their references retain ideal history with a fixed 2e-6 absolute
limit. Other checks use zero numeric tolerance. Counter observes only output 0
with unit-valued increments, reset held 0 and limits 7/5. First-capture,
zero-crossing and window-report policies are declared where primary prose is
less specific, and remain unchanged after execution. No reset-method, arbitrary
control, one-frame module-ABI, sample-offset-event or Gen/patcher claim follows.

Callback medians span 54–379.5 µs, peak 380 µs; no CPU-review flag triggers.
Every executed image finalises, with zero arena high-water use and passing
memory/allocation gates. The two rejected source forms have no device output,
callback timing or resource-use observation.

See [the complete stateful results](../evidence/xiao-smoke-rnbo-codebox-stateful.json)
and [the original programs/reference](../tests/fixtures/smoke/rnbo-codebox-stateful/README.md).

## RNBO codebox shaping, windows and integer helpers

All 40 authored scalar forms compile and execute: **38 pass and two retain
small curve-reference exceedances**, across 409,600 output checks. They cover
30 individually authored easing functions, four windows, two interpolators and
four bounded integer helpers. This does not qualify the separate stateful
`ease` class or similarly named Gen/patcher functions.

| Exact codebox call | Retained mismatch |
| --- | --- |
| `ease_in_bounce()` | 320 outputs exceed the fixed 2e-6 limit; maximum error 2.4437904357910156e-6. |
| `ease_out_bounce()` | 320 outputs exceed the same unchanged limit; maximum error 2.4437904357910156e-6. |

Independent models follow the pinned RNBO curve definitions, including
cubic-minus-sine back curves, 6.5π elastic oscillation and the documented bounce
pieces. They do not assume another library's easing convention. The phase set
includes endpoints and Float32 neighbors of piece boundaries. Ordinary curves
use 2e-6; linear interpolation and small integer helpers use zero numeric
tolerance. `cosineinterp` passes its predeclared 1e-3 ideal-cosine screen with
maximum error 0.00015687942504882812; that screen is not an accuracy guarantee.
Integer overflow and zero divisors are excluded. No limit is fitted to output.
The overall batch is not bit-exact.

Zero automatic preparation warm blocks precede four checked manual warmups and
sixteen timed callbacks. Medians span 45–8,515 µs, peak 8,519 µs. **Eighteen
contexts trigger CPU review, and all eighteen pass their output limits.**
`blackman` has an 8.515 ms median; the three elastic variants measure 6.139,
6.312 and 6.493 ms, each above the 5.805 ms block period. These are complete
stereo callback costs, not isolated function costs or measured savings.
Every image finalises, with zero arena high-water use and passing memory and
allocation gates. The CPU queue reaches 76; the stateful batch adds no flags.

See [the complete shaping results](../evidence/xiao-smoke-rnbo-codebox-shaping.json),
[the original programs/reference](../tests/fixtures/smoke/rnbo-codebox-shaping/README.md)
and [CPU review queue](cpu-review-backlog.md).

## RNBO codebox range, routing and conversion forms

The 47 authored source forms produce **40 executed scenarios: 36 pass and four
retain comparison mismatches**, across 409,600 output checks. The initial 45
direct-call attempts remain intact. Two separate, valid converter programs use
`@state` instances and `.next(input, 440)`; they do not replace rejected calls.

| Exact codebox call | Retained comparison outcome |
| --- | --- |
| `step()` | 9,520 outputs differ, maximum error 1, against the declared first-input >= second-input reference. |
| `fastpow()` | 9,400 outputs exceed the 1e-3 ideal-math screen; maximum error 0.23720312118530273. |
| `fastexp()` | 10,240 outputs exceed that screen; maximum error 0.06756162643432617. |
| `fasttan()` | 8,320 outputs exceed that screen; maximum error 0.002815753221511841. |

Fast screens are predeclared approximation-quality checks, not documented
accuracy guarantees or universal malfunction verdicts. Other independent
references cover fixed ranges, extrapolating scale, edge-first smoothstep,
Cartesian/polar tuples, boolean routing, payload comparisons and practical
unit conversions. Basic dyadic checks use zero numeric tolerance, ordinary
math 2e-6, unit conversions 5e-4 and fast screens 1e-3. Domains and limits remain
unchanged after output. The 2,600 operation zero-sign differences are separate
diagnostics; the executed math batch is not bit-exact.

| Nonexecuted source form | Retained outcome |
| --- | --- |
| Direct `rdiv`, `rmod`, `rsub`, `rminus` calls | C++ compilation failed for each closed source form. No device output or cost is claimed. |
| Direct `switch(...)` call | Frontend rejection of this reserved call form; not compiled or executed. |
| Direct `mtof(...)`, `ftom(...)` calls | Frontend rejection because these require state instances. Their separately authored `.next()` programs both pass. |

These are source-form outcomes, not universal object bans. `mtof` and `ftom`
owner entries are qualified only by their passing instance programs, with the
direct-call rejections retained as known gaps. The default `ftom` reference is
integer-rounded at the selected notes and quarter tones; no continuous-pitch,
half-note-tie, reset or other-member claim follows.

Zero automatic preparation warm blocks precede four checked manual warmups and
sixteen timed callbacks. Medians span 48–14,663 µs, peak 14,664 µs. Six complete
callback contexts trigger review: `log2f`, `atodb`, `dbtoa`, `t60`, and the
`mtof`/`ftom` instance forms. The `dbtoa` median is 14.663 ms against a 5.805 ms
block period; optimisation is queued, not performed.

All executed images finalise and memory/allocation gates pass. Each module
reserves a 1 MiB arena; only `mtof` records use, at 262,256 bytes high-water
including its unchanged 262,144-byte lookup payload. All other cases, including
`ftom`, record zero arena high-water use. Reserved capacity is not consumption.

See [the complete codebox range results](../evidence/xiao-smoke-rnbo-codebox-range.json),
[the original programs/reference](../tests/fixtures/smoke/rnbo-codebox-range/README.md)
and [the CPU review queue](cpu-review-backlog.md).

## Gen named constants and configuration values

All **32 independently authored bare-value scenarios pass**, checking **327,680
output words bit-for-bit**. The batch covers 28 mathematical constant spellings
and four configuration names: `samplerate`/`SAMPLERATE` and
`vectorsize`/`VECTORSIZE`. The latter report 44,100 Hz and 256 frames in this
audio configuration. Both output lanes hold the selected value; the declared
FX inputs are unused. Every alias has its own source and execution record.

The reference independently computes each mathematical value and rounds it
once to binary32. Zero automatic preparation warm blocks precede four checked
manual warmups and sixteen timed callbacks. All medians are 37 µs, peak 42 µs;
no CPU-review flag triggers. Every image finalises, with zero arena high-water
use and passing memory/allocation gates. There is no optimisation comparison.
These observations cover the supplied bare-value syntax and configuration,
not zero-argument calls, FFT/voice/elapsed contexts, other block sizes or matching
RNBO names. They add no entries to the RNBO main coverage table.

See [the complete Gen constant results](../evidence/xiao-smoke-gen-constants.json)
and [the authored sources/reference](../tests/fixtures/smoke/gen-constants/README.md).

## Gen range, routing and conversion calls

Of 30 authored GenExpr forms, **29 compile and execute on XIAO: 25 pass and four
exceed their predeclared references**, across 296,960 output checks. The tuple
`gate(in1, in2, choices=2)` form is rejected by the frontend; it is not compiled
or executed. This describes that supplied syntax, not all uses of Gen `gate`.

| Exact Gen call | Retained comparison outcome |
| --- | --- |
| `fastpow()` | 9,400 outputs exceed the 1e-3 ideal-math screen; maximum error 0.23720312118530273. |
| `fastexp()` | 10,240 outputs exceed the 1e-3 ideal-math screen; maximum error 0.06756162643432617. |
| `fasttan()` | 8,320 outputs exceed the 1e-3 ideal-math screen; maximum error 0.002815753221511841. |
| `ftom()` | 4,480 outputs exceed the continuous-pitch reference's 5e-4 limit; maximum error 0.25. The tested quarter-tone points produce integer-rounded results. |

The fast-function limits are deliberately chosen approximation-quality screens,
not documented accuracy guarantees or universal malfunction verdicts. All input
domains and limits were fixed before execution and remain unchanged. Other
checks cover finite range endpoints, integer selector choices, Cartesian/polar
tuples, interpolation, practical pitch/time points and finite-only NaN helpers.
They do not establish fractional routing choices or nonfinite handling. The
2,600 operation zero-sign differences remain diagnostics, not bit-identity.

Each case uses zero automatic preparation warm blocks, four checked manual
warmups and sixteen timed callbacks. Medians span 42–14,663 µs, peak 14,664 µs.
Six cases trigger CPU review: `mtof`, `ftom`, `atodb`, `dbtoa`, `t60` and
`triangle`. The stereo `dbtoa` callback's 14.663 ms median exceeds the 5.805 ms
block period. These costs include the complete callback, not an isolated opcode.

All executed images finalise and module/global memory and allocation gates
pass. The 1 MiB arena is reserved capacity, not measured consumption: only
`mtof` uses it, with a 262,256-byte high-water mark including its unchanged
262,144-byte lookup payload. Every other case, including `ftom`, records zero
arena high-water use. The earlier unflashed 4 KiB module cohort is retained;
the larger capacity was selected before this run without changing DSP sources,
inputs or references.

See [the complete Gen range results](../evidence/xiao-smoke-gen-range.json),
[the authored programs/reference](../tests/fixtures/smoke/gen-range/README.md),
[the separate Gen record](gen-qualification.md) and [CPU review queue](cpu-review-backlog.md).

## RNBO codebox numeric and mathematical calls

All 43 authored calls export, compile and execute on XIAO. **40 pass their
predeclared references; three retain numerical mismatches**, across 440,320
output checks. All images finalise and memory/allocation gates pass. These are
RNBO codebox calls, independently tested from Gen and patcher-object names.

| Exact codebox call | Retained mismatch |
| --- | --- |
| `round()` | 280 outputs differ, maximum error 1, against the declared nearest-integer/ties-away reference. |
| `isdenorm()` | 9,960 outputs differ, maximum error 2,147,483,648; observations resemble identity rather than the documented 0/1 predicate. |
| `fixdenorm()` | 1,680 outputs differ; subnormals remain, maximum error 1.1754942106924411e-38. |

The basic-function corpus includes signed zeros, subnormals, halfway neighbors
and signed 32-bit-safe conversion limits. Standard mathematical inputs stay in
their listed valid domains. Basic checks use zero numeric tolerance; ordinary
math uses a fixed 2e-6 absolute limit against the once-Float32-rounded ideal.
The 2,780 operation zero-sign differences remain separate diagnostics. Finite
`isnan`/`fixnan` inputs do not establish NaN handling. No reference was changed
to fit output, and no tolerance was widened after the run.

There are zero automatic preparation warm blocks, then four checked valid-input
manual warmups and sixteen timed callbacks. Callback medians span 42.5–7,499 µs,
with peak 7,504 µs. **Fourteen cases trigger CPU review**; all fourteen pass their
output limits. The stereo `exp2()` fixture's 7.499 ms median exceeds the 5.805 ms
block period. These are complete callback costs, not isolated function costs
or optimisation gains; investigation remains queued while coverage proceeds.

See [the complete results](../evidence/xiao-smoke-rnbo-codebox-numeric.json),
[the original programs/reference](../tests/fixtures/smoke/rnbo-codebox-numeric/README.md)
and [the CPU review queue](cpu-review-backlog.md).

## RNBO codebox arithmetic and named constants

Two RNBO codebox batches execute **83 scenarios, all passing their declared
checks**, with **849,920 output comparisons**. Two other authored forms are
rejected before execution and remain unverified. These are RNBO `codebox~`
programs, with their own source/program/module bindings; GenExpr and patcher
object results do not transfer to them.

The arithmetic/logic batch executes 43 forms and checks 440,320 values. Nonzero
numeric outputs match exactly. Its 2,880 allowed operation zero-sign differences
are retained, so this is not a bit-identity claim. The independent reference uses
finite dyadic inputs, with nonzero powers of two on both lanes for division and
signed remainder. Unary forms act per lane and binary forms reverse operands.

| Rejected source form | Retained outcome |
| --- | --- |
| Named `mod(a,b)` call | Generated C++ failed on an unavailable `safemod` reference; not executed. The separately authored `%` infix form passes. |
| `^^` infix expression | Frontend rejection; not compiled or executed. The separately authored `xor(a,b)` call passes. |

Those failures describe the supplied closed syntax forms, not universal
unsupported-object verdicts. No timing, heap or hardware output claim is made
for either rejection.

The named-value constant batch executes 40 exact spellings, and **all 409,600
output words match bit-for-bit**. Thirty mathematical constant spellings and
ten ASCII digit constants are independently authored. `CHAR_0` through `CHAR_9`
are numeric character codes 48–57, not digit values 0–9. Both output lanes hold
the chosen constant; declared FX inputs are unused. This qualifies the listed
named-value syntax, without automatically qualifying zero-argument calls,
other aliases or dynamic clock/query operations.

Both batches use four automatic zero-input preparation blocks, four checked
manual warmups and sixteen checked timed callbacks at 44.1 kHz/256 frames.
Arithmetic/logic medians range from 42 to 274 µs, peak 279 µs. All constant
medians are 37 µs, peak 42 µs. Every executed image finalises and memory/allocation
gates pass. Neither batch triggers CPU review; no optimisation gain or isolated
operation cost is claimed. The production ABI still uses complete 256-frame
calls; these observations do not establish one-frame host calls.

See [arithmetic/logic results](../evidence/xiao-smoke-rnbo-codebox.json),
[constant results](../evidence/xiao-smoke-rnbo-codebox-constants.json),
[the original codebox programs/reference](../tests/fixtures/smoke/rnbo-codebox/README.md)
and [named-value sources/reference](../tests/fixtures/smoke/rnbo-codebox-constants/README.md).

## Additional events and signal constants

Two further XIAO batches execute **61 scenarios: 56 pass and five retain output
mismatches**, checking **624,640 output values** and 840 actual parameter updates
with readbacks. All 61 images finalise and memory/allocation gates pass. Neither
batch triggers a CPU-review flag; no optimisation gain is claimed. These add 60
mapped exact spellings: `sig~` already had composition coverage and now has a
separate initial-value observation.

The extra event batch executes 40 exact spellings: 35 pass and five fail their
unchanged zero-tolerance references:

| Exact event form | Retained observation |
| --- | --- |
| `isdenorm` | 4,608 mismatches; maximum error 8; observations resemble pass-through rather than the documented 0/1 predicate. |
| `fixdenorm` | 768 mismatches; signed subnormals remain; maximum error 1.1754942106924411e-38. |
| `rmod`, `!%` | 512 mismatches each; maximum 5.960464477539063e-8, one binary32 ULP near 0.5. The exact gate is retained. |
| `step` | 4,352 mismatches; maximum error 1 against the documented first-input ≥ second-input ordering. |

These are the supplied hot numeric-message scenarios, with one linear/unstepped
`drive` parameter, 21 ordered actual-value updates per case, duplicate-call
ordering, unchanged resends and holds. Zero automatic preparation warmups precede
four checked manual warmups and sixteen timed callbacks. The left result is held
through `sig~`; the right input is raw-bit exact across 204,800 pilot values,
including zero signs and subnormals. The 256 permitted left zero-sign differences
remain diagnostics; strict right-zero violations are zero.

Reverse division/remainder actions exclude zero divisors. `isnan`/`fixnan`
cover finite inputs only. Integer/floating stores cover hot numeric input/output,
without bang/cold-store qualification. In this namespace `constant` is an alias
of the floating-number store, not an autonomous signal constant. No signal,
Gen or unexecuted alias result transfers to these event names.

Callback medians are 75–76.5 µs, peak 81 µs, primarily the held-signal/pilot work.
The 840 event API observations total 6,419 µs, with individual values 5–43 µs;
setter/routing timing excludes readback/logging and is separate from callback
timing. These are observed scenario costs, not isolated event-opcode costs or
worst-case latency bounds. No within-block scheduling is established.

The constant batch executes 21 exact spellings; **all 215,040 output words match
bit-for-bit**. It covers mathematical constants and aliases, explicit
`sig~` initial values 0.25/-0.5, `samplerate~` at 44,100 Hz and `vectorsize~` at 256.
FX inputs are declared but unused. Four automatic zero-input preparation blocks
precede four checked manual warmups and sixteen timed callbacks. Medians are
37–50 µs and the largest observed peak is 54 µs. Message updates, impulses, other
configurations and arbitrary initial values remain untested.

See the [extra-event results](../evidence/xiao-smoke-rnbo-events-extra.json),
[constant results](../evidence/xiao-smoke-rnbo-constants.json),
[original event sources/reference](../tests/fixtures/smoke/rnbo-events-extra/README.md)
and [constant sources/reference](../tests/fixtures/smoke/rnbo-constants/README.md).

## RNBO parameter-driven event batch

**All 35 exact event spellings pass on XIAO**, with 735 ordered parameter
updates/readbacks and **358,400 output checks**. No parser/compiler failures,
processing-time CPU flags or memory/allocation failures occur. These are
non-tilde event objects; signal and Gen results do not transfer to them.

| Exact event form | Result | Callback median µs | Total 21 event calls µs | Event peak µs |
| --- | --- | ---: | ---: | ---: |
| `abs` | Pass | 76.0 | 157 | 34 |
| `neg` | Pass | 75.0 | 161 | 35 |
| `floor` | Pass | 76.0 | 160 | 35 |
| `ceil` | Pass | 76.0 | 157 | 34 |
| `trunc` | Pass | 76.0 | 156 | 35 |
| `round` | Pass | 76.0 | 203 | 44 |
| `fract` | Pass | 76.0 | 162 | 35 |
| `sign` | Pass | 75.0 | 159 | 35 |
| `boolnum` | Pass | 76.0 | 167 | 34 |
| `not` | Pass | 76.0 | 164 | 34 |
| `!` | Pass | 76.0 | 164 | 34 |
| `add` | Pass | 76.0 | 171 | 33 |
| `+` | Pass | 76.0 | 173 | 33 |
| `sub` | Pass | 76.0 | 168 | 33 |
| `-` | Pass | 76.0 | 169 | 33 |
| `mul` | Pass | 76.0 | 171 | 37 |
| `*` | Pass | 76.0 | 169 | 33 |
| `div` | Pass | 76.0 | 166 | 35 |
| `/` | Pass | 76.0 | 161 | 35 |
| `mod` | Pass | 75.5 | 156 | 31 |
| `%` | Pass | 76.0 | 157 | 31 |
| `minimum` | Pass | 75.0 | 165 | 34 |
| `min` | Pass | 76.0 | 161 | 34 |
| `maximum` | Pass | 75.5 | 164 | 34 |
| `max` | Pass | 75.0 | 162 | 35 |
| `eq` | Pass | 75.5 | 157 | 35 |
| `==` | Pass | 75.0 | 157 | 35 |
| `gt` | Pass | 76.0 | 156 | 34 |
| `>` | Pass | 75.5 | 156 | 34 |
| `lt` | Pass | 76.0 | 156 | 34 |
| `<` | Pass | 76.0 | 158 | 34 |
| `and` | Pass | 76.0 | 162 | 34 |
| `&&` | Pass | 75.5 | 157 | 34 |
| `or` | Pass | 76.0 | 154 | 36 |
| `xor` | Pass | 75.0 | 159 | 36 |

Each original patch has one ordinary numeric `drive` parameter, initially 0,
with range [-8,8], exponent 1 and no steps. It drives the event object's hot
inlet; its value output drives `sig~` and the left output. Binary operands are
literal 2, except `or 0` so both Boolean outcomes occur. `round 2` uses base 2.
Minimum/maximum observe value outlet 0 only; their index outlets are untested.
The independent right input goes directly to the right output.

The 21 authored updates include signed/fractional values, range endpoints,
unchanged resends, holds, and multiple ordered updates before one callback.
Per-model sequences make last-write ordering observable. Stable parameter IDs
are resolved against each loaded runtime schema; actual/normalized readbacks
match the independent linear mapping. All twenty callbacks have their own
expected blocks, including four checked manual warmups and sixteen timed calls.
There is no automatic zero-input preparation processing.

Every nonzero numeric left value matches exactly. The 2,816 left zero-sign
word differences are retained as allowed numeric-zero diagnostics. The right
observer is **raw-bit exact** over all 179,200 values, including both zero signs,
subnormal values and finite extremes; strict zero-sign failures are counted
separately and remain zero. Parameter readbacks allow only numeric ±0
equivalence while preserving their raw words in the result.

Processing medians range from 75 to 76 µs per stereo 256-frame callback. Event
API calls are measured separately, before processing and without readback/logging
inside their timer: 154–203 µs total per 21 updates, individual observations 5–44 µs.
These event times include the SDK setter and downstream routing, not an isolated
arithmetic instruction. The callback cost mostly represents held-signal/pilot
processing; it is not an event-operator speed comparison. No optimisation gain
or peak-latency guarantee is claimed.

The existing API dispatches at `RNBO::TimeNow` between complete 256-frame calls.
This run establishes the supplied **block-boundary** changes and ordering,
not within-block timestamps, nonlinear/stepped parameter normalization, arbitrary
cold operands, multiple-control interactions or counter/reset semantics.
The fast compiler now admits 0–32 ordinary numeric parameters; this hardware
batch exercises one control per fixture, not the full count limit. No production
SDK or event ABI was changed.

To retain all checks in one upload, exact repeated 512-word reference blocks
are shared: 700 logical callback references use 36 stored blocks. Each case
keeps its full stream hash and ordered block indices. An initial unflashed
build's expanded 8.5MiB report exceeded the existing 8 MiB preflight limit; the
uploader stopped before writing. The revised report is 1,327,267 bytes, with
the generated case data byte-identical except for the plan-identity string.
The size guard and numerical/word checks were not relaxed. Both build versions
remain saved locally; only the compact-report firmware was uploaded.

See [the complete event/readback result](../evidence/xiao-smoke-rnbo-events.json)
and [the original patches and independent reference](../tests/fixtures/smoke/rnbo-events/README.md).

## RNBO functions and conversions batch

**35 forms execute on XIAO: 34 pass their declared checks, and `fasttan~`
exceeds the chosen ideal-reference limit.** All export and compile; eleven
cases trigger CPU review. Memory/allocation gates pass and all images finalise.

| Exact form | Short result | Median µs | Peak µs | CPU review |
| --- | --- | ---: | ---: | --- |
| `sin~` | Pass | 281.0 | 286 | No flag |
| `cos~` | Pass | 285.5 | 290 | No flag |
| `tan~` | Pass | 419.5 | 424 | No flag |
| `tanh~` | Pass | 645.0 | 646 | Queued |
| `asin~` | Pass | 532.0 | 533 | No flag |
| `acos~` | Pass | 485.0 | 487 | No flag |
| `atan~` | Pass | 344.0 | 347 | No flag |
| `atan2~` | Pass | 681.0 | 682 | Queued |
| `sinh~` | Pass | 694.0 | 695 | Queued |
| `cosh~` | Pass | 643.5 | 646 | Queued |
| `asinh~` | Pass | 756.5 | 757 | Queued |
| `acosh~` | Pass | 828.0 | 828 | Queued |
| `atanh~` | Pass | 772.0 | 772 | Queued |
| `hypot~` | Pass | 224.0 | 229 | No flag |
| `degrees~` | Pass | 50.0 | 50 | No flag |
| `radians~` | Pass | 50.0 | 54 | No flag |
| `radtodeg~` | Pass | 37.0 | 37 | No flag |
| `RADTODEG~` | Pass | 37.0 | 42 | No flag |
| `degtorad~` | Pass | 37.0 | 41 | No flag |
| `DEGTORAD~` | Pass | 37.0 | 42 | No flag |
| `mtof~` | Pass | 2392.0 | 2397 | Queued |
| `ftom~` | Pass | 667.5 | 668 | Queued |
| `atodb~` | Pass | 4875.0 | 4876 | Queued |
| `dbtoa~` | Pass | 14659.0 | 14660 | Queued |
| `mstosamps~` | Pass | 349.0 | 351 | No flag |
| `sampstoms~` | Pass | 154.0 | 159 | No flag |
| `hztoms~` | Pass | 157.0 | 157 | No flag |
| `mstohz~` | Pass | 157.0 | 161 | No flag |
| `hztosamps~` | Pass | 142.0 | 147 | No flag |
| `sampstohz~` | Pass | 142.0 | 146 | No flag |
| `fastsin~` | Pass | 147.0 | 148 | No flag |
| `fastcos~` | Pass | 158.0 | 161 | No flag |
| `fasttan~` | Exceeds declared test limit | 306.0 | 311 | No flag |
| `cosT8~` | Pass | 492.0 | 495 | No flag |
| `cosT8safe~` | Pass | 429.0 | 434 | No flag |

Each fixture checks 10,240 output values over twenty callbacks, totalling
**358,400 output checks**. Sixteen callbacks supply timing. Binary `atan2~` and
`hypot~` reverse operands across the two lanes. The four `radtodeg~`/`degtorad~`
spellings are zero-input constants (180/π and π/180), with declared but unused
FX inputs; they are not converters. Constants and integer-rounded default
`ftom~` outputs compare exactly. The aliases have separate source/device records.

Limits and domains were chosen before execution. Ordinary mathematical cases
use `2e-6` absolute error. MIDI conversion includes practical notes 36–84,
quarter tones and A4=440 Hz, with a `5e-4` Hz limit for `mtof~`. Time/frequency
conversions include ordinary block/sample counts, milliseconds and musical
frequencies, using `5e-4` in the output units. Decibels use unity=0 dB.
The fast sine/cosine/tangent cases use a declared `1e-3` ideal-math threshold;
first-party prose does not promise that numerical accuracy.

`fasttan~` returns finite values, but its maximum deviation from `tan(x)` on
these inputs is about 0.01409, above the selected 0.001 threshold. This is a
retained approximation-quality result, not a claim that the object universally
malfunctions or violates a documented accuracy guarantee. Fast sine/cosine
stay within their same predeclared threshold. Taylor-cosine checks use the
listed small-angle and small-after-wrap domains, not all possible angles.

The default converter resources are preserved. The fast compiler has an
explicit one-MiB arena tier, changing only the wrapper's advertised maximum;
its original four-KiB cache control still reproduces the entire reference ELF.
Each fixture reserves 1,048,576 arena bytes for this run, which does not mean
it consumes that amount. `mtof~` peaks at **262,416 bytes** (one shared 65,536
Float32 lookup payload of 262,144 bytes, plus overhead); `ftom~` peaks at
**160 bytes**. The other 33 cases use zero arena bytes in this scenario.
These measurements do not establish minimum viable arena sizes for all modes.
All resource initialization precedes audio processing, with no table omission,
precision-profile change or DSP optimisation. Zero automatic audio warm-up
blocks are followed by four checked valid-domain warmups and sixteen timed calls.

Eleven costs are retained in [the CPU-review queue](cpu-review-backlog.md).
The `dbtoa~` two-instance stereo fixture takes 14.659 ms median, about 2.53 times
the 5.805 ms block period. `atodb~` takes 4.875 ms and `mtof~` 2.392 ms. These
are whole-fixture costs, not isolated node timings or optimisation gains.
Existing AMOLED optimisation percentages remain separate from these XIAO
baseline observations.

See [the compact results](../evidence/xiao-smoke-rnbo-functions.json) and
[the original sources/reference](../tests/fixtures/smoke/rnbo-functions/README.md).

## Gen stateful and per-sample batch

**All 12 programs pass on XIAO**, covering nine exact GenExpr spellings:
`delta`, `change`, `latch`, `dcblock`, `sah`, `slide`, `accum`, `plusequals` and
`counter`. Every program exports, compiles and executes; no CPU-review flags
trigger. Module/global memory checks pass and all twelve images finalise.

| Program / left-lane form | Result | Median µs | Peak µs | Maximum error |
| --- | --- | ---: | ---: | ---: |
| `delta(in1)` | Pass | 50.0 | 55 | 0 |
| `change(in1)` | Pass | 67.0 | 68 | 0 |
| `latch(in1, in2)` | Pass | 56.0 | 56 | 0 |
| `dcblock(in1)` | Pass | 551.0 | 552 | 1.55e-06 |
| `sah(in1, in2)` | Pass | 70.0 | 75 | 0 |
| `sah(in1, in2, 0.5)` | Pass | 72.0 | 77 | 0 |
| `sah(in1, in2, in1)` | Pass | 67.0 | 71 | 0 |
| `slide(in1, 2, 4)` | Pass | 374.0 | 378 | 5.96e-08 |
| `slide(in1, 4, 2)` | Pass | 373.0 | 378 | 5.96e-08 |
| `accum(in1, 0)` | Pass | 52.0 | 56 | 0 |
| `plusequals(in1, 0)` | Pass | 52.0 | 57 | 0 |
| `counter(1, 0, 7); right maximum 5` | Pass | 63.0 | 67 | 0 |

Each program processes **5,120 continuous frames per channel**: four checked
manual warm-up callbacks followed by sixteen checked timed callbacks, with no
state reset between them. This is **122,880 output checks** across the batch.
The repeated input vector has an independently calculated output stream for
all twenty callbacks; repeating only the first expected block is insufficient.
Each stream is bound by its own little-endian word hash, and mismatch records
identify both the callback and in-block sample position.

The input design distinguishes a reset at the 256-frame boundary from continuous
state for delta/change, latch/sample-hold, accumulators and counters. Late held
values differ from the next block's first input; accumulator sums have nonzero
block totals; counter periods 7 and 5 do not divide 256. The counter matches the
predeclared increment-before-output sequence in this count-output-only test.
`accum` and alias `plusequals` have separate original programs and device records.

Nine programs use exact numerical comparisons and have **zero raw-word
differences**. DCblock and both slide modes use a predeclared absolute `2e-6`
limit against ideal Float64 mathematical state, rounded to Float32 outputs.
Their raw differences remain visible: 10,197 words for dcblock and 4,467/5,737
for slide. Maximum errors are about 1.55e-6 and 5.96e-8 respectively; these are
bounded-accuracy passes rather than exact-bit claims. The reference's Float64
state is an independent mathematical model, not a change to target DSP storage.

The run has zero automatic zero-input preparation blocks; its fresh-state epoch
and all twenty expected blocks are recorded before execution. Median complete
stereo callbacks range from 50 to 551 µs, with peak 552 µs. DCblock is the
highest cost here at about 9.49% of the 5.805 ms block period, below the existing
CPU-review threshold. No optimisation or percentage improvement is claimed.

These results validate the listed per-sample state updates inside fixed
256-frame callbacks, including the supplied cross-block histories. They do not
exercise one-frame host calls, sample-offset events, nonzero initial attributes,
reset modes, counter carry outputs, arbitrary smoothing rates or all stateful
Gen objects. Those remain part of the full goal.

See [the compact stateful result](../evidence/xiao-smoke-gen-stateful.json) and
[the original programs and reference](../tests/fixtures/smoke/gen-stateful/README.md).

## Gen mathematical batch

There are **34 separately authored GenExpr forms: 27 pass on XIAO, four fail
C++ compilation, and three are rejected by the frontend parser**. Thirteen
executed forms trigger CPU review. The run completes all module/global memory
checks and leaves the quiet test firmware installed.

| Exact form | Short hardware result | Median µs | Peak µs | CPU review |
| --- | --- | ---: | ---: | --- |
| `div(in1, in2)` | Pass | 159.0 | 163 | No flag |
| `in1 / in2` | Pass | 159.0 | 159 | No flag |
| `in1 % in2` | Pass | 275.0 | 279 | No flag |
| `sqrt(in1)` | Pass | 199.0 | 203 | No flag |
| `exp(in1)` | Pass | 486.0 | 490 | No flag |
| `exp2(in1)` | Pass | 7499.0 | 7503 | Queued |
| `log(in1)` | Pass | 3684.0 | 3685 | Queued |
| `ln(in1)` | Pass | 3684.0 | 3685 | Queued |
| `log2(in1)` | Pass | 4732.0 | 4733 | Queued |
| `log10(in1)` | Pass | 4297.0 | 4302 | Queued |
| `pow(in1, in2)` | Pass | 1135.0 | 1135 | Queued |
| `sin(in1)` | Pass | 284.0 | 289 | No flag |
| `cos(in1)` | Pass | 289.0 | 294 | No flag |
| `tan(in1)` | Pass | 423.0 | 428 | No flag |
| `tanh(in1)` | Pass | 649.0 | 649 | Queued |
| `asin(in1)` | Pass | 536.0 | 537 | No flag |
| `acos(in1)` | Pass | 491.0 | 492 | No flag |
| `atan(in1)` | Pass | 345.0 | 349 | No flag |
| `atan2(in1, in2)` | Pass | 673.5 | 674 | Queued |
| `sinh(in1)` | Pass | 697.0 | 698 | Queued |
| `cosh(in1)` | Pass | 649.0 | 650 | Queued |
| `asinh(in1)` | Pass | 760.0 | 760 | Queued |
| `acosh(in1)` | Pass | 831.0 | 831 | Queued |
| `atanh(in1)` | Pass | 775.0 | 776 | Queued |
| `hypot(in1, in2)` | Pass | 205.0 | 210 | No flag |
| `degrees(in1)` | Pass | 45.0 | 45 | No flag |
| `radians(in1)` | Pass | 45.0 | 49 | No flag |

The seven unexecuted forms stay in the source catalog and failure records:

| Form | Rejected at | Observed reason |
| --- | --- | --- |
| `in1 !/ in2` | GenExpr parser | Unexpected `!` token |
| `in1 !% in2` | GenExpr parser | Unexpected `!` token |
| `in1 !- in2` | GenExpr parser | Unexpected `!` token |
| `rdiv(in1, in2)` | Target C++ compiler | Ambiguous emitted `div` call |
| `mod(in1, in2)` | Target C++ compiler | Undeclared emitted `safemod` call |
| `rmod(in1, in2)` | Target C++ compiler | Undeclared emitted `safemod` call |
| `rsub(in1, in2)` | Target C++ compiler | Undeclared emitted `sub` call |

Registry membership alone does not prove parser/compiler support. These are
retained support gaps, without fallback expressions or DSP fixes. In particular,
the successful `%` expression does not qualify the rejected `mod()` call.
RNBO signal-object results remain separate from these GenExpr outcomes.

The 27 loaded forms check **276,480 output values**. `div()`, `/` and `%` use
exact numerical comparison; the other 24 forms use the predeclared absolute
limit `2e-6` against independently computed, once-binary32-rounded references.
Raw differing words remain recorded even when within that limit. The largest
observed error is about 4.77e-7 for `degrees`; these approximate passes are not
claims of exact-bit equality. Both channels and reversed binary operand orders
are exercised using per-model bounded finite input vectors.

This batch uses zero automatic zero-input preparation blocks and four checked
manual warmups with each case's valid-domain vector, then sixteen timed calls.
That configuration is recorded in both the plan and device log; it avoids
feeding a zero pre-roll to functions such as `acosh`, whose real domain starts
at 1. Default zero-preroll behaviour is not qualified by this batch. All calls
remain fixed at 256 frames, 44.1 kHz; single-sample and stateful-feedback coverage
remains limited to the separately documented History tests.

`exp2` takes 7.499 ms median in this two-instance stereo fixture, exceeding the
5.805 ms block period. The thirteen [CPU-review entries](cpu-review-backlog.md)
are retained for future optimisation. Timings are whole-graph absolute costs,
with no optimisation gain or real-time audio headroom claim.

See [the compact device/stage results](../evidence/xiao-smoke-gen-math.json) and
[the original programs and independent reference](../tests/fixtures/smoke/gen-math/README.md).

## RNBO numeric and maths batch

One upload executes **33 exact RNBO signal forms: 30 pass, three have output
mismatches, and eight trigger CPU review**. All compile. The final run completes
all module and global memory checks, and leaves the quiet firmware installed.

| Exact form | Short hardware result | Median µs | Peak µs | CPU review |
| --- | --- | ---: | ---: | --- |
| `div~` | Pass | 164.0 | 168 | No flag |
| `/~` | Pass | 164.0 | 168 | No flag |
| `rdiv~` | Pass | 164.0 | 169 | No flag |
| `!/~` | Pass | 164.0 | 169 | No flag |
| `mod~` | Pass | 288.0 | 293 | No flag |
| `%~` | Pass | 288.5 | 293 | No flag |
| `rmod~` | Pass | 288.0 | 293 | No flag |
| `!%~` | Pass | 288.0 | 293 | No flag |
| `floor~` | Pass | 125.0 | 129 | No flag |
| `ceil~` | Pass | 123.0 | 128 | No flag |
| `trunc~` | Pass | 52.0 | 57 | No flag |
| `round~` | Output mismatch | 172.0 | 177 | No flag |
| `fract~` | Pass | 110.0 | 115 | No flag |
| `sign~` | Pass | 56.0 | 61 | No flag |
| `isnan~` | Pass | 52.0 | 57 | No flag |
| `fixnan~` | Pass | 46.0 | 50 | No flag |
| `isdenorm~` | Output mismatch | 41.0 | 46 | No flag |
| `fixdenorm~` | Output mismatch | 41.0 | 46 | No flag |
| `intnum~` | Pass | 52.0 | 56 | No flag |
| `int~` | Pass | 52.0 | 56 | No flag |
| `i~` | Pass | 52.0 | 57 | No flag |
| `sqrt~` | Pass (approximate) | 197.0 | 201 | No flag |
| `cbrt~` | Pass (approximate) | 430.0 | 435 | No flag |
| `exp~` | Pass (approximate) | 483.0 | 487 | No flag |
| `exp2~` | Pass (approximate) | 7494.0 | 7498 | Queued |
| `expm1~` | Pass (approximate) | 418.0 | 423 | No flag |
| `log~` | Pass (approximate) | 3681.0 | 3682 | Queued |
| `ln~` | Pass (approximate) | 3680.5 | 3682 | Queued |
| `log2~` | Pass (approximate) | 4729.0 | 4730 | Queued |
| `log2f~` | Pass (approximate) | 4729.0 | 4730 | Queued |
| `log10~` | Pass (approximate) | 4294.0 | 4299 | Queued |
| `log1p~` | Pass (approximate) | 3979.0 | 3979 | Queued |
| `pow~` | Pass (approximate) | 1141.0 | 1141 | Queued |

Each form checks 10,240 output values over twenty callbacks, for **337,920
output checks**. Sixteen callbacks provide the timings above. Cases have their
own predeclared input vectors: division/remainder use nonzero operands in both
lanes; logarithms, roots, exponentials and powers use bounded valid domains.
Basic functions use a 77-word finite edge set, including subnormal signs,
half-way neighbours and safe signed-32-bit conversion endpoints.

Basic functions use exact numerical comparison with separate zero-sign
counts. Roots/exponentials/logarithms/powers use an absolute error limit of
`2e-6` (stored as binary32) against independently computed, once-rounded
mathematical outputs. Raw differences remain visible: `expm1~` has 640 and
`pow~` has 400 differing output words, all within that predeclared limit; their
largest errors are about 1.19e-7 and 2.38e-7. This is not an exact-bit pass for
those two functions. No comparison limit was changed after device execution.

Retained discrepancies:

- `round~` outputs 1 for input `0x3effffff` (just below 0.5), where the declared
  nearest-integer, ties-away reference expects 0. Its short object prose does
  not define every tie rule; this witness is below the tie itself.
- `isdenorm~` returns a normal input value such as 4,194,304 instead of predicate 0.
- `fixdenorm~` retains the smallest subnormal instead of replacing it with zero.

The `fract~` pass uses the explicitly selected signed-fraction convention.
`isnan~` and `fixnan~` use finite inputs only; NaN/infinity handling is untested.
The denormal discrepancies are consistent with the currently disabled denormal
handling already seen in Gen; no runtime or DSP adapter was changed here.

The eight CPU flags are retained in [the review queue](cpu-review-backlog.md).
The `exp2~` two-instance stereo fixture takes 7.494 ms median, exceeding the
5.805 ms block period at 44.1 kHz. These absolute graph costs include the wrapper
and two operator instances; they are not isolated object costs, optimisation
gains or proof of audio headroom. Coverage continues before optimisation.

The first attempt reached all 33 case records but failed its final global
internal-memory check: decimal error formatting retained 104 bytes between
case records, while each module's own memory baseline recovered. That attempt,
its exact source and artifacts remain saved locally. Logging error/tolerance
as raw IEEE words removes that formatter allocation; the repeated run uses
the same modules, input vectors and comparison limits and passes all memory
gates. The gates were not relaxed.

See [the compact result](../evidence/xiao-smoke-rnbo-numeric.json) and
[the original patches and independent reference](../tests/fixtures/smoke/rnbo-numeric/README.md).

## RNBO arithmetic and logic batch

A single upload checks **36 exact RNBO signal spellings: all 36 pass**, with no
output mismatches, compilation failures or CPU-review flags. Aliases have their
own authored patches and device records; status does not transfer by alias.

| Exact form | Basic hardware result | Median µs | Peak µs | CPU review |
| --- | --- | ---: | ---: | --- |
| `add~` | Pass | 54.0 | 59 | No flag |
| `+~` | Pass | 54.0 | 59 | No flag |
| `mul~` | Pass | 54.0 | 55 | No flag |
| `*~` | Pass | 54.0 | 55 | No flag |
| `times~` | Pass | 54.0 | 59 | No flag |
| `rsub~` | Pass | 54.0 | 58 | No flag |
| `!-~` | Pass | 54.0 | 55 | No flag |
| `rminus~` | Pass | 54.0 | 55 | No flag |
| `absdiff~` | Pass | 89.5 | 93 | No flag |
| `neg~` | Pass | 43.0 | 48 | No flag |
| `fabs~` | Pass | 67.0 | 67 | No flag |
| `pass~` | Pass | 41.0 | 42 | No flag |
| `neq~` | Pass | 54.0 | 55 | No flag |
| `!=~` | Pass | 54.0 | 55 | No flag |
| `notequals~` | Pass | 54.0 | 59 | No flag |
| `gt~` | Pass | 54.0 | 59 | No flag |
| `>~` | Pass | 54.0 | 59 | No flag |
| `greaterthan~` | Pass | 54.0 | 59 | No flag |
| `gte~` | Pass | 54.0 | 55 | No flag |
| `>=~` | Pass | 54.0 | 59 | No flag |
| `greaterthaneq~` | Pass | 54.0 | 59 | No flag |
| `lte~` | Pass | 54.0 | 59 | No flag |
| `<=~` | Pass | 54.0 | 59 | No flag |
| `lessthaneq~` | Pass | 54.0 | 55 | No flag |
| `and~` | Pass | 66.0 | 70 | No flag |
| `&&~` | Pass | 66.0 | 70 | No flag |
| `logand~` | Pass | 66.0 | 66 | No flag |
| `or~` | Pass | 58.0 | 62 | No flag |
| `\|\|~` | Pass | 58.0 | 62 | No flag |
| `xor~` | Pass | 67.0 | 71 | No flag |
| `^^~` | Pass | 67.0 | 71 | No flag |
| `not~` | Pass | 52.0 | 53 | No flag |
| `!~` | Pass | 52.0 | 56 | No flag |
| `boolnum~` | Pass | 52.0 | 53 | No flag |
| `bool~` | Pass | 52.0 | 57 | No flag |
| `b~` | Pass | 52.0 | 52 | No flag |

Each graph has two operator instances, with reversed inputs for binary objects
and independent lanes for unary objects. The common vector covers all 256
ordered pairs of sixteen small binary fractions/integers in [-4,4], including
both zero signs. Twenty callbacks compare 10,240 output words per module:
**368,640 output checks** in this batch. Numeric-zero sign differences are
diagnostic, so `pass~` is a short numerical check rather than a separate
bit-exact copy qualification.

The 16 timed callbacks per graph have median costs from 41 to 89.5 µs, with a
largest observed peak of 93 µs. These are complete stereo graph costs for
256 frames at 44.1 kHz, not per-instance timings or optimisation gains.
All 36 images finalise successfully; the test firmware stays installed and
quiet after completion. Other modes, message-rate forms and domains remain
untested by this batch.

See [the compact device result](../evidence/xiao-smoke-rnbo-stateless.json) and
[the original test patches and reference](../tests/fixtures/smoke/rnbo-stateless/README.md).

## First numeric batch

One upload executes 15 original GenExpr forms: **10 pass and 5 have output
mismatches**. A sixteenth form, `f()`, fails compilation and is not executed.
These are 16 authored scenarios, including three variants of `round` and a
unary-minus form; they are not 16 additional unique inventory names.

| Exact form | Basic hardware result | Median µs | Peak µs | CPU review |
| --- | --- | ---: | ---: | --- |
| `floor(in1)` | Pass | 129.0 | 133 | No flag |
| `ceil(in1)` | Pass | 127.0 | 132 | No flag |
| `trunc(in1)` | Pass | 48.0 | 52 | No flag |
| `round(in1)` | Output mismatch | 172.0 | 177 | No flag |
| `round(in1, 1)` | Output mismatch | 172.0 | 176 | No flag |
| `round(in1, 0.5)` | Output mismatch | 184.0 | 189 | No flag |
| `fract(in1)` | Pass (signed-fraction convention) | 114.0 | 119 | No flag |
| `neg(in1)` | Pass | 44.5 | 45 | No flag |
| `-in1` | Pass | 44.0 | 49 | No flag |
| `absdiff(in1, in2)` | Pass | 47.0 | 47 | No flag |
| `int(in1)` | Pass | 48.0 | 52 | No flag |
| `i(in1)` | Pass | 48.0 | 52 | No flag |
| `float(in1)` | Pass | 42.0 | 47 | No flag |
| `f(in1)` | Compile failure; not executed | — | — | — |
| `isdenorm(in1)` | Output mismatch | 42.0 | 43 | No flag |
| `fixdenorm(in1)` | Output mismatch | 42.0 | 47 | No flag |

Times are measured complete stereo callbacks, 256 frames at 44.1 kHz. They
are absolute costs in this short harness, not optimisation percentages or
isolated instruction costs. The batch uses a 75-word binary32 edge set repeated
across the input vector: both zero signs, subnormals, half-way neighbours,
large integer boundaries and the common safe Int32 endpoints. All 20 checked
calls per module use that same vector; zero-sign differences are recorded
separately and do not fail a numerical-zero check. There is no PCM stage.

Specific findings:

- Default/unit `round` returns 1 for `0x3effffff` (just below 0.5), where the
  half-away-from-zero reference expects 0. The half-unit variant similarly
  returns 0.5 for `0x3e7fffff` (just below 0.25), where 0 is expected.
- `isdenorm` returns an input normal value unchanged instead of predicate 0.
- `fixdenorm` retains the smallest subnormal instead of replacing it with zero.
- `fract` passes the explicitly selected signed-fraction convention. This is
  an observed convention; the short reference wording does not establish every
  negative-input policy.
- Registered alias `f()` reaches export/preparation but fails target C++
  compilation as an undeclared function. Canonical `float()` passes.

The numerical failures are retained for later fixes; no DSP optimisation was
made in this batch. All 15 loaded images are finalised. An initial harness
attempt stopped at its final heap baseline because hardware SHA initialisation
had occurred after that baseline. That attempt remains saved locally; the
corrected harness warms SHA before measurement and the new run completes.

See [the compact result data](../evidence/xiao-smoke-gen-numeric.json) and
[the CPU-review queue](cpu-review-backlog.md).

## Repeatable fast path

`tools/build_smoke_modules.py` reuses a verified existing module-build cache.
It recompiles only the export-dependent wrapper, replaces that object in a
private archive copy, and links each module. The original cache is unchanged.
The first batch builds 15 modules in 13.2 seconds, with one compiler rejection;
this is compiler wall time, not DSP performance.
Rebuilding the combined firmware with the SDK cache takes 7.7 seconds in the
measured check, with 19 build steps and the earlier tested artifacts unchanged.

```sh
python3 tools/build_smoke_modules.py \
  --prepared-root build/prepared/smoke-batch \
  --base-build build/hardware/gen-logic-target-inputs-v1/modules/neq-call \
  --out build/smoke-modules/batch-01

python3 tools/build_hardware_smoke.py \
  --catalog tests/fixtures/smoke/rnbo-stateless/catalog.json \
  --modules-report build/smoke-modules/batch-01/batch-report.json \
  --build-dir build/smoke/batch-01 \
  --cache-build-dir build/hardware-smoke-cache-xiao
```

Supply normal prepared exports matching the selected catalog. The Gen numeric, mathematical and stateful catalogs, plus RNBO stateless,
numeric, function/conversion and event catalogs, have separate independent references. Numeric cases carry their own input-vector hashes and
predeclared tolerances; older catalogs keep the original exact gate.
The initial fast
builder supports strict, self-contained two-input/two-output FX modules with zero to 32 ordinary numeric parameters.
The boundary-event reference route currently uses linear, unstepped controls;
other shapes and control modes remain pending. The
firmware SDK cache is reusable, while each completed batch's artifacts are
copied to its own directory. An unfinished build can use `--resume-incomplete`
only with the same plan; completed batch artifacts are not overwritten.
A module compilation failure returns a nonzero exit status, but its batch
report and successfully built modules remain available for the hardware run.

`tools/run_hardware_smoke.py` writes only the application partition after
checking the selected USB identity, original backup, partition table and build
artifacts. Its `DONE` marker means that the batch completed, including any
recorded output mismatches. It does not mean that every case passed.

`tools/collect_hardware_smoke.py` checks the receipt, module identities, case
totals and raw timing samples, then produces the compact result and CPU queue.
The new reference/tool tests and runner tests pass; the actual device run is
the functionality evidence.

Frontend export/preparation rejections can be retained as separate admission
failures in a merged module ledger. Their original source and failure-log hashes
are checked before planning; they are not counted as C++ compilation failures
or embedded as executable modules. The Gen mathematical result retains all
34 authored forms while embedding only the 27 successful modules. The original
fast module report stays unchanged alongside that merged ledger.

Stateful plans can supply a twenty-block expected stream, beginning with fresh
prepared state and carrying state through every warm-up and timed call. The
collector checks the complete stream shape/hash and callback-specific mismatch
witnesses. Reference data and module payloads share a two-MiB embedding budget;
this leaves room for the framework in the application partition.

`tools/build_smoke_modules.py --max-arena-bytes 1048576` builds the optional
one-MiB resource ceiling while the default remains four KiB. The original cache
control always compiles with its original four-KiB maximum and must match the
whole cached ELF; only candidate wrapper compilations select the larger macro.
For the preserved default filter buffers, `--max-arena-bytes 2097152` selects
the explicit two-MiB tier. The hardware-smoke loader alone is compiled with
that larger caller bound; the ordinary benchmark loader retains its one-MiB
default. The original four-KiB control is still recompiled unchanged.

The host then checks the actual module descriptor against the requested arena,
and the result records reserved capacity separately from observed high-water.

Boundary-event plans contain validated parameter contracts and ordered actual-value
actions. The worker resolves live IDs, verifies initial metadata/readbacks,
applies actions before the next full callback, and logs API timings separately.
Shared reference pools retain complete binary32 blocks and stream hashes; sharing
is exact storage reuse, without lowering sample count or comparison precision.

## Gen noise, FFT context and compound assignments

The [24-source guide](../tests/fixtures/smoke/gen-execution-forms/README.md)
retains **five hardware passes, 14 C++ failures and five frontend failures**.
Noise passes a finite/range/32-sample variation screen; local `+=`, `*=`, `-=`
and `/=` pass independent arithmetic references. The 51,200 output-word checks
have zero differences. FFT programs never execute: standalone globals are
undeclared. History compound assignments and local modulus assignment fail C++;
five bitwise compound forms fail parsing. No failed form is silently replaced
with an easier passing program.

Whole offline callback medians are 44–115 µs, peaks 45–120 µs, with no CPU flag;
the queue remains 111 contexts. All five images finalise with no late/host
allocation, zero arena high-water and unchanged free RAM. Noise flag equality
does not compare random sequences. FFT transforms, exact default constants,
one-frame host calls and general stateful operator aliases remain unqualified.
See [target evidence](../evidence/xiao-smoke-gen-execution-forms.json) and
[native/rejection evidence](../evidence/gen-execution-forms-native.json).
The ordinary player is restored after the batch for Studio use.

## Analysis, oscillator and noise member methods

The [22-source member guide](../tests/fixtures/smoke/rnbo-codebox-analysis-members/README.md)
records **19 executions: 16 passes and three output mismatches**, with 194,560
output-word checks. Three direct-list-index window programs fail C++. Named-list
variants execute, but their state-only selectors are hoisted before the sample
loop; they retain their original per-sample reference mismatches. A secondary
native callback-held model explains these observations without replacing the
original oracle. Fixed/reset/input-reset means, oscillator audio/current phase/
reset/phase-index checks and basic noise/paired-seed screens pass.

Twelve complete average callbacks trigger CPU review at 587–820 µs median,
raising the queue to **123 contexts**. Their two original Float64 rings observe
705,760 bytes arena high-water despite 3–16-sample logical windows. Cycle
scenarios use 65,648 bytes and noise scenarios zero arena bytes; a 2 MiB capacity
ceiling is not consumption. All 19 images finalise with no late/host allocations
or frees, and unchanged completion RAM totals.

Results bind eleven exact member IDs, taking the RNBO dashboard to **789 scoped
entries**, without inheriting results into bare names, aliases, patcher objects
or Gen. Default physical buffer wrap, full noise semantics and general modes
remain outside the checks. The normal player, saved Main and live controls are
[restored and verified](../evidence/xiao-analysis-members-player-restoration.json).
See [target results](../evidence/xiao-smoke-rnbo-codebox-analysis-members.json) and
[native diagnostics](../evidence/rnbo-codebox-analysis-members-native.json).
