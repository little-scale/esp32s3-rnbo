# Scalar filter-duration hoisting

`--hoist-filter-durations` is a default-off option for the exact reviewed
RNBO 1.4.4 `filters-scalar` Main graph at 44,100 Hz/256 frames. It requires
normal runtime fixes, `float32-strict` and the explicit 40 ms cap.

```sh
node host/export/export.mjs tests/fixtures/objects/filters-scalar.rnbopat \
  --out build/exports/filter-hoist-NEW
python3 host/compiler/prepare.py \
  --export build/exports/filter-hoist-NEW \
  --class-name rnbos3patch --role main --filter-delay-max-ms 40 \
  --hoist-filter-durations --out build/prepared/filter-hoist-NEW
```

The scalar duration is copied by value for each render call. Its conversion
and invariant clamp use the same Double expression and Float32 return as the
reference, evaluated once per vector. Three original comb statements and two
allpass statements move verbatim before their fixed 256-frame loops. Remaining
state-dependent ring clamps, reads/writes, interpolation, feedback and precise
scheduler time retain their original order and types.

Signal-rate durations stay per-sample and are rejected by this option. Fixed,
Float32-storage, audio-v2 and drone contexts are also outside this admission.
The current drone has two signal-driven comb delays. This option cannot be
combined with the separate exact signal-delay conversion or other optional
adapters/profiles. It changes no drone firmware.

## Source and execution contract

Admission pins the entire 42-file post-fix/post-cap source map, including the
baseline configuration, authored graph, description and all 36 runtime headers.
It checks scalar signatures, complete callers/setters, two sample-rate writes,
private Float64 ring ownership and unchanged ring helpers. Unknown or linked
files, aliases, edits, partial/repeated changes and unreviewed compositions
reject before an output directory is published.

Compile contracts require binary32 RNBO samples, binary64 conversion/time and
strict floating-point compilation. The reviewed execution contract uses
nearest/even rounding, exclusive process/event ownership and caller planes
separate from private state. Concurrent preparation, external resource
replacement and floating-environment/trap/NaN-payload equivalence are not
qualified. In particular, fewer evaluations change when exceptions could be
observed even though the numerical result is preserved.

The manifest keeps `float32-strict` and adds the explicit Boolean flag plus a
versioned contract. Provenance records full source inverses, original moved
statement hashes and helper/runtime/ownership pins. Retain these records and
the ELF hash; the raw source hash and strict profile name alone do not select
the optional implementation.

## Exact-image reuse and measurements

Fresh exports and actual public CLI preparations reproduce the reviewed
reference and guarded candidate. The new complete module images match the
previously measured pair exactly, with the same compiler, SDK, dependencies,
private archives and state policy:

| Module | Entire ELF SHA256 | Bytes |
| --- | --- | ---: |
| Reference | `7117c0ccd9b0b9342b8e18f1e7d75741e60e582c77d2549350f52331a414fa9d` | 55,172 |
| Optional | `e24f0298e3927c8824c6144344503c415dbc854982cfea0c3a6089046ef23468` | 55,172 |

This refresh uses the current defined-Math runtime. The earlier private source
used an older runtime; it was not restored to force a hash match. The runtime
correction and new compile assertions leave these complete executable images
unchanged. No new hardware execution is claimed.

The [saved three-case comparison](../evidence/filter-duration-hoist.json)
therefore remains evidence for this exact pair: 2,359,296 compared channel words
have zero numerical Float32 difference and exact PCM. Total callback time falls
from 7,503,863 to 5,325,609 µs over 4,320 timed vectors per profile: **29.03% less
processing time**. Per-case reductions are 31.36% for impulse, 21.89% for minimum
delay and 32.79% for maximum delay. The complete Main callback includes unchanged
excitation and both filters; no isolated-object or live-player deadline claim
follows. Preparation/events, I2S, display and networking are outside the timer.
Three alternating rounds use 512 blocks per case, four warmup blocks and the
same seed; timing excludes the first 32 blocks while comparisons retain every
sample.

Both target images use a 15,136-byte context and a selected 1,048,576-byte arena
with 65,792 bytes high-water. Four C++ requests and eight total arena requests
occur during preparation; no running allocation is observed. Aligned text grows
by 36 bytes, while total ELF length remains unchanged. This is a processing-time
option, with no measured arena saving.

Current-runtime native comparisons cover 18 workloads and 12,582,912 Float32/PCM
words, including the previous 14 scalar cases plus cold and long-tail cases.
Outputs/readbacks match exactly, with healthy pause/reconstruction and no
observed late C++/Platform allocations. Those extra native cases do not become
new hardware timings or complete filter-domain coverage.

The [public compiler admission record](../evidence/filter-duration-hoist-compiler.json)
binds the current pipeline, tests and image comparison to the unchanged
historical record. Other generated forms, gains, rates, resource interfaces and
option compositions remain separate work.
