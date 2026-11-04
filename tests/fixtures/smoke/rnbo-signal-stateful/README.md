# RNBO signal stateful smoke fixtures

These 15 original MIT-authored flat RNBO patches exercise exact signal-object spellings. Each FX patch has two independent objects and two outputs; latch and sample/hold receive cross-connected signal controls. Fixed control literals, active ports, primary XML fingerprints and model IDs 700–714 are recorded in `catalog.json`. There are no parameters, codebox programs or GenExpr nodes. Their results do not inherit codebox, Gen or alias qualifications.

Fresh constructors run with zero automatic preparation warm blocks, followed by four compared manual callbacks and sixteen compared timed callbacks. `reference_blocks` carries state continuously across twenty repeated 256-frame vectors. Each model has a first-versus-subsequent-block witness, including previous-input state, held values, gate edges, unfinished ramps, window/report phases and accumulated history.

Controls are explicit: accumulator reset0 with scaled input, DC coefficients .5/.75, dyadic delta-clipping slopes, downsampling3/5, linear ramps4/8, default positive gate edges, zero-count windows7/5, absolute/RMS windows8/16 with reset0, sample/hold thresholds0/.5, and slide2/4. The accumulator input vector is scaled by1/1024 before DSP, so no extra signal arithmetic is added to its patch.

The independent reference uses RNBO signal semantics and mathematical definitions; source equations can be reused without transferring another surface's execution evidence. DC, ramps, slide and available-history fsum/RMS averages have a predeclared `2e-6` numerical limit. Other models use exact dyadic/integer expectations and zero numerical tolerance. Operation zero signs are diagnostic. Sample/hold compares previous raw control against the current threshold. The downsample first-capture phase, strict opposite-nonzero zero-cross/initial0 rule and completed-window/held-report rule are explicitly declared where primary prose is less precise; discrepancies remain observations under those policies.

`delta~`, `sah~` and `slide~` were added to obtain fresh XIAO checks beyond earlier native-only coverage. Those earlier cases and known limits remain separate; these fixed modes do not supersede broader native observations. No reset, arbitrary modulation, alias, different vector size or one-frame ABI is inferred.

Default storage and resource behavior are preserved. Actual generated-resource preflight found two44,101-slot Float64 histories for each absolute/RMS program (705,616 payload bytes before overhead), with no DataRefs in the remaining programs. The batch uses a1 MiB structural module arena ceiling; capacity is not measured use. There is no buffer omission, precision change or storage optimisation.

Portable reference tests are in `tools/test_smoke_rnbo_signal_stateful_reference.py`. Ignored `build/research/rnbo-signal-stateful-smoke-v1` retains producer/resource/test records, and `build/hardware/rnbo-signal-stateful-smoke-modules-v1` retains actual module links. All15 exports/preparations and Xtensa links succeeded with zero imports. Hardware functionality, actual memory and callback timing are separate observations. Generated RNBO C++ stays private; compilation wall time is not DSP performance.

[XIAO hardware evidence](../../../../evidence/xiao-smoke-rnbo-signal-stateful.json)
records 14 passing cases and one `downsamp~` capture-phase mismatch across
153,600 checked output values. Absolute/RMS average workloads enter the CPU
review backlog. The two resource-backed programs each used 705,760 arena bytes;
default Float64 histories remain unchanged. This short scenario does not resolve
the broader native `slide~` numerical gap.
