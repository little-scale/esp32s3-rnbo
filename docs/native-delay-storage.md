# Native delay storage investigation

13 November 2026. **Automatic build policy; hardware validation pending.**

## Default for future builds

Following the offline trial, new native Studio builds (including Max helper
submissions) and default CLI preparation automatically convert reviewed internal
ordinary `delay~` rings to Float32 storage. Each ring is checked independently.
Unknown algorithms, ownership or sizing expressions retain their native storage
and a fallback reason is recorded; they do not stop other matching rings from
converting. Comb, allpass, Gen, external buffers and other buffer families are
outside this automatic policy and retain native storage. This is a bounded
compiler adaptation to Cycling ’74 output; no custom patch importer is used.

The build manifest contains a `delay_storage` summary, and provenance records
the exact source hashes, converted rings, retained Float64 references, fallback
reasons and payload bytes saved. Studio logs the summary and shows savings in
build results. Audio arithmetic, authored delay capacity, interpolation and
binary64 scheduler time stay unchanged. Existing packages do not change; rebuild
to use the new policy. The player itself needs no reflash for this storage change.

For a low-level native-storage comparison, pass `--delay-storage float64` to
`host/compiler/prepare.py`, or `delay_storage_policy='float64'` to its Python API.
The existing explicit `--float32-delays` option retains its broader, all-or-fail
historical research behaviour; it is not how Studio implements the new default.
Archived importer exports marked by `generator.json` retain their old behaviour
for reproducibility. Hardware qualification remains pending; there is no CPU
saving claim from a computer build.

The [default-policy receipt](../evidence/native-delay-storage-default.json)
records the real preparation, native render, ESP32-S3 cross-build and package
check. Its compiled source inputs match the offline candidate exactly.

The native RNBO 1.4.4 Minimal Export of SawSAHArpy explicitly constructs a
`Float64Buffer` for its ordinary `delay~` ring. `RNBO_USE_FLOAT32` makes audio
samples and `number` Float32, but does not change this explicitly Double buffer.
The generated writer accepts a Float32 `number`; the reviewed reader passes its
buffer samples to interpolation functions with Float32 arguments. Keeping these
stored samples as Double therefore deserves a controlled storage-only trial.
This finding does not establish that every native buffer can change precision.

## Trial and measured results

The existing fingerprint-guarded `--float32-delays` research converter recognises
this native export without extending its algorithm catalogue. The trial changes
exactly the ring's constructor and reference type to `Float32Buffer` and
`Float32BufferRef`. The constructor also selects the runtime's Float32 data type.
Ring capacity, generated reader/writer/interpolation logic, delay-change ramps,
feedback, lookup tables, other objects and binary64 scheduler time are retained.
The original export is preserved. No importer is involved.

| Measurement | Baseline | Storage candidate |
|---|---:|---:|
| Authored maximum delay | 22,050 samples | 22,050 samples |
| Allocated ring length | 32,768 samples | 32,768 samples |
| Ring payload | 262,144 bytes | 131,072 bytes |
| Host wrapper arena used | 589,920 bytes | 458,848 bytes |
| Cross-compiled module file | 96,912 bytes | 97,020 bytes |

The memory reduction is **131,072 bytes (128 KiB)**. Host arena totals include
other patch allocations and are not ESP32 heap measurements. The ring allocation
rounds up to a power of two; this is why its allocation exceeds 22,050 samples.

The offline probe compares raw Float32 output for the default patch, both
parameter extrema, fractional controls, a gradual sweep, rapid alternating
controls, a long default run, and fresh-context reconstruction. It also exercises
the actual generated ring methods directly with fractional/clamped delay values,
interpolation branches, repeated wraps, decaying feedback, clearing and reset.
An independent integer-delay impulse assertion checks that an impulse returns
after exactly 22,050 samples. Clearing is checked independently against zero.

All **25,165,824 compared Float32 words** are bit-identical across nine cases,
with zero maximum absolute or RMS error. The long run renders 190.22 seconds.
The ring test covers interpolation values 0–7 (seven generated branches; two
values share the fallback). Fresh-context captures also repeat exactly within
each version. No runtime errors, invalid output samples or late platform
allocations were reported. A shorter nine-case repeat passes
UndefinedBehaviorSanitizer and remains bit-identical.

