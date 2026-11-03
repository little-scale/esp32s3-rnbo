# Compiler correctness fixes and optional optimisations

Preparation still defaults to `float32-strict`. The normal correctness-fix
profile now also defines the reviewed 32-bit integer wrap operations. Cycle
conversion hoisting and compact average history are separate, default-off
flags. All three adapters require reviewed RNBO 1.4.4 forms and record their
source/runtime guards and changes in provenance.

The subsequent [pink output option](noise-float32-normalisation.md) adds an
independently qualified default-off Float32 scaling change for the exact
authored 16-row noise graph. It retains the strict base profile and seed/time
behavior; its manifest flag records the selected transformation.

The [scalar-power numerical profile](scalar-powers.md) separately admits one
exact nonlinear FX graph, optionally after the finite-wrap correction. It
changes rounding for exponents 2, 4 and 0.25 and retains the original fallback
for every other scalar exponent. Fresh native and target comparisons preserve
the declared accuracy gates; the strict default remains unchanged.

The [exact signal-delay conversion option](exact-delay44100-compiler.md) retains
strict arithmetic identity in the reviewed 44.1 kHz/cap40 Main graph, replacing
only the two per-sample duration conversions with their exact integer route.
The public build reproduces the entire previously measured module; the older
12.70% callback observation is reused for that exact image, with no new device
execution claimed.

The [scalar filter-duration option](filter-duration-hoist-compiler.md) moves the
original Double calculation outside sample loops without narrowing it. This
separate strict cap40 scalar context reproduces both modules from the older
29.03% callback comparison using the current corrected runtime. It is off by
default and rejects signal/fixed/storage/profile compositions.

| Selection | Default | Effect and admission scope |
| --- | --- | --- |
| Defined integer wrap | On with normal runtime fixes | Replaces the reviewed `rnbo_imul` signed product with defined modulo 2^32 arithmetic and a safe signed mapping. Matching pink-noise generators also receive a defined unsigned affine multiply/add. Other signed arithmetic is outside this fix's claim. |
| `--hoist-cycle-conversions` | Off | Caches original scalar/fixed `uint32_trunc` expressions once per 256-frame vector. Exact known signal-rate forms remain unchanged and record skipped conversions; unknown forms reject preparation. |
| `--compact-average-history` | Off | Admits one exact authored two-channel `average~ 64` graph with scalar window 1..64. Replaces its two 44,101-frame Float64 histories with 65-frame Float32 histories. Other graphs and bounds are rejected. |

`--no-runtime-fixes` retains the original runtime for controlled reference
builds, including the original integer implementation. It disables the integer
fix as well as the existing list/clock fixes. It is not required to select a
strict numerical profile. Pink's original seed policy is retained by the new
integer fix; this change does not promise a new deterministic-seeding policy.

## Use

Use a raw Minimal Export and a fresh output directory. For the reviewed scalar
cycle fixture:

```sh
node host/export/export.mjs tests/fixtures/objects/cycle-scalar.rnbopat \
  --out build/exports/cycle-hoist-NEW
python3 host/compiler/prepare.py \
  --export build/exports/cycle-hoist-NEW \
  --out build/prepared-cycle-hoist-NEW \
  --class-name rnbos3patch --role main \
  --hoist-cycle-conversions
```

The same flag can follow an admitted numerical profile, such as
`--numerical-profile float32-audio-v2`. Hoisting retains that profile's exact
literal spelling, macro conversion, UInt32 cast and rounding. The scalar phase
conversion stays conditional before the loop, and the original in-loop branch
remains. This uses no alternative unsigned-conversion helper. In the actual
drone, both comb delays are signal arrays, so their per-sample millisecond
calculations remain unchanged.

For the exact authored average fixture:

```sh
node host/export/export.mjs tests/fixtures/objects/wave2/average-window.rnbopat \
  --out build/exports/average-window-NEW
python3 host/compiler/prepare.py \
  --export build/exports/average-window-NEW \
  --out build/prepared-average-compact-NEW \
  --class-name rnbos3patch --role fx \
  --compact-average-history
```

This option includes both the reviewed capacity and storage changes; a separate
`--float32-delays` flag is unnecessary. It needs the standard corrected runtime
and therefore does not combine with `--no-runtime-fixes`. It is not a general
maximum-window inference rule or an average accuracy correction.

Compact history preserves DataRef indices and positive allocation/update
notifications, but changes resource size/type. The manifest declares the opaque
resource contract and modified semantics. Generated `patch_config.h` requires
the SDK ABI header first and accepts exactly C ABI 1.0. Generic RNBO resource
inspection is outside that contract. The same shared gate covers optional
[mtof-table omission](unused-mtof-table.md); currently admitted contexts do not
imply every combination of optional flags is supported.

