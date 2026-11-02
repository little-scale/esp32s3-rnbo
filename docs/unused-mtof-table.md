# Optional unread mtof lookup payload omission

`--omit-unused-mtof-table` is an explicit, default-off preparation option for
reviewed RNBO1.4.4 direct-exponential `mtof~` forms. It requires the current
module C ABI, which exposes no DataRef resource API. It does **not** preserve
general RNBO resource inspection or resource-notification semantics.
Generated `patch_config.h` enforces the reviewed C ABI1.0 at compilation:
missing SDK ABI macros or any other major/minor version are errors. This covers
native, dynamic, static firmware and manual builds without changing the SDK.

```sh
python3 host/compiler/prepare.py \
  --export build/user-patches/3sawsDrone3/export \
  --out build/user-patches/3sawsDrone3/prepared-NEW \
  --class-name rnbos3patch --filter-delay-max-ms 40 \
  --float32-delays --numerical-profile float32-audio-v1 \
  --omit-unused-mtof-table
```

The admitted generated forms allocate a shared65,536-sample float table named
`RNBODefaultMtofLookupTable256`, but their audio conversion calls the direct
exponential helper. Every named mtof buffer reference is accounted for:
declaration, construction, view refresh, initial capacity, sample rate and
allocation. Scala helpers do not read this buffer. The flag changes only the
matched initial requests from65,536 to0 samples. It retains resource names,
indices, types, view objects and declarations; it removes the payload's
allocation and fill. The zero-request branch also suppresses that resource's
initialization `DataRefUpdate` event. These resource/event changes are recorded
explicitly in the manifest and provenance.

The guard requires exact reviewed DataRef and raw/fixed MinimalEngine runtime
hashes, direct-exponential helper and filler hashes, complete DataView callback
hashes, both time-update overloads and their clock helpers. It currently admits
the isolated FX mtof fixture, the authored Main mtof fixture and the actual
drone callback layouts. All table/view symbol references and metadata aliases
must match the reviewed forms. Indexed DataRef calls, member-pointer aliases,
new readers, lazy resizes, changed callbacks and other forms stop preparation.
Other layouts need their own review. This is conservative admission for these
generated forms, not a general C++ dead-code analyzer or a sandbox.

Zero samples follow the reviewed runtime's no-allocation path. A one-sample
replacement is deliberately avoided: the existing filler divides by
`bufsize-1`. No arithmetic, phase, tuning, cache, delay, frame-counter or clock
source is changed by this option.

The private reference/prototype investigation tested four exact source
variants: strict/f32 isolated FX mtof, f32 Main mtof and the f32 cap40 drone.
All12 workloads produced identical float outputs; three drone cases rendered
4,096blocks each. They were finite, with zero errors or late Platform
allocations. Separate static and real dynamic-wrapper native tests exercised
16 lifecycles/reconstructions per variant,128blocks each, parameter minimum,
normalized maximum, restore and Panic. Both C++ and RNBO Platform late counters
remained zero. Native lifecycle stubs do not qualify ELF constructors/unload.

| Measured arena use | Reference | Omitted table |
| --- | ---: | ---: |
| Isolated FX mtof, static Platform arena | 262,224B | 72B |
| Main mtof, static Platform arena | 327,768B | 65,616B |
| Drone, static Platform arena | 361,240B | 99,088B |
| Drone, dynamic arena including C++ requests | 362,448B | 100,288B |

The payload saving is262,144B; allocator overhead explains the different arena
deltas. C++ view construction counts are unchanged. These are **used/high-water
reductions**: a caller that still reserves a1MiB arena still reserves1MiB. A
smaller explicit arena needs separate admission and qualification.
The private native dynamic-wrapper test also passed a128KiB arena/bound-region
budget with16reconstructions, parameter boundaries and Panic. The drone used
100,288B of that arena; this establishes native budget feasibility, not target
heap availability. Its report is `tight-budget.json` beside the other evidence.

An independent instrumented native trace compared all four pairs with fresh
contexts, pre-audio parameter changes, later edits and a fractional-time queued
event. Filtering exactly the omitted table notifications/events left identical
other traces, exact double engine/patcher times and audio bytes. It establishes
those tested traces; it does not establish unchanged queue contents, generic
RNBO scheduling equivalence or target timing.

