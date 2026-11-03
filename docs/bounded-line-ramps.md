# Experimental bounded line ramps

`--bounded-line-ramps` is a default-off correctness option for the exact reviewed
RNBO 1.4.4 `line-timing` Main graph at 44,100 Hz/256 frames. It replaces the
Float32 absolute ramp timestamps and growing cancellation list with one bounded
segment, a UInt64 sample anchor and a short relative sample count. Audio values,
the increment and the inner loop remain Float32. The original Double duration
conversion and engine clock paths are retained.

```sh
node host/export/export.mjs tests/fixtures/objects/wave2/line-timing.rnbopat \
  --out build/exports/bounded-line-NEW
python3 host/compiler/prepare.py \
  --export build/exports/bounded-line-NEW \
  --class-name rnbos3patch --role main --bounded-line-ramps \
  --out build/prepared/bounded-line-NEW
```

The input must use normal fixes and `float32-strict`, with no other optional
transformations. Its complete 42-file source map, runtime, graph, description,
configuration, callers, setters, clock paths and ownership are pinned. Unknown,
partial or repeated transformations, aliases, other graphs/profiles and option
combinations reject atomically. Compile contracts check binary32 audio,
binary64 event/time types, UInt64/UInt32, SDK ABI 1.0, strict arithmetic and the
wrapper's fixed-list capacity 16. ABI/type assertions do not establish exclusive
ownership: that remains part of the reviewed opaque boundary-event execution
contract, with no concurrent processing/preparation or external state aliases.

The manifest keeps the strict base profile and adds an explicit Boolean flag
and versioned experimental correctness contract. This is a changed
implementation with changed rounding, not baseline bit identity. Preserve its
manifest, provenance, prepared source and complete ELF identity.

## State and timing policy

Only the authored two-item `[target, milliseconds]` pack route is admitted.
Target is hot, milliseconds is cold, and same-block command order and repeated
targets are preserved. Replacement overwrites bounded state rather than
accumulating expired same-time list triples. Arbitrary lists, additional line
instances, signal controls and broader reset/transport modes remain separate.

The original Float32 duration result is converted to a bounded integer expiry
count. Active age is checked as UInt64 before narrowing the proven short value
to UInt32/Float32. Durations of at most one sample use a causal one-sample path
without a reciprocal, avoiding tiny-duration overflow. Each block re-anchors the
Float32 value before its short accumulation loop. That deliberate numerical
change reduces the long-ramp error in the tested programs; it is not an
unchanged-output hoist.

Completion still schedules the existing clock once at the original next-vector
timestamp expression. It does not schedule a cancellation clock or flush an
already queued completion. The zero-to-zero startup ramp still completes.
Audio equality alone is not proof of completion timing.

## Native evidence and observability

Both the Double-timestamp alternative and the selected integer/relative
implementation pass the original 43 programs in O3 and UBSan builds. The
selected implementation removes the two observed ABI faults, has no observed
running allocations and produces byte-identical early/late tails in all ten
matched programs. Its largest independent ideal error there is about `6.95e-6`,
below the unchanged `2e-5` observation limit.

An additional [128 seeded programs](../tests/fixtures/objects/wave2/line-bounded-domain.json)
exercise more durations, neighbouring Float32 boundaries, targets, signed zero,
subnormal amplitudes, command orders and cancellation patterns. They all
complete without faults or running allocations, with byte-identical O3/UBSan
outputs/traces/statistics. Maximum ideal error is about `7.40e-6`.

Five of those programs expose an observability defect in oracle v1: a tiny
quantised signal can equal its target before its internal completion clock.
Oracle v2 retains every fixed amplitude, exact target-word and late target-hold
check. It qualifies an early-settling observation only when the ideal critical
sample differs from the target by more than the unchanged amplitude budget.
Otherwise it records early timing as unqualified. It never infers an internal
clock pass from output equality. The first report and v1 source are retained;
no native outputs were changed or rerun to make those observations pass.

Direct scheduling, dispatch and actual completion-bang observations separately
compare baseline and both alternatives in 12 focused programs plus two tiny
amplitude programs, each with reconstruction. Observer/plain controls retain
identical audio, PCM, normal traces and statistics. This covers those clock
programs, rather than qualifying every clock mode in the larger corpus.

The five original catalogue gates remain unchanged. Some corrected outputs
deliberately differ from the baseline, especially where the baseline timestamps
or tiny-duration handling were wrong. No blanket pairwise tolerance or bit
equivalence is claimed over the expanded domain.

## Compiled ESP32-S3 costs and remaining gates

Fresh public export/preparation and actual module builds reproduce the reviewed
complete images:

| Module | Entire ELF SHA256 | ELF bytes | Target context bytes | Loaded text bytes |
| --- | --- | ---: | ---: | ---: |
| Original | `7f267f52143239331166ac575218871728538228c321f7342d99182ec875f407` | 46,892 | 14,048 | 39,412 |
| Double timestamps | `345e705084e3ebf97346c73f7629d6bbc78b87c95714fd3d9e2372e0ba4edb04` | 45,324 | 14,096 | 39,340 |
| Integer/relative | `8ad0b7c3b3c92e90c8f9d1217c428c7cba8e75c9a42e9ccd773e0988ce90aa5f` | 44,448 | 14,096 | 38,524 |

All have zero imports and the same selected 4,096-byte arena descriptor. Target
contexts are compiled DWARF layout facts; native zero arena high-water does not
become a target heap measurement. The selected module is 2,444 bytes smaller
than the original while its context grows by 48 bytes.

Both alternatives keep Float32 inner loops. The Double alternative introduces
conditional Double re-anchor operations; the integer/relative alternative has
none there. Static callsites are not invocation counts or CPU measurements.
Relative timing also avoids a separate finite fractional-timestamp horizon of
absolute Double addition. The parent engine's Double clock and counter-wrap
limits remain; this is not an unbounded whole-scheduler precision claim.

The [sealed compiler evidence](../evidence/bounded-line-ramps.json) binds the
public pipeline, complete images, native programs, oracle revisions and
independent reviews. No line image in this record has executed on ESP32-S3.
The option therefore remains **experimental**, with partial working status and
no performance percentage. Hardware output, resource and timing tests remain
before promotion. The [original fault record](line-timing-modes.md) remains
unchanged and the default strict implementation retains that baseline behaviour.
