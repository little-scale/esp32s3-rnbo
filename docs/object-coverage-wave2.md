# Object coverage audit and second-wave evidence

The handover's FM1 compatibility counts are reference-project evidence. They
do not establish this compiler's native or ESP32 coverage. The implementation
compiles generated RNBO operators; it does not maintain a replacement DSP
interpreter or claim that an optimization catalog is an RNBO object whitelist.

Current admission fixes RNBO1.4.4,44.1kHz/256frames, Main0→2 or FX2→2, ordinary
numeric parameters, bounded MIDI ports and the declared service restrictions.
The flat importer supports ordinary object/message/number graphs. It explicitly
rejects embedded/external patch dependencies and visual `gen~`. External data
and message services remain outside the current adapter. Other builtin objects
can compile under strict preparation when those contracts and budgets fit;
each generated form still needs output, resource and target qualification.

The first object wave has15 original forms across eight families: cycle,
saw, mtof, scale, resonator, comb/allpass, ordinary delay and arithmetic. Separate
examples/native tests cover stereo pass-through and the authored MIDI envelope
at1/2/4voices. These are forms and workloads, not complete object/mode coverage.
Target evidence remains separate in the existing object-optimization reports.

The highest missing areas before wave2 were:

| Gap | Why it matters | Wave2 scope |
| --- | --- | --- |
| Averaging/history reductions | Handover specifically identifies oversized averaging buffers; running sums have different precision concerns from delay interpolation | Window1/16/63/64, reset versus warm history, impulse/DC and cancellation |
| Ramp/control scheduling | Time arithmetic must retain intentional precision; a good oscillator comparison says nothing about interrupted ramps | line~/pack,0/5/10ms, block-boundary interruption/restart |
| PRNG and clock-derived state | Supplied seed and private target clock do not necessarily control each object's internal generator | Explicit white seed and native pink clock seed, spectrum and repeat observations |
| Other phase/time oscillators | Phasor/pulse counters differ from cycle's integer phase algorithm | Negative/zero phasor rates, train sample period/duty extremes |
| Recursive filters | Resonator coverage does not cover arbitrary biquad coefficient/state behavior | Biquad difference-equation impulse/DC, identity and stable slow pole |
| Nonlinear math | Generic math overloads/domain boundaries can select different precision paths | tanh, wrap/clip and fractional/integer pow over declared safe domains |

Six original graphs and23 cases are in
`tests/fixtures/objects/wave2/catalog.json`; their runner is
`host/compiler/qualify_wave2.py`. The sealed initial result is
[`objects-wave2.json`](../evidence/objects-wave2.json), corresponding to
`build/object-qualification/wave2-final/report.json`. Eight independent model
and adversarial unit tests pass. Every render is finite and has zero observed
late RNBO Platform allocations/errors. This does not prove complete libc/C++
allocation coverage or target deadlines.

Four families pass their declared semantic gates: line, biquad, phase/pulse and
nonlinear math. Average impulse/DC checks pass, but the strict cancellation
case exceeds the unchanged2e-6 accuracy limit: maximum absolute errors are
8.6557120e-6 and1.0257587e-5 against a fresh double-precision mathematical window.
The independent oracle does not copy the generated running-accumulator method.
It fixes zero causal lag and source-grounded reset/warmup policy; negative tests
reject wrong history, wrong windows and a one-sample regression.

The two averaging objects reserve705,632B of the Platform arena although the
authored maximum window is64. Each initializer requests44,101double frames;
the DSP setup can regrow that capacity. A future bounded-history experiment
must address both routes and preserve maximum-window-plus-one capacity because
the current sample is written before the oldest sample is read. Such a memory
change does not automatically correct running-sum drift.

White noise variance was0.3326981, lag-one correlation−0.0008014 and low/high
spectral-power ratio0.87369. Pink's low/high ratio was71.0589. These bounded
statistical observations pass; native same-create-seed pink reconstruction is
not bit-identical. The explicit white stream is identical. Sealed source methods
show pink initializes its private LCG from `systemticks()`; native `clock()` and
the dynamic module's private clock are distinct policies. No SDK change is
inferred from this host finding.

The report therefore intentionally has `completed:true`, `passed:false` and
the CLI returns nonzero. It retains the two baseline limitations. All six
audio-v2 attempts are recorded as `unsupported-form`; the current exact catalog
does not admit these new audio methods. Source-only precision inventories live
under `wave2-final/precision/`. Decimal counts indicate review candidates, not
measured double calls or justified transformations.

Still outside this wave: arbitrary long-uptime scheduler/counter behavior,
nested clocks, cancellation/overflow under queue pressure, full ADSR curve and
shared-polyphony topology, all interpolation modes and fractional delay/gain
boundaries, FFT/spectral/convolution families, general sample/data resources,
transport/sequencing collections, arbitrary lists and Gen conversion. Their
absence is an evidence gap, not a statement that every such builtin is banned.
Filesystem, external data and message-resource work additionally needs service
design/admission rather than an object-name expansion alone.