Investigation evidence is under `build/research/mtof-table-zero/`:
`audit.json`, `comparison.json` and `lifecycle.json`. Independent event traces
are under `build/research/mtof-event-trace/trace-proof.json`. The original
exports and previously qualified drone variants remain intact. Target resource
and timing results are recorded separately below.

The final reviewed preparation is
`build/user-patches/3sawsDrone3/prepared-cap40-f32audio-no-mtof-table-v2`.
`final-comparison.json` repeats all three4,096-block drone workloads with
matching final compiler/integration identities. The reference and candidate
(at both1MiB and128KiB static arena budgets) have identical float and PCM hashes;
candidate Platform arena use is99,088B. Its runtime primitive test also passed.
The fresh dynamic module/report is under
`build/modules/3sawsDrone3-cap40-f32audio-no-mtof-table-v2/`, with zero imports and
ELF SHA256 `51d42f3e8d9d316f5eb8ce688804ddc04ac639b96dc4df561a68e2a53809571c`.

## Target resource and setup observations

The isolated direct-input mtof FX fixture was tested on the AMOLED V2 with
strict arithmetic in both modules; the candidate adds only table omission.
Three cases (cached pitch, continuous pitch and fast/deep modulation) each ran
three alternating-order passes per profile, 512 vectors per pass, four warmup
vectors and seed 0x12345678. All 2,359,296 compared float values had zero numerical
difference and all PCM words matched. The comparator checks numerical float
equality, not signed-zero/NaN bit-pattern equality; the separate native drone
output files provide the byte-identity evidence described above.

| Observed target quantity | Strict | Omitted table |
| --- | ---: | ---: |
| Dynamic arena high-water, including C++ requests | 262,288B | 128B |
| Total create/prepare time across nine contexts | 6,258,779µs | 6,682µs |
| Mean create/prepare time per context | 695.420ms | 0.742ms |
| Total process time across 4,320 timed vectors | 7,213,192µs | 7,212,512µs |

The preparation timer covers module create and prepare, including detached
warmup. It excludes ELF loading, relocation and BIND, which occur before this
timer. The process-time difference is ordinary measurement variation; table
omission establishes no audio-processing speedup. There were zero running host
heap operations or module-local late requests, all four loaded images finalized,
and the observed PSRAM/internal free memory returned to its baseline. I2S, UI
and networking were inactive in this isolated comparison.

The actual drone was also qualified separately with a 128KiB static arena.
It remained active for 300 status polls over 304.270 seconds at zero output
volume, with I2S and the patch UI active. Arena use was 99,088/131,072B,
leaving 31,984B. Reducing the previous 384KiB reservation to 128KiB increased
observed free PSRAM from 7,866,044 to 8,128,188B, exactly 262,144B. This is a physical
reservation saving, distinct from the allocator high-water measurements.

The observed owner-through-PCM render mean was 3,941.24µs/vector and peak 5,045µs;
driver wait and post-write capture are outside that metric. Deadline overruns,
module/nonfinite/queue/driver faults, late allocations and audio-task heap
operations remained zero. These are observed healthy-run values, not a
worst-case timing bound or a controlled timing comparison with the prior drone.
The live output was silent and was not captured for waveform equivalence.
After qualification and the isolated fixture test, the tableless drone was
restored with the latest user controls, Panic active, volume 7 and ready to
Resume. Oscillator phase continuity across reconstruction is not claimed.

The sealed [omission evidence](../evidence/mtof-table-omission.json) binds the
native output/lifecycle/event traces, target build and serial records, live
status log and installation script. Its SHA256 is
`af5cb8982459374ff12610e66b70dd7a180c229b78182c21f4ad3d782ee50af7`.
The live firmware ELF SHA256 is
`00452e66d6e1d2d6b166e7993f40d2a99e4f64534fd13fde0bef4e1e0fa6920f`.
The omission option remains default-off and retains the opaque ABI1.0 resource
contract and all native/target scope limits above.
