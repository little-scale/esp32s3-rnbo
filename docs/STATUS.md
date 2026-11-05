# Implementation status — 6 November 2026

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

The [analysis/oscillator/noise member batch](hardware-smoke.md#analysis-oscillator-and-noise-member-methods)
records **22 sources: 19 execute, 16 pass, three retain output mismatches and
three fail C++**, across 194,560 output-word checks. Fixed means, explicit and
input resets, oscillator phase/state and bounded noise screens pass. Three
named-list selectors are evaluated once per callback, retaining their per-sample
window-change mismatches; a separate native diagnostic explains that schedule
without changing the primary oracle. The 11 exact member IDs bring the RNBO
dashboard to **789 scoped entries**. Twelve average CPU contexts (587–820 µs
median and 705,760-byte arena high-water) bring the review queue to **123**.
All images finalise and allocation/memory gates pass. The normal player and
saved controls are restored and USB/audio progress verified. The full RNBO/Gen
qualification goal remains active and incomplete.

The [Gen execution-form batch](hardware-smoke.md#gen-noise-fft-context-and-compound-assignments)
records **24 sources: five hardware passes, 14 C++ rejections and five frontend
rejections**, with 51,200 output-word checks. Noise passes only its declared
range/variation screen; four local arithmetic compound assignments pass bit
for bit. FFT context values, History compound updates, floating modulus
assignment and bitwise compound forms retain exact route failures. Callback
medians are 44–115 µs (0.76–1.98% of the audio period), with no new CPU flags;
the queue stays **111**. All five images finalise and allocation/memory checks
pass. These Gen results do not change the **778-entry RNBO** dashboard count
or complete visual Gen, event/resource/mode or remaining RNBO qualification.
The [normal player has been restored](../evidence/xiao-gen-execution-player-restoration.json);
its saved Main and live controls match the pre-test snapshot, USB replies and
audio frame progress are verified, and runtime counters remain zero.

The [extended Gen data batch](hardware-smoke.md#extended-gen-tables-sample-access-and-boundaries)
records 31 sources: **24 execute on XIAO, 17 pass and seven retain mismatches**,
with 245,760 output checks. Seven frontend/C++/adapter rejections are separate.
Long-period oscillators and weighted writes pass cross-block sample-state
checks. Five channel cases differ between native and Xtensa; a host sanitizer
confirms an out-of-range negative-float-to-unsigned conversion before boundary
handling. Signal lookup adds one CPU context at 807 µs median, bringing the queue
to **111**. All loaded images finalise and memory/allocation gates pass. Quiet
Gen part 2 firmware is installed. The RNBO table remains **778 scoped entries**;
Gen/visual/resource/remaining RNBO qualification stays active and incomplete.


The [delay resource/member batch](hardware-smoke.md#delay-resources-and-member-operations)
executes **22 programs: 17 pass and five retain mismatches**, across 225,280
output checks. Eleven string-enum calls remain C++ rejections; separately
sourced numeric enums execute. Fractional next size and higher-order read
alignment remain scoped compatibility follow-ups. All images finalise and
memory/allocation gates pass. The nine new CPU contexts bring the queue to
**110**: default comb/allpass clear/reset scenarios take about 44 ms per callback,
including repeated clearing of roughly 1 MiB state. The RNBO table now maps
**778 entries with scoped outcomes**. Quiet delay-member test firmware was
installed at that checkpoint; the complete qualification goal remains active.


The [explicit member batch](hardware-smoke.md#explicit-stateful-members-and-resetclear)
records 36 original next/reset/clear programs in two uploads: **35 execute,
27 pass and eight retain mismatches**, with 358,400 output checks. The one-pole
reset/clear cache issue is reproduced on native and XIAO; downsample phase and
zero-crossing boundary differences remain visible. `history.reset()` fails C++.
Whole-callback medians are 56–500.5 µs, peak 503 µs, with no new CPU flag; the queue
remains **101 contexts**. All images finalise and allocation/memory gates pass.
The dashboard now maps **765 exact entries with scoped outcomes**. The second
quiet member-test firmware was installed at that checkpoint and the complete goal remains active.


The [RNBO codebox structure/lifecycle batch](hardware-smoke.md#rnbo-codebox-structures-and-lifecycle)
passes **all 24 programs and 245,760 numeric output checks** on XIAO. It covers
bounded control flow, short-circuit side effects, scalar/list-return functions,
sample/block state and fresh lifecycle counts. **3,700 signed-zero differences**
remain explicit. Whole callback medians span 41.5–86 µs, peak 91 µs; no new CPU
flags, so the queue remains **101**. All images finalise and memory/allocation
gates pass. The three lifecycle hooks bring the RNBO table to **730 exact
entries with scoped outcomes**. The quiet structure-test firmware was installed at that checkpoint;
the complete RNBO/Gen/structure goal remains active.

The GitHub Linux workflow is also fixed: strict GCC rejected misleading
indentation in the MIDI parser test helper. Explicit braces preserve the test
and warnings; all stages passed after commit `5c089b7`.


The [list-function call batch](hardware-smoke.md#rnbo-list-function-call-forms)
records all 34 authored sources: ten execute on XIAO, **nine pass**, and
`listsect` retains a duplicate-policy mismatch across **102,400 output checks**.
Seven forms fail C++ array-bounds warning checks, sixteen reject in the frontend
(including fifteen dotted calls), and the wide rotation vector faults in native
preflight and is deliberately not flashed. Every executed image finalises and
passes memory/allocation gates. `listswap` and `listunion` join the CPU queue,
bringing it to **101**. The RNBO table now maps **727 exact entries with scoped
outcomes**, including unverified/rejected forms. The quiet list-function smoke
firmware was installed at that checkpoint; the complete RNBO/Gen/structure goal remains active.

The next [Gen control/structure batch](hardware-smoke.md#gen-control-declarations-and-language-structures)
passes **19 programs and 194,560 numeric output checks** on XIAO. Twelve
pass-gate spellings, `Param` defaults, elapsed sample counting, lowercase history,
two independent function-local histories and bounded for/while/break/continue
pass with zero finite numerical error. **33,360 signed-zero differences** remain
explicit; this is not bit-identity qualification. Five exact forms fail C++ and
two fail the Gen frontend, with source/log identities saved. No CPU flag
triggers (42–94.5 µs medians, 99 µs largest peak); the queue remains 99.
Gen evidence stays separate from the 693 mapped RNBO entries. The latest quiet
Gen smoke firmware is installed and the complete qualification goal stays active.

The qualification goal has **resumed**. The new
[codebox container batch](hardware-smoke.md#rnbo-codebox-lists-and-fixed-arrays)
passes all 26 executable programs on XIAO: all seventeen fixed-array
constructors and nine list methods, **266,240 exact output checks**, continuous
sample/block state and no late-allocation or memory-finalisation faults. Two
documented length-return forms (`push`, `unshift`) fail C++ compilation and stay
separate. Five whole list callbacks are queued for CPU review, bringing the
backlog to **99**; no optimisation gain is claimed. The dashboard now maps
**693 exact entries**, including scoped passes, gaps and rejected forms rather
than 693 fully qualified objects. The quiet smoke firmware remains installed.

**Follow-up requested: return to physical MIDI testing when hardware is
available, UART first and USB host second.** The
[return-to-test checklist](midi-inputs.md#return-to-test-checklist) records the
required equipment, functional checks and CPU/error observations. No external
MIDI hardware testing is running; the main qualification goal is active.

The [MIDI-input tangent](midi-inputs.md) now has UART1 input on **XIAO
D7/GPIO44**, saved off/UART selection in Studio, running status, MIDI clock and
short system messages, plus bounded queue and held-note recovery. At that
checkpoint the updated standard player was installed. A silent monitor passed **206 delivered messages**,
including exact counts of 96 software clocks and 96 actual UART internal-loopback
clocks, note/velocity readback, transport/system-common bytes, pause/resume
releases and Active Sensing timeout. All audio/allocation fault counters stayed
zero; the original Main patch `a` was restored at 50%, with UART off.
[Evidence](../evidence/player-midi-xiao.json) records its narrow scope: external
receiver wiring, the D7 pad and a physical MIDI controller remain untested.

An explicit experimental USB MIDI1 host variant builds, with bounded descriptor
and packet-decoder tests. It replaces the USB console and needs a suitable host
adapter/power arrangement and previously paired Wi-Fi. It has **not** been
flashed or tested with a USB controller. Standard XIAO, host XIAO and standard
AMOLED builds pass, along with 526 compiler tests, 97 Studio tests, 25 frontend
tests, the UBSan parser check and seven native monitor/contract tests. These
transport checks do not promote RNBO object catalog entries. The main
qualification goal remained paused at that checkpoint; it has now resumed above.

Studio now offers explicit [Float32 Trial mode](float32-trial.md). It attempts
eligible unreviewed DSP methods, compares default native output with Auto and
saves method fingerprints/edits/skips plus post-upload CPU/error observations.
Saved packages retain an **unverified** label and `[Float32 trial]` display name.
EEE and an original dynamic-resonance filter example passed the full build
workflow; the filter also passed a short XIAO runtime smoke. Its small native
sample-error diagnostic failure is retained. No catalog entries were promoted.
Reviewed EEE was restored at the observed 41% volume before releasing the board
for the user's physical-input player installation.

The earlier physical-input tangent added
[inline `@meta` input bindings](physical-inputs.md), which now compile into
XIAO player packages, with analog smoothing, debounced digital gates and
capacitive-touch calibration/hysteresis. Studio shows mappings and live input
diagnostics. Both board player builds pass; installation is available through
Studio and physical input wiring tests remain pending. The
[pin table and copyable examples](physical-inputs.md#exactly-how-xiao-pin-names-map)
document aliases, reservations and the XIAO-only input profile.

The supplied [EEE patch now runs on XIAO](eee-optimisation.md): the reviewed
fixed-0.9 `lores~` method uses Float32 math. The previous Auto package was rejected
at 5,993 µs; the running candidate's 112 status observations give a **2,246.5 µs
median (38.70% audio CPU)** and **2,585 µs observed peak (44.53%)**. All checked
fault/allocation counters are zero across the note sweep. Its original file,
wiring and delay length are untouched. Native comparison records up to 1 PCM LSB
difference; the strict 2e-6 sample-error diagnostic fails and remains recorded.
That comparison used the existing player, saved Wi-Fi and **17% volume**, note
**39**; its later Trial-test restoration is described above. All **517 compiler
tests** passed at that stage. This is a patch-specific tangent, not a resumed qualification goal.

The [local Gen Data batch](hardware-smoke.md#gen-local-data-and-indexed-storage)
passes all eight programs and 81,920 output checks, including indexed history,
same-sample writes/reads and seven-sample feedback across callback boundaries.
Original Float32 storage is preserved; every program measures 128 bytes of
arena high-water. Feedback's 687/688 µs median/peak adds one future CPU review,
bringing the queue to **94**. Other modes and external Buffer remain pending.

All [85 remaining RNBO character constants](hardware-smoke.md#rnbo-character-constants)
pass on XIAO: **870,400 raw-word-exact output checks**, including strict signed-
zero input copies. Combined with the earlier ten digits, all 95 printable-ASCII
bare names now have scoped hardware evidence. No CPU flag triggers; medians
are 40–40.5 µs, peak 45 µs. The status page now maps **665 exact entries**.

The [further RNBO signal-state batch](hardware-smoke.md#further-rnbo-signal-state)
executes seven programs and 71,680 output checks: six pass, while `onoff~`
retains a documented block-versus-sample toggle mismatch. Counter outputs,
normalization history and linear-filter scenarios pass; no CPU flags trigger.
At that stage the page mapped **580 exact entries**, with previous qualifications
and failures retained. `updown~` remains reference-design-pending.

The [Gen Delay compatibility fix and hardware rerun](gen-delay-bool-clamp.md)
now pass both previously blocked programs: **20,480 output checks**, including
one-sample delay and feedback across callback boundaries. Three guarded integer
casts resolve the generated-code warning while preserving numerical semantics,
Float64 storage and compiler warning settings. Original failures and the five
phase/pulse mismatches remain saved separately; no speedup is claimed.

The explicit [Float32 dbtoa experiment](dbtoa-float32.md) passes all 48 XIAO
runs and 491,520 independent output checks. Its matched stereo callback uses
**91.64% less time**: 15,869.50 → 1,326.51 µs mean, or 273.38% → 22.85% of
the block period. Changed rounding is recorded separately; maximum target
error is 1.1920928955078125e-7. Native PCM pairs are identical, while direct
target pairwise PCM/float capture is untested. The option remains explicit and
exact-graph; Studio Auto is unchanged. The status page shows this as an
experimental measured optimisation for `dbtoa~` only.

The player now supports [Wi-Fi scanning, USB pairing and wireless package loads](player-wifi.md).
XIAO association, authenticated upload with no USB serial handle, wireless
controls and failed-connection retry stability pass. An early system-event stack
overflow was corrected with a minimal callback and an 8 KiB event-task stack.
Studio now defaults to **automatic reviewed Float32 optimisation**; unknown
methods keep their original code. The [DDD comparison](ddd-optimisation.md)
records the speed observation and its explicit numerical differences. Integer
number-box import is supported; exact current producer identities were added
without changing historical hardware records or admitted DSP bytes.

The [stable Main player and RNBO Studio](player-protocol.md) now load compiled
`.rnbopkg` patches over USB while keeping player firmware installed. All effects
live inside Main. XIAO package swaps, saved-package reopening, controls and reboot
restoration pass; a 60-second drone run has zero reported audio errors. The AMOLED
player builds and passes computer-side display checks; its device trial remains
pending. [Exact integration evidence](../evidence/player-xiao.json) records scope
and artifact identities. The user has authorised continuing fast object qualification, CPU flags and
separately recorded Float32 optimisation.

The [signal routing and interpolation batch](hardware-smoke.md#rnbo-signal-routing-and-interpolation)
passes all 20 exact spellings and 204,800 output checks. `cubicinterp~` records
3,367 µs median/3,371 µs peak, around 58% of the block period, and brings the
CPU-review queue to 93. Interpolation rounding and gate zero-sign differences
are retained separately. The status page now maps 576 exact entries; this is
scoped evidence, not complete-object qualification. Those runs used quiet smoke firmware. A verified full-flash backup preserves
the player, package and private settings; the player has since been restored silently.

The [Gen clock/reset/delay boundary batch](hardware-smoke.md#gen-clock-reset-and-delay-boundaries)
retains all eight programs. Six execute: `mulequals` passes and five phase/pulse
comparisons retain mismatches against their declared policies. Two explicit
Delay programs originally stopped at a generated-code boolean-comparison compiler warning;
the marked two-program rerun above resolves those builds and passes their original references.
All 61,440 executed output checks are saved; there are no CPU flags or memory
faults. Delay and phase-policy follow-ups remain separate from the earlier
passing Gen history/state evidence.

The [parameter-driven event batch](hardware-smoke.md#rnbo-parameter-driven-event-batch)
passes all 35 exact event spellings,735 updates/readbacks and 358,400 output checks.
A single linear numeric control is applied at callback boundaries; the independent
right observer is raw-bit exact. Event-call and processing timings remain separate,
with no CPU flags. Exact reference pooling keeps the full test within existing
flash/report limits. Within-block host-event timing is still unqualified.

The latest [RNBO functions/conversions batch](hardware-smoke.md#rnbo-functions-and-conversions-batch)
executes 35 forms: 34 pass declared limits, `fasttan~` exceeds an explicitly
chosen approximation threshold, and eleven CPU costs are queued. `dbtoa~`
takes 14.659 ms median in the stereo fixture. An explicit one-MiB arena tier
preserves default resources; `mtof~` peaks at 262,416 bytes and `ftom~` at 160.
No DSP optimisation or timing gain is claimed by this infrastructure change.

Testing now prioritises [fast batched hardware checks](hardware-smoke.md),
with CPU-review flags retained for future optimisation. The latest numeric
batch checks 33 RNBO signal forms: 30 pass, three have output mismatches
(`round~`, `isdenorm~`, `fixdenorm~`), and eight are queued for CPU review.
The stereo `exp2~` fixture exceeds the block period. The previous arithmetic/logic
batch checks 36 exact spellings: all pass, with no CPU-review flags. The earlier numeric Gen run executes 15 forms: 10 pass, 5 have output
mismatches; registered `f()` fails compilation. It also has no CPU-review flags. Those batches used quiet smoke firmware; the stable player is now installed on
XIAO with the saved drone package.

The [stateful Gen batch](hardware-smoke.md#gen-stateful-and-per-sample-batch)
passes all twelve programs/nine exact spellings. Its 122,880 output checks carry
sample state through twenty continuous callbacks per program and expose block
boundary resets. No new CPU-review flags trigger; medians are 50–551 µs.
This is per-sample semantics within fixed256-frame calls, not a one-frame host
ABI or sample-offset event qualification.

The new [Gen mathematical smoke batch](hardware-smoke.md#gen-mathematical-batch)
retains all 34 authored forms: 27 pass on XIAO, four fail C++ compilation and
three fail frontend parsing. Thirteen executed forms trigger CPU review.
`exp2` again exceeds the stereo block period. Valid-domain manual warmups are
recorded explicitly; this batch does not add single-sample or feedback claims.

The earlier [Gen comparison/logic batch](gen-logic-qualification.md) adds twenty
native/XIAO passes with per-form timing, exact outputs and full memory recovery.
The twenty-first form, `step`, fails the unchanged documented argument-order
model on native and target execution; the failure is retained. `sign(-0)` is
observed as `+0`. Two interrupted recovery checks are preserved separately;
fresh runs pass after adding a command-free boot phase. Final local checks pass
463 compiler, 141 tool and 31 recovery-runner tests. That batch restored the drone at 50%.

The active scope also includes **Gen/`gen~` and its single-sample processing**.
Gen has a separate metadata inventory, guarded GenExpr export admission and two
native History programs with sample-level feedback/reset/partition tests.
Three Gen history programs now also pass XIAO execution: 1,769,472 independent
model checks and 828 observable reset witnesses, exact memory recovery and
verified drone restoration. Identical-module timings claim no gain. Other
operators, visual Gen import and sample-offset target events remain pending;
the RNBO table does not validate Gen. See [the Gen results](gen-qualification.md) and
[the qualification requirements](qualification-scope.md).
The optional [Gen feedback Float32 profile](gen-feedback-float32.md) now removes
the baseline's double-literal promotion. Its matched XIAO comparison uses 83.94%
less whole-callback time with exact output in the three declared cases and
unchanged state/memory behaviour. Native subnormal/zero-sign counterexamples
retain the explicit changed-rounding contract; other Gen graphs remain pending.

Fifteen separately authored GenExpr arithmetic spellings now also pass XIAO:
45 case programs, 4,423,680 exact pair comparisons and 8,847,360 independent
model/bit checks, with full memory recovery and drone restoration. Absolute
callback times are [recorded per exact source](gen-arithmetic-qualification.md);
same-image controls claim no optimisation gain. Three unbound, non-registry
function-call probes are kept as compile failures rather than working objects.

The optional [Gen abs intrinsic](gen-abs-intrinsic.md) now passes four matched
XIAO cases with exact finite magnitude bits, including subnormals and zero
signs. Callback time falls from 71.46 to 45.60 µs (36.19% less); Float32 calls
become Float32 instructions and scheduler precision is unchanged. The drone is
restored at 50%. Final local checks pass 454 compiler and 135 tool tests.

Systematic **XIAO object qualification** is now active. The first isolated
oscillator control and comb/allpass duration-hoist comparisons passed, with
5,505,024 exact reference/candidate sample comparisons, complete memory recovery
and verified restoration to the drone at 50%. The filter fixture used 29.03%
less callback time; the identical-module oscillator control claims no gain.
Neither first-batch Main test runs an independent on-device semantic oracle.
A subsequent biquad stereo FX control passes 4,718,592 independent output-model
checks and 18 settled-level checks, with zero pair differences and full memory
recovery. Its same-module timing claims no optimisation gain. See
[the board-specific results and remaining scope](xiao-qualification.md).

Thirteen additional arithmetic/comparison/RNBO-codebox fixtures now pass on XIAO:
3,833,856 pair comparisons, 7,667,712 independent model checks, exact observer
bits, recovered memory and restored drone defaults. Their absolute callback
times and exact source scopes are recorded separately; identical-module controls
claim no optimisation gain. This adds 15 scoped exact names to the dashboard, without Gen coverage or new
optimisation percentages.

The **XIAO ESP32-S3 headless profile** now has initial 3sawsDrone hardware
validation. It uses the same prepared patch as AMOLED and starts automatically,
unpaused at 50% volume. Stereo buffer capture, USB parameter control,
Pause/Resume and watchdog-reboot startup checks pass with zero reported audio
faults. The user confirmed hearing the drone through the existing I²S DAC.
This is whole-patch bring-up; per-object qualification remains separate.
See the [headless guide](headless.md).

The **Waveshare ESP32-S3 Touch AMOLED 1.8 V2** has been qualified running the supplied
`3sawsDrone3` patch with an FM1-style graph, a 40 ms comb limit and optional
float32 delay storage/audio arithmetic. The user confirmed audio and touch
parameter control. The current
[AMOLED interface](amoled-controls.md) provides a single Pause/Resume button,
a Patch/Params page switch, eight wide vertical parameter bars with continuous cross-bar
dragging, a thicker volume slider and a post-volume output meter. The user
confirmed the continuous gesture works well. See [patch qualification](drone3-qualification.md)
and [the numerical choices](float32-audio.md). The original firmware has a
private full-flash backup, and earlier readback
verified that the original bootloader, partition table, NVS and PHY bytes below
the application are unchanged.

The earlier compact drone build completed 300 continuously playing status polls
over 303 seconds, with the output volume set to zero for the timing test.
Average render work was 3,879.3 µs (66.83% of one audio core), peak 4,967 µs,
against a 5,805 µs block period. There were no render overruns, DMA/write/module
errors, non-finite samples or late audio-owner allocations. Its arena uses
361,240 of 393,216 reserved bytes, freeing 655,360 bytes compared with the
earlier 1 MiB reservation. This is measured workload evidence, not a hard
worst-case bound or a Wi-Fi qualification.

That earlier measurement used firmware ELF
`f64cdf654598d72955e9ec5cca6fd9cd3eaa7230def4d95590347826ff9d9ac3`.
It is historical evidence for that build, rather than a timing qualification
of the newer interface.

The latest verified installation is the wide-bar GUI with a single playback
button, ELF
`722047477ce7dd2d46c1531e1c3de1ab70f0b4c2b7bf20f35fede45467fef78c`.
It retains the qualified optimised drone export, including unused-table
omission: the arena uses 99,088 of 131,072 reserved bytes. The installation
check captured silence → signal → silence at volume 0 → 5 → 0, restored all
eight parameter values, volume and Pause state, and observed no render
deadline overruns or allocation/module/DMA/write faults. The subsequent user
trial of the preceding wide-bar build confirmed easier continuous dragging.
The newer single-button installation restored the freshly saved 25% volume,
paused state and all eight parameter values, with no observed faults. This is
the last verified RNBO snapshot, not a guarantee of current live settings.
The subsequent XIAO bring-up and object-test goal authorise scoped hardware
work on that identified board. Fresh identification and recovery evidence remain
required before replacing any other current image. Cold startup uses zero speaker volume; controls remain RAM state. The preceding
GUIv3 image and its recovery observations remain historical evidence.
See [the current GUI installation evidence](../evidence/amoled-gui-v4.json) and
[the table-omission review](unused-mtof-table.md).

## Hardware qualification

The board reports ESP32-S3 revision 0.2, 16 MiB flash and 8 MiB PSRAM. Firmware
and module source identities are recorded in every capture and qualification.

| Check | Recorded result |
| --- | --- |
| Strict oscillator: volume, actual/normalized pitch, Panic/resume | 8 cases passed |
| Optimized oscillator: same controls and capture checks | 8 cases passed |
| Strict and optimized four-voice MIDI | 19 cases passed per profile, including four simultaneous voices, independent release, sustain, stealing and stale note-off |
| Five-minute MIDI stress per profile | 2,400 acknowledged events, nine concurrent periodic captures, no missed render deadlines or late allocations |
| Ten detached reconstructions after each stress run | Free internal RAM and PSRAM totals unchanged |
| Allocation guard negative test | One intentional 16-byte audio-task allocation detected; output became exact digital silence; clean operation restored |
| Host versus target oscillator PCM | 44,100 samples matched exactly in both comparisons after integer-vector alignment, without gain or fractional phase fitting |
| Native ELF loader fixture | 32 measured cycles with two simultaneous images, constructor/finalizer/callback checks and exact heap recovery passed |
| Real RNBO dynamic modules | 132 loads/unloads, 32 lifecycle rounds, 378,368 exact float/PCM comparisons, stereo FX and four distinct MIDI notes; free memory recovered |
| FM1-style patch view | Actual 58-object/70-connection graph; native LVGL touch simulation and user-confirmed audio/parameter control |

During both MIDI stress runs, free internal RAM stayed at 190,499 bytes and free
PSRAM at 7,197,948 bytes. Audio stack headroom stayed above 12 KiB. The largest
contiguous PSRAM block decreased once after initial reconstruction, then remained
bounded across the recorded cycles; total free memory did not decrease.

Real RNBO modules also passed the [isolated loader qualification](dynamic-loader.md).
The stable player now integrates Main replacement and flash maintenance on XIAO;
its AMOLED device trial remains pending. Effects are contained inside Main.
External clock/data signals were not measured with
electrical test equipment. Speaker/display observations came from the user;
software PCM capture is a separate evidence category.

## Measured compiler optimization

The optional `float32-cycle-v1` profile changes exactly two coefficients in each
qualified RNBO 1.4.4 oscillator kernel to float32 literals. It retains integer
phase arithmetic, lookup/interpolation, buffers and double scheduler time.
The strict profile remains the default.

The two runs used matching firmware sources, toolchain, configuration and
dependencies. Only the prepared numerical profile differed.

| Five-minute four-voice workload | Strict | Optimized |
| --- | ---: | ---: |
| Average render time per 256-frame block | 3,311.7 µs | 2,003.4 µs |
| Average share of one audio core | 57.0% | 34.5% |
| Highest observed render time | 4,276 µs | 3,082 µs |
| Render deadline overruns | 0 | 0 |
| Observed late audio allocations | 0 | 0 |

Average render work decreased **39.5%**, about **1.65× faster** in this workload.
Render timing covers audio-owner events through final PCM. I²S waiting and
post-write capture are measured separately. The peaks are observations, not
hard timing bounds, and Wi-Fi was inactive.

All 36 authored host comparison cases produced identical final float32 and PCM
samples. An exhaustive intermediate-value check found small fraction differences,
so this is not a general bit-identity promise for arbitrary patches or feedback.
See [the numerical profile documentation](../host/README.md).

## Oscillator recovery image and earlier evidence

The known-good oscillator recovery application is
`build/firmware-amoled-rnbo-sine-cycle-f32/`, with ELF
identity `b14f63ef2f56e30732afec7c893fd68f68d22e584d023689cac524ce5c901ca4`.
It renders the autonomous 440 Hz oscillator, level 0.2. Its earlier read-only
snapshot showed the user's selected **28% volume**, running, with no faults.
Controls are RAM state; startup defaults apply after a reset.

Machine-readable results and links to raw logs/captures are in
[amoled-v2-hardware.json](../evidence/amoled-v2-hardware.json). Detailed local
reports live under `build/hardware/amoled-first/`. The initial host-only snapshot
is retained in [initial-validation.json](../evidence/initial-validation.json);
later hardware results supersede its unqualified status. The loader test was
rebuilt with a short USB-attachment delay for complete log collection.

Software validation also includes 25 compiler/admission tests, 36 client tests,
46 strict/optimized native fixture checks, 34 upstream loader host regressions,
four emitted-loader validation checks, and five earlier UBSan runtime checks.
Generated code and runtime notices remain in ignored local build directories.
Imported source/license identities are in [UPSTREAM.json](../UPSTREAM.json).

The expanded source now passes 39 compiler/admission tests, 16 dynamic host
tests, seven layout tests, three actual-XAM importer tests, three portable
runtime tests and native LVGL interaction checks. The XIAO profile also rebuilds
with the current shell; no XIAO hardware was attached. Local macOS
AddressSanitizer binaries stalled at startup, so this session does not claim a
new ASan pass. The portable tests passed without it; the public Linux workflow
runs the sanitizer configuration separately.

## Remaining implementation gates

The local RNBO 1.4.4 exporter, validated manual import, native compiler route,
static C ABI, caller-owned dynamic SDK, bounded owner events, allocation guards,
capture and FM1-style UI are implemented. Stable player builds now integrate
loaded Main images with the live audio lifecycle, persistent `.rnbopkg` selection
and previous-package recovery. Studio compiles or reopens packages and loads them
without reflashing the player. Static patch firmware remains available for
development. Physical AMOLED player validation, interrupted-power recovery,
authenticated Wi-Fi/group deployment, full browser conversion and broader
RNBO/Gen coverage remain later work. The new XIAO whole-patch bring-up is described above; comprehensive
per-object XIAO hardware qualification remains open.
