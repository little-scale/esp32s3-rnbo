# Exact audio-delay conversion option

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

`--exact-audio-delay44100` enables the reviewed integer duration conversion in
one exact RNBO 1.4.4 `filters-signal` Main graph. It is off by default, keeps
`float32-strict`, and requires normal runtime fixes plus the explicit 40 ms cap.
Storage, filter arithmetic, interpolation, feedback and scheduler time retain
their original types and evaluation order.

```sh
node host/export/export.mjs tests/fixtures/objects/filters-signal.rnbopat \
  --out build/exports/filters-exact44100-NEW
python3 host/compiler/prepare.py \
  --export build/exports/filters-exact44100-NEW \
  --class-name rnbos3patch --role main --filter-delay-max-ms 40 \
  --exact-audio-delay44100 --out build/prepared/filters-exact44100-NEW
```

The option consumes each signal duration every sample. For already-materialized
binary32 values from positive zero through 40 ms at exactly 44,100 Hz, a 32-bit
integer calculation produces the original Double pipeline's Float32 result.
Negative values, negative zero, values above the cap and other helper fallback
inputs retain the original promoted-Double ternary, multiplication and return
rounding. The shared `mstosamps(MillisecondTime)` and scheduler remain unchanged.

The strict compiler route does not admit other rates, caps, graphs or option
combinations. In particular it rejects Float32 ring storage, other numerical
profiles and the current optimised drone. That drone already has its separately
qualified Float32 duration arithmetic; this option changes no drone code.

## Source, type and ownership guards

Admission checks the complete post-fix/post-cap 42-file source map, description,
runtime, processing methods, sample-rate writes and private ring ownership.
The generated baseline configuration is included in that map. Unknown or linked
files, repeated/partial transformations, source edits and unsupported options
fail before an output directory is published.

Inline compile contracts require binary32 RNBO samples, binary64 Double/time,
32-bit integer operations, standard Float32 evaluation and strict floating-point
compilation. The proof assumes nearest/even rounding. These compile checks do
not establish arbitrary runtime rounding-mode, exception, trap or NaN-payload
equivalence. Nonfinite whole-filter semantics remain outside qualification.
Exclusive process/event ownership, separate caller planes and internally owned
rings remain part of the contract.

The manifest records an explicit Boolean flag and versioned conversion contract;
provenance records the helper, methods, source inverse and complete input map.
The unchanged helper retains its earlier private-experiment filename/comment
for source identity; public admission is recorded by the new flag and metadata.

## Reused exact-image evidence

The actual public command was prepared and compiled on the computer. Its entire
64,376-byte, zero-import ELF is **byte-identical** to both the guarded prototype
and the physically measured private module:
`e026c4f9428145fec35084858616549785eba3dd00187471cb9dcb2da05066cb`.
Compiler, SDK, dependencies and private support archives also match. The new
compile assertions emit no additional operations or data. No new device run is
claimed by this admission.

A fresh export from the current installed generator also reproduces all
41 raw files and 43 admitted files, with identical manifest and provenance.

The [earlier four-case target comparison](exact-delay44100.md) therefore remains
evidence for this exact executable in that tested context: 3,145,728 compared
channel words have zero numerical float difference and exact PCM. Complete
callback time falls from 13,005,048 to 11,353,630 µs over 5,760 timed vectors per
profile, **12.70% less processing time**. These are whole Main callbacks,
including excitation objects; they exclude preparation, I2S, display and
networking and establish no live-player deadline bound.

That target record reports a 19,360-byte context per image and a 1,048,576-byte
selected arena with 131,392 bytes used in each version. Those memory costs are
unchanged; the candidate ELF grows by 304 bytes. Five C++ requests and ten total
arena requests occur during construction/preparation, with no observed running
allocation. Context size, arena reservation and actual high-water are separate
resource figures.

Original native Release and sanitizer proofs each check all 1,109,393,409
nonnegative binary32 encodings through 40 ms against stored Double and an
independent widened-integer rational oracle. Helper bytes are unchanged. Four
native patch cases compare 8,388,608 Float32/PCM words exactly. The fresh public
pipeline adds guard, CLI, failure-atomicity, type and composition checks; it does
not relabel those earlier exhaustive runs as new executions.

The [compiler admission record](../evidence/exact-delay44100-compiler.json)
binds the current public source/tests/preparation/module to that immutable
historical proof. The old [target record](../evidence/exact-delay44100.json)
remains unchanged. Other generated forms, rates, storage/profile compositions
and independent long-run/filter-domain checks remain separate work.
