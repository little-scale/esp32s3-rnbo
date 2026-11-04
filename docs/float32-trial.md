# Float32 Trial: try first, retain evidence, review later

Select **Advanced build settings → Arithmetic profile → Float32 trial —
unverified kernels** in RNBO Studio. Compile normally. Trial starts with the same
reviewed conversions as Auto, then attempts additional generated DSP methods
without requiring their algorithm fingerprints to be in the reviewed catalog.

Auto remains the default. Standard arithmetic and existing explicit profiles
remain available. Trial is an experiment: a successful compile, finite output
or fast device callback does **not** mark an object or operation verified.

## What it attempts

The additional pass appends `f` to unsuffixed decimal floating literals inside
eligible generated DSP methods. This can keep expression arithmetic in Float32
and select RNBO's Float32 math overloads. It does not rewrite algorithms or
globally narrow C++ types. A named method fingerprint is recorded, not admitted
to Auto automatically.

The v1 classifier starts with `_perform` methods whose signatures contain signal
buffers, then follows named generated helper calls. Extra changes must belong to
an object-specific generated prefix such as `dspexpr_01` or `codebox_tilde_01`.
This includes eligible Gen-generated signal code, but does not claim support for
every Gen operator, state layout or generated form.

The trial pass preserves:

- Setup, event and scheduler methods; shared generated math/interpolation helpers.
- Visible clock types/state and calls to time-sensitive generated helpers.
- Explicit double/Float64/64-bit time state and methods that visibly depend on it.
- Methods also reached from setup/event roots, and ambiguous generated overloads.
- Integer literals, types, buffer allocation/storage and shared RNBO runtime files.

Methods with no suitable literals are recorded as skips. Other skips include
unclassified signatures, explicit double/time dependencies and shared helpers.
The classifier is deliberately conservative and is **not a complete C++ type
checker or call graph**. Some double operations remain, and some patches may fail
to compile in Trial. An integer-based math overload, for example, is not repaired
by merely suffixing decimal literals. There is no automatic retry in a different
profile when Trial fails.

Delay storage and comb capacity remain separate explicit choices. Trial inherits
Auto's already reviewed conversions; its extra pass does not change the timing
or storage types of an unreviewed method.

## Checks and downloadable logs

For each successful Studio Trial build:

1. Export and prepare the original patch with a source/manifest identity.
2. Build the Trial renderer and run **1,024 × 256 stereo frames**, about 5.94 s of
   audio, at default parameters, after four warmup blocks with seed 305419896.
   Errors, nonfinite samples or late platform allocations reject this screen.
3. Build a separate reviewed **Auto reference** with matching voices, arena and
   delay choices. Render the same startup scenario and compare actual Float32
   captures and PCM WAV output.
4. Record maximum absolute error, error RMS, level RMS and maximum PCM difference.
   The 2e-6 sample / 1 PCM-LSB diagnostics are recorded as passes or failures.
   A failed numerical diagnostic remains in the report; it does not silently
   turn an experimental comparison into verification or hide the package.
5. Compile the native Xtensa package. The normal player startup/CPU admission
   remains in effect when it is uploaded.

The result is labelled **Experimental · unverified**, and offers **Download trial
report**. The report contains:

- RNBO version, source identities, role, voices, sample rate and block size.
- Each changed method's normalized kernel fingerprint, full input/output method
  hashes, signature, line numbers and exact literal replacements.
- Reviewed Auto conversions and every classified extra-pass skip with its reason.
- Native comparison settings/results and any failed numerical diagnostics.
- After an upload: a short runtime observation with firmware/package identities,
  render/peak time, audio CPU percentage and reported fault/allocation counters.
  A peak at or above 80% of the block budget is flagged for later CPU review.
  CPU-admission failures are recorded too, without claiming the patch ran.

Post-upload observations are **runtime smoke evidence**, not captured-output or
sample-accurate correctness evidence. They are not per-object CPU benchmarks or
an all-parameter/worst-case timing guarantee. Native render wall times are not
used as ESP32 performance measurements. Network credentials are excluded from
the runtime report.

Studio stores the full combined report in its build directory as
`build/private/studio/<job>/trial-review.json`. The immutable transform audit is
`prepared/float32-trial-audit.json`, covered by the preparation integrity map.
Downloads remain available during the current Studio session; the files remain
on disk after a restart.

## Saved packages keep the experimental label

The `.rnbopkg` contains a checked `float32_trial` summary with the audit SHA256,
method counts and fixed `unverified` status. Studio's compiler adds
**`[Float32 trial]`** to the package's display name, so existing player firmware
also makes the experiment visible in its running Main name. No player firmware
update is needed for this arithmetic mode.

Opening a saved trial package preserves its experimental label. The full report
and audio captures are separate build artifacts, not embedded in the package;
an imported package therefore does not fabricate a detailed audit or device
test history. Keep the downloaded report with the package when comparing trials.

CLI preparation uses:

```sh
python3 host/compiler/prepare.py --export RAW_EXPORT --out NEW_PREPARED \
  --class-name rnbos3patch --role main --numerical-profile float32-trial-v1
```

CLI preparation creates the transform audit and manifest summary. The automatic
reference render and combined downloadable review are Studio build steps, not a
claim made by preparation alone. Module compilation and packaging otherwise use
the usual commands.

## Using logs to expand the reviewed list

Yes: the logs are intended to make later review faster. They identify exactly
which generated form changed, what was edited, which context was tested, what
outputs differed and whether CPU needs further work.

Promotion remains a deliberate review step:

1. Reproduce the method with the pinned generator and inspect the complete
   algorithm, state and precision requirements.
2. Check representative outputs against an independent expected result, including
   relevant boundaries, control changes and sample-by-sample state.
3. Capture/compare device outputs where needed and record CPU costs separately.
4. Add the exact reviewed form, regression fixture and scoped evidence to the Auto
   catalog and object-status data. Retain any failures and numerical differences.

A whole-patch comparison with Auto is useful evidence, but Auto itself is not an
independent oracle for an unknown object's semantics. Trial logs never update the
verified-object count or the reviewed catalog automatically. The separate RNBO/
Gen hardware-qualification goal remains paused unless explicitly resumed.

## Implementation checks

The initial [evidence record](../evidence/float32-trial-v1.json) includes two full
Studio builds:

- **EEE:** two additional methods attempted, 14 Auto methods retained, 26 classified
  skips. Its 524,288-sample default capture and PCM were identical to Auto in this
  short scenario. The final native module was also identical; no speedup is claimed.
- **Filter example:** four additional methods attempted with dynamic resonance.
  Maximum native difference was **2.1532177925109863e-6**, error RMS
  **1.7958587246990774e-7**, and PCM difference **1 LSB**. The sample-error diagnostic
  failed; the PCM diagnostic passed. That failure is retained in the report.
  The package passed player admission and short runtime checks on XIAO, with
  recorded CPU/counters and no captured-output correctness claim.

The [original filter example](../examples/float32-trial-filter.rnbopat) can be used
to exercise the workflow. Its test package started at 0% volume. Reviewed EEE was
restored after the temporary hardware test, with the user's then-observed 41%
volume and note 39. The board was subsequently released for the user's player
firmware installation; physical-input wiring tests remain separate.

The full compiler suite passed **524 tests**. The focused seven-test Trial suite
also passed, including an additional native Gen render checked against an
independently calculated Float32 constant. Studio passed **95 tests**, and the
frontend passed **24**. None of these checks automatically promotes a method.
