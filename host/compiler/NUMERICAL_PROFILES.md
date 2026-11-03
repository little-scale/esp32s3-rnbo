# Optional cycle coefficient profile

`prepare.py` defaults to `--numerical-profile float32-strict`. The experimental
`--numerical-profile float32-cycle-v1` adds an `f` suffix to exactly two constants
inside each admitted RNBO 1.4.4 scalar-frequency, fixed-256 `cycle~` kernel:

* Fraction interpolation multiplier `3.81471181759574e-6`.
* Phase output multiplier `0.232830643653869629e-9`.

The complete reviewed kernel is checked after masking comments and C++ string
and character literals. Unrecognized kernels, altered coefficients, missing
kernels, and other runtime versions stop preparation. The profile changes no
integer phase arithmetic, truncation, table lookup/interpolation algorithm,
buffer representation, scheduler, or double-precision clock. Original generated
source and runtime remain under `originals/`. Provenance records each source
hash, kernel count, and literal-suffix count separately from runtime fixes.

```sh
python3 host/compiler/prepare.py --export build/exports/sine \
  --class-name rnbos3patch --numerical-profile float32-cycle-v1 \
  --out build/prepared/sine-cycle-experiment
```

Prepared strict/optional variants have the same **raw** `source_tree_sha256`.
Their prepared source hashes, manifests, numerical profile names, and resulting
artifact identities distinguish them. Use the complete manifest and ELF identity
when comparing firmware; the raw input identity alone does not select a profile.

`compare_profiles.py` accepts separately built strict/optional host renderers,
requires matching raw source, runtime headers, SDK/integration source, compiler,
and build settings, then records quantitative float32 and PCM differences:

```sh
python3 host/compiler/compare_profiles.py --fixture sine \
  --strict-renderer PATH_TO_STRICT_BUILD/rnbo_render \
  --optimized-renderer PATH_TO_OPTIONAL_BUILD/rnbo_render \
  --out build/profile-comparison-NEW
```

Its declared limits are maximum absolute float difference `2e-6` and maximum PCM
difference one signed-16-bit LSB. Reports include actual maximum and RMS error,
changed samples, exact byte identity, signal frequency/RMS checks, and complete
build reports. The authored sine and MIDI1/2/4 forms are qualification fixtures;
other RNBO forms need their own comparison. Host timing does not establish an
Xtensa speed improvement, and this profile remains optional until target
measurements support it.

The separately named `float32-cycle-v2`, `float32-audio-v1` and
`--float32-delays` options are described in
[the float32 audio profile notes](../../docs/float32-audio.md). Their broader
method catalogs and measured audio differences do not change v1 admission or
its comparison limits. Strict remains the default.

The separate [`float32-scalar-powers-v1` profile](../../docs/scalar-powers.md)
admits only the whole-source/runtime-pinned nonlinear FX fixture. It deliberately
changes power rounding, supports the reviewed finite-wrap composition, and has
its own native and board evidence. Its results do not extend cycle or audio
profile admission.

The separate [`--exact-audio-delay44100` option](../../docs/exact-delay44100-compiler.md)
keeps `float32-strict` and records an explicit manifest flag and versioned
conversion contract. It reproduces the reviewed Double conversion's Float32
return in one pinned signal-delay graph; strict profile name or raw source hash
alone does not identify whether this optional implementation was selected.
Retain the complete manifest, prepared source and ELF identities.

[`--hoist-filter-durations`](../../docs/filter-duration-hoist-compiler.md) also
keeps the strict profile and uses its own explicit manifest flag and versioned
contract. It retains Double evaluation and the original Float32 return while
hoisting only the reviewed scalar conversions. This is separate from the
per-sample exact signal-delay option; the two cannot be combined.