## Evidence and limits

Native integer tests check defined products and pink recurrence against an
independent widened-integer oracle, including edge cases and 200,000 random
steps, with UBSan. They also demonstrate that fixing only multiplication leaves
the original pink addition overflow. This establishes the tested integer paths;
it does not establish that every generated expression is overflow-free. The new
adapter's target noise comparison subsequently passed 786,432 finite sample
words with zero numerical float difference, exact PCM and recovered memory.
That result establishes stream preservation in its tested clock/seed context;
it makes no CPU gain claim.

The cycle helper reproduces the measured private candidate source bytes exactly.
Native strict/v2 scalar tests covered 30 workloads and 7,864,320 float/PCM words;
the actual-drone tests covered six workloads and 12,582,912 words, including
parameter changes. Outputs were byte-identical. The separate
[scalar-cycle target records](../evidence/cycle-invariant-hoist.json) and
[whole-drone target record](../evidence/drone-invariant-hoist.json) observed zero
numeric float difference and exact PCM under their stated offline workloads.
These are private-prototype observations and do not establish a universal timing
bound or automatic hardware qualification of every newly prepared image.

The integrated compact-average native report compares 3,407,872 float-channel
words and corresponding PCM words with exact output identity; the static wrapper
reports 544B through its Platform hooks. Separately, the earlier four-variant
private memory proof covered 13 workloads and 39 paired renders. Its lifecycle
tests reconstructed each variant 16 times; the compact dynamic arena used 736B,
including two C++ view allocations, within a 4KiB budget. These dynamic counts
exclude module code, caller-owned opaque context and loader memory. The known
running-sum accuracy limitations remain. Target comparison of windows 1/16/63/64 subsequently passed
3,145,728 output comparisons and 6,291,456 independent model checks. Dynamic
arena use, including C++ requests, fell from 705,760 to 672B on the ESP32.
Total callback time fell from 3,340,755 to 1,832,921µs over 5,760 timed vectors,
about 45% in that workload. Those four cases do not correct or qualify the known
cancellation error. A separate target control using the identical compact module
passed all four windows and model checks with a 4KiB reservation: 672B used,
12,912B opaque context and 17,008B total caller binding. This establishes the
tested smaller reservation; it makes no additional processing-speed claim.
A smaller high-water mark releases physical memory only when the caller also
reduces its reserved arena.

The target window63 cancellation diagnostic retained the known numerical failure.
Strict and compact outputs matched numerically with exact PCM over 786,432 words,
but their maximum output/cache error was approximately 2.41399e-6. Allowing for
the cache/model rounding bound gives a true supplied-model error of at least
2.39951e-6, above the unchanged 2e-6 limit. The old runner stopped during the
failure line; the sealed record uses the preceding complete semantic result and
its model bound, without claiming a complete final failure condition. The
instrument was restored.

Float64 history reads promote the original `accum -= history[...]` subtraction
to double; Float32 history makes that intermediate float. The arithmetic source
statements and accumulator field type are preserved, but intermediate precision
does change. Identity is established for the tested normal workloads. The later
[standalone target corner diagnostic](float32-corners.md) observed no tested
finite-result differences in either ROM or private-module arithmetic closures;
it retains NaN sign and exception-status differences. No all-domain bit-identity
claim follows from this bounded corpus or the host/workload results.

The integrated static drone also completed 300 playing polls over 304.43 seconds
with a 128KiB arena, using 99,088B. Its observed mean was 3,884.35µs/vector,
playing peak 4,972µs and final peak counter after Panic 4,984µs, with zero fault
counters. Output volume was zero while DSP, I2S and the UI were active; networking
was inactive. This is live health evidence, separate from the offline waveform
and timing comparisons, with no universal deadline guarantee. The
[consolidated evidence](../evidence/compiler-optimisations.json) seals the native,
target comparison, reservation, retained numerical failure and live records.

Preparation applies the existing runtime fixes, then exact-context average
compaction, then the integer fix. Delay/storage and numerical adaptations
precede cycle hoisting; optional mtof omission follows it. Manifest resource
semantics are merged, and source/provenance plus native/module build reports
capture compiler-helper hashes (eight with the subsequent pink-output adapter).
Failed admission publishes no prepared
output. Five end-to-end integration tests cover the golden drone/average source,
default integer fix versus raw reference, ABI negatives and failure atomicity.
