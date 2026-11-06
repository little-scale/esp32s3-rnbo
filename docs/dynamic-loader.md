# Real RNBO ELF loader qualification

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

Real RNBO native modules passed the isolated hardware qualification on the
Waveshare ESP32-S3 Touch AMOLED 1.8 V2 on 2 November 2026. The run loaded and
unloaded 132 images, completed 32 repeated lifecycle rounds after an initial
warm-up round, and compared 378,368 channel samples against a statically linked
sine reference. Floating output and the test's int16 conversion matched with
zero absolute tolerance and zero LSB tolerance.

The result qualifies the tested modules' native loading, callback execution,
image isolation and reclamation in this application. It does not yet qualify
dynamic modules inside the permanent instrument's running audio/UI/network
pipeline. The complete structured record is
[evidence/dynamic-loader.json](../evidence/dynamic-loader.json); reproduction
and individual target checks are documented in
[rnbo-loader-test/README.md](../rnbo-loader-test/README.md).

## Source and artifact identity

The firmware uses ESP-IDF 5.5.0, Xtensa GCC 14.2.0
(`esp-14.2.0_20241119`) and Espressif ELF loader 2.0.0 from commit
`d2d935d0ee3e78deffa3981cc8c39ac8f534932b`. Dependency file inventories are
locked in `loader-spike/dependencies.json`. All tested modules use the
`float32-strict` numerical profile, 44,100 Hz, 256 frames, four detached warm-up
blocks, and seed `0x12345678`.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Qualification application | 419,040 | `b1fc6cf1c661b98340466b72dd65a02f9078ba5f186ac1714f52ce13ee6f1b8c` |
| Qualification firmware ELF | 4,838,292 | `d2cb37e632e894962075504284f1e8e34568176d985c467160772d0cc122885e` |
| Dynamic sine ELF | 46,980 | `222826d0ddbc5fd5245683f66de46aaac36dfe373aaf687578ac6cead031c72f` |
| Dynamic pass-through FX ELF | 32,736 | `ea6e98cdb81cf4b06079fe81f16b9c2a9df64120a0c8482d961780bd14915afc` |
| Dynamic four-voice MIDI ELF | 80,688 | `82a3eeb8091392d97442986cfbe800966dfe5f1b3ab5ee226e47702efad1e795` |

The firmware build report is
`build/rnbo-loader-test-amoled/build-report.json`, SHA-256
`c2a7da9ca9c07286836b305b76e2317007cd8efc309ab84966600c1e37587b4a`.
The device hashes all embedded ELF bytes before loading them. Its application
descriptor reports the firmware ELF hash, which is distinct from the flashable
application `.bin` hash. Raw serial evidence is retained at
`build/hardware/rnbo-dynamic-first/test-serial.log`, SHA-256
`615b7ddcd63f157f269a7a33f3f4f13f9e83fe2bd6096b4a9134d49f734f0d8e`.

## Admission and lifecycle observed

The modules contain no undefined imports. Math/compiler support and the C++
allocator/finalizer support are private to each image. Libc, ESP-IDF, customer
and shared-object symbol export paths remain disabled; the test also confirms
that common firmware/libc/C++ symbols cannot be found through the loader's
registry.

Before requesting entry, the host validates relocated constructor/finalizer
array spans and their executable targets. The handshake reports success
explicitly because this loader discards the entry function's C return value.
The host validates the actual module descriptor's complete data-section span,
its ABI/profile/state contract, and every base/extension callback against the
image's executable `.text` alias before invoking callbacks.

The device observed:

- One global initialization and one finalization per image across repeated entry
  requests, including 1,188 expected invalid/busy handshake rejections.
- Two concurrently loaded copies of the identical sine ELF with independent
  contexts, parameters, phase progression, descriptors and callback addresses.
- Successful reconstruction in an existing binding without rerunning global
  constructors; the other image continued processing after its sibling was
  destroyed and unloaded.
- Copied parameter metadata surviving unload, actual and normalized parameter
  changes, and conversions agreeing with the static reference.
- Exact pass-through of distinct planar left/right FX inputs, and silence
  after the FX Panic latch.
- Four MIDI notes held on channel four, continued sound after a different
  channel's release, and silence after the correct release.

The initial MIDI chord had measured amplitudes 0.0627223, 0.0631719, 0.0628672
and 0.0626991 at notes 60, 64, 67 and 71. Each exceeded the declared 0.015
threshold, so aggregate nonzero output alone could not satisfy this check.
The malformed-ELF error in the log is the expected truncated-input rejection.
The four-voice fixture intentionally discards its declared MIDI output port;
this qualification does not establish MIDI-output delivery.

Each fixture used a caller-owned PSRAM region containing its context and a
1 MiB arena. Initialization requested 363 module-local C++ allocations and 660
total arena allocations across the run. The largest observed arena high-water
was 328,416 bytes; that figure excludes the context, loaded code/data and host
shell. There were zero module-local late allocations and zero firmware heap
allocations or frees during watched parameter, MIDI and process callbacks.

After the warm-up round, free PSRAM remained exactly 8,377,996 bytes after every
repeated round. Free internal RAM never fell below 315,879 bytes at those
checkpoints and was exactly 315,879 bytes at completion. Heap integrity checks
passed. The test task's final stack margin was 20,508 bytes.
Patch destruction preceded ELF finalizers/unmapping; caller state was freed
only after finalization completed.

## Timing scope

The test ran on core 1 with no I²S, display or network initialized. These are
elapsed callback measurements, excluding load/preparation, PCM conversion and
the analysis work used to check output. They do not measure the complete
instrument's audio CPU use or establish an audio deadline bound.

| Callback workload | Blocks | Total µs | Average µs/block | Recorded peak µs |
| --- | ---: | ---: | ---: | ---: |
| Static sine reference | 706 | 376,108 | 532.73 | 617 |
| Dynamic sine copies | 739 | 420,980 | 569.66 | 711 |
| Dynamic pass-through FX | 264 | 27,685 | 104.87 | Not emitted |
| Dynamic four-voice MIDI | 2,372 | 6,203,443 | 2,615.28 | Not emitted |

The block populations and work mixes differ, including extra reconstructed
dynamic instances. This table is not a controlled static-versus-dynamic speed
comparison. In particular, the MIDI average cannot establish its worst-case
deadline behavior with I²S, UI, capture and Wi-Fi active.

## Restoration and remaining gates

The root-owned hardware runner flashed only the matching application region
and restored the identified instrument afterward. Restoration verified firmware
ELF `b14f63ef2f56e30732afec7c893fd68f68d22e584d023689cac524ce5c901ca4`,
running state and volume 28%. Parameter settings were replayed; the restored
protocol did not expose actual parameter readback, and oscillator phase was
not restored.

This test does not provide native-package installation, persistent recovery,
authenticated deployment, browser upload, or live Main-to-FX activation. It
tested two independent Main images and a separately processed FX, rather than
an attached Main/FX audio chain. Each loaded image supports one live context;
multiple concurrent contexts inside one image remain unqualified.

Native source remains trusted. Section checks cannot prove that an arbitrary
byte inside `.text` is a valid function entry, and a narrow import contract is
not memory isolation. Broader generated patches, data dependencies and
delay-heavy programs need their own initialization/resource and numerical
qualification. In particular, this fixture's 1 MiB allocation budget must not
be assumed sufficient for an unrelated patch.

The next integration gates are whole-system memory admission, audio-owner
activation/detachment of dynamic images, concurrent Main/FX processing, flash
maintenance and durable storage, followed by deadline qualification under the
instrument's actual enabled services.
