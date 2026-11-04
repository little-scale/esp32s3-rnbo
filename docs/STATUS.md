# Implementation status — 5 November 2026

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
scoped evidence, not complete-object qualification. Quiet smoke firmware is
currently installed on XIAO; the previous player, package and private settings
have a verified full-flash backup for later restoration.

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
