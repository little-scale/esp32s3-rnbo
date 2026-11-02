# Original object qualification patches

These flat RNBO patches are original MIT-licensed test graphs, not copies of
generated RNBO source. `catalog.json` declares their parameters, deterministic
workloads, semantic observations and explicit numerical comparison tolerances.

The first three fixtures isolate the costly drone objects:

* `mtof-varying`: a sine varies MIDI pitch around60. Default depth12 and the
  fast boundary depth24 exercise changing exponential inputs each sample;
  depth0 tests the cache. Left exposes the exact pitch divided by128, right
  exposes converted frequency divided by2048. The scales are exact powers of
  two and stay fixed during tests.
* `saw-signal`: a signal inlet drives the saw. Left exposes its audio at a
  parameterized level, right exposes phase. Tests measure phase increments,
  fundamental and low-frequency harmonic proportions, DC and silence.
* `reson-modulated`: a sine provides excitation while a second sine modulates
  center frequency around a parameterized offset. Left exposes input, right
  exposes filtered output. A static-center case checks the independently
  derived transfer magnitude. A silence event permits filter state to decay.

Other families cover cycle fixed/scalar/signal inlets, linear scaling,
comb/allpass fixed/scalar/signal delays, ordinary delay crossfade and arithmetic
DC boundaries. The filter graphs trigger a fresh unit impulse with a parameter
event after warmup. Ordinary delay values are samples; filter caps are
milliseconds. Their meanings must not be interchanged.

Run a fresh host qualification:

```sh
python3 host/compiler/qualify_objects.py \
  --only mtof-varying,saw-signal,reson-modulated \
  --profiles float32-audio-v1 --out build/object-qualification/NEW
```

The runner exports with the installed version-checked RNBO1.4.4 generator,
prepares strict and selected optional variants, builds matching Release
renderers, and saves float/PCM outputs plus identity-bound reports. It refuses
an existing output directory. Unsupported exact profile guards are recorded as
`unsupported-form`; this does not qualify an optimization for that form.

All cases recreate context with the same seed, warmup and input graph. Reports
distinguish semantic checks from strict/optional output comparisons, and list
RNBO Platform arena/allocation observations. These hooks do not establish
complete C++ allocation coverage. Host timing does not establish board cost.
No board access, flashing or installation is performed by this runner.

The Main fixtures include their authored excitation/observation nodes in timing;
their measured deltas describe the complete fixture. They cannot establish a
cost exclusively attributable to one method. A separate `catalog-fx.json`
isolates the same priority objects with external signals and no cycle object:

| Fixture | Input1 | Input2 | Output1 | Output2 |
| --- | --- | --- | --- | --- |
| mtof-fx | MIDI60+depth*sin(2*pi*rate*t) | .125*sin(2*pi*371*t) | Input2 | mtof(Input1)/2048 |
| saw-fx | frequency+depth*sin(2*pi*rate*t) | same pilot | .2*saw(Input1) | Input2 |
| reson-fx | .2*sin(2*pi*excitation*t) | center+depth*sin(2*pi*rate*t) | Input1 | reson(Input1,Input2,.95) |

The per-case stimulus entries override the fixture defaults; time is the
zero-based rendered frame index divided by44100 after the zero-input warmup.
Input samples are rounded to IEEE float32 before processing. Both variants use
the same saved input file and its hash is verified. Native and target stimulus
generators must implement the same contract, but cross-platform transcendental
rounding does not imply identical input bytes between platforms.

```sh
python3 host/compiler/qualify_objects.py \
  --catalog tests/fixtures/objects/catalog-fx.json \
  --profiles float32-audio-v1 --out build/object-qualification/FX-NEW
```

`fx_probe.cpp` is an original MIT host test harness using the established C ABI.
It reads an exact bounded stereo float input, rejects truncated, oversized or
non-finite input, and emits the same float/PCM proof format. The qualifier links
it to each matching native SDK library and records compiler flags, source,
library, executable and build-report hashes. The general native renderer's
default440/660Hz input is not used for these FX pitch/filter tests.