AddressSanitizer could not complete: its macOS runtime stalled during shadow
memory initialization before the probe entered `main`, including outside
restricted execution. A sampled stack shows recursive sanitizer allocator
initialization. That process was stopped; no AddressSanitizer pass is claimed.
This leaves address-sanitized memory checks outstanding in addition to hardware
validation. The slightly larger compiled module file is separate from the
128 KiB reduction in runtime delay payload.

See the [machine-readable results](../evidence/native-delay-storage.json) for
capture counts, numerical errors, source/artifact hashes, memory use and checks.
Generated source, private audio and full local build logs remain under
`build/research/native-delay-f32/` rather than being distributed in the repository.

The evidence applies to this single native patch and fixed-size ordinary delay.
It does not qualify Gen delay, comb/allpass, external buffers, nonfinite inputs,
other RNBO versions or live package replacement. Measured host timing is
diagnostic only; no ESP32 CPU saving is claimed. The trial itself left Studio
defaults and installed firmware unchanged; the subsequent automatic policy is
described above.

## Reproduce without a board

Use the normalised native Minimal Export directory from a local Studio job.
The input must be trusted C++ and contain the authored SawSAHArpy patch. Output
must be a fresh directory.

```sh
python3 tools/investigate_native_delay_storage.py \
  --export build/private/studio/<job-id>/export \
  --out build/research/native-delay-f32/my-trial

python3 tools/investigate_native_delay_storage.py \
  --export build/private/studio/<job-id>/export \
  --out build/research/native-delay-f32/my-sanitized-trial \
  --blocks 512 --long-blocks 1024 --sanitizers

python3 -m unittest discover -s tools -p test_investigate_native_delay_storage.py -v
```

On this Mac the combined sanitizer runtime stalls before startup. The completed
undefined-behaviour-only repeat uses the same command with
`--sanitizers undefined` instead.

The script prepares independent baseline/candidate copies and compiles the same
production static wrapper with an isolated research probe. It records source,
runtime, compiler and output hashes and rejects unexpected transformation scope.
The two tests that require a real native export skip when it is unavailable;
set `RNBO_S3_TEST_NATIVE_DELAY_EXPORT` to a local export to run them elsewhere.
No generated Cycling ’74 source is embedded in the public tests.

## Hardware follow-up — pending

The later [Voice PE port](voice-pe.md) additionally checks the reviewed ordinary
ring at native 16 and 48 kHz using genuine Max exports. Six host comparisons
cover 6,291,456 Float32 words with exact agreement, saving 16 KiB for that
4,096-frame ring. See its [receipt](../evidence/voice-pe-readiness.json).
This extends computer-side evidence only; hardware qualification remains pending.

- Use the baseline and candidate from the same native export, player build,
  compiler, sample rate, block size, seed, controls and initial master volume.
  Confirm actual loaded identities before comparing them.
- Measure available heap, arena use and package-load/reset behaviour. Verify that
  the saved package restarts correctly. Test AMOLED touch controls and Wi-Fi
  responsiveness during delay changes.
- Measure alternating baseline/candidate runs with median and peak render time,
  render CPU percentage (`render_us / (256 / 44100 * 1e6) * 100`), deadline
  overruns, runtime errors and late allocations. Include steady state and rapid
  parameter sweeps; keep the existing startup admission threshold.
- Capture and compare target audio, including delay changes, wrap and feedback
  tails. Listen for clicks or numerical changes and compare against the native
  baseline at the same 44,100 Hz / 256-frame settings.
- Record numerical differences independently from speed and memory savings.
  Revisit the default if these checks uncover faults. Expand the automatic scope
  to other delay families only after separate native-export validation.

Both baseline and candidate ESP32-S3 modules can be cross-compiled without a
connected board. Their exact artifact identities are recorded in the receipt;
successful compilation is not hardware execution or deadline qualification.

## Separate hotspot to investigate

The same native export triggers a host compiler warning in `lores~`: its Double
literal `0.3` is compared with a Float32 cached resonance. Those values cannot
compare equal, so this generated condition takes the coefficient-recalculation
path on every sample even when resonance and cutoff are otherwise unchanged.
This observation comes from source inspection and a compiler diagnostic; its
individual target cost has not been measured. A separate, explicitly tested
cache-comparison experiment should precede any compiler change. It is outside
this storage-only candidate.
