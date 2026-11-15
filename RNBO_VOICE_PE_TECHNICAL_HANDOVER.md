# RNBO on Home Assistant Voice Preview Edition: technical handover

Prepared 15 November 2026 for a new implementation project. Target hardware: **Nabu Casa Home Assistant Voice Preview Edition**, abbreviated **Voice PE**. Required audio profiles: **native 48 kHz and native 16 kHz**, initially with **256-frame RNBO processing blocks**.

This document combines the working Voice PE SynthDef port with the current ESP32-S3 RNBO player. It describes what can be reused, what must change, how to avoid the faults already encountered, and how to qualify the result. It does **not** claim that RNBO has already run on Voice PE. Preparing this handover did not connect to or modify a board, restart Studio, or change either runtime.

## Contents

1. [Recommended implementation](#1-recommended-implementation)
2. [Source baselines and evidence](#2-source-baselines-and-evidence)
3. [The current RNBO system](#3-the-current-rnbo-system)
4. [Voice PE hardware and clocking](#4-voice-pe-hardware-and-clocking)
5. [Two complete sample-rate profiles](#5-two-complete-sample-rate-profiles)
6. [Audio driver and startup sequence](#6-audio-driver-and-startup-sequence)
7. [Module ABI, package and compiler changes](#7-module-abi-package-and-compiler-changes)
8. [Real-time ownership and patch replacement](#8-real-time-ownership-and-patch-replacement)
9. [Button, dial, mute switch and LED ring](#9-button-dial-mute-switch-and-led-ring)
10. [Memory, timing and numerical behaviour](#10-memory-timing-and-numerical-behaviour)
11. [Flash layout, recovery and XMOS deployment](#11-flash-layout-recovery-and-xmos-deployment)
12. [Studio, Max and networking](#12-studio-max-and-networking)
13. [Implementation sequence](#13-implementation-sequence)
14. [Test plan and acceptance gates](#14-test-plan-and-acceptance-gates)
15. [Diagnostics and known traps](#15-diagnostics-and-known-traps)
16. [Source navigation and delivery checklist](#16-source-navigation-and-delivery-checklist)

## 1. Recommended implementation

**Extend the existing `esp32s3-rnbo` permanent player with a third board backend. Reuse the Voice PE audio, codec, controls and recovery work from `esp32s3-synthdef`.** Retain the RNBO module loader, native export compiler, package store, parameter routing, Max helper and Studio.

There is no need to build another RNBO object interpreter, port the SuperCollider graph renderer into the RNBO firmware, or begin again from the original FM1 loader. Those would discard the most useful work already completed.

The intended product flow is:

```text
RNBO patch in Max
  ├─ Minimal C++ export: fixed 48000 Hz / 256 frames
  │    └─ compile → rate-checked .rnbopkg → Voice PE with 48 kHz XMOS + ESP firmware
  └─ Minimal C++ export: fixed 16000 Hz / 256 frames
       └─ compile → rate-checked .rnbopkg → Voice PE with 16 kHz XMOS + ESP firmware

On each device:
  persistent RNBO Main package
       → private module context / event engine
       → stereo Float32 output
       → output meter / master gain / replacement envelope / PCM conversion
       → ESP32 I2S slave TX, stereo 32-bit slots
       → TLV320AIC3204 codec → speaker and/or analog output

  XMOS supplies playback BCLK, WS and codec MCLK.
  Button/dial/mute → bounded input snapshots → RNBO parameters.
  RNBO LED output extension → bounded mailbox → control task → RGB ring.
```

The two rates are **first-class build and deployment targets**, rather than one working mode and a future possibility. Native 16 kHz means that DSP, I2S wire rate and codec playback rate are all 16 kHz. A 16 kHz DSP feeding a 48 kHz output through a resampler is a different architecture and is not the initial target.

Use a single persistent **Main** package. All RNBO audio effects initially live inside that Main patch. The current RNBO product does not expose the SynthDef firmware's separate Main/FX slots. Its low-level ABI contains an FX role for tests, but the current package creator and permanent player reject that role. Adding an independently replaceable FX package would be a separate feature.

Start with generation, parameters and short MIDI input, not microphone capture or the Home Assistant voice assistant. The original voice-assistant software will be replaced by the RNBO player on the ESP32. Preserving a route back to the original firmware is part of commissioning; simultaneously running the complete assistant is not part of this port.

### Proposed profile identifiers

These names are a design proposal, not existing accepted CLI values:

| Profile | RNBO DSP rate | Output rate | RNBO block | Required XMOS playback image |
| --- | ---: | ---: | ---: | --- |
| `voice-pe-48000-256-v1` | 48,000 Hz | 48,000 Hz | 256 frames | Qualified stock-compatible 48 kHz image |
| `voice-pe-16000-256-v1` | 16,000 Hz | 16,000 Hz | 256 frames | Qualified custom native-16 image |

A profile includes the board, sample rate, vector size, codec settings, expected external clock and supported control capabilities. It must be present in build provenance and device information. **Do not infer a profile from a board nickname.**

## 2. Source baselines and evidence

### 2.1 Repositories reviewed

| Project | Local source at preparation | Baseline |
| --- | --- | --- |
| Voice PE / SynthDef | `/Users/a1106632/Documents/WaveShareAmoled18-synthdef` | [`510c14aabb48f8a7b2318ba6947a915b2c7e874c`](https://github.com/little-scale/esp32s3-synthdef/tree/510c14aabb48f8a7b2318ba6947a915b2c7e874c) |
| Current ESP32 RNBO | `/Users/a1106632/Documents/esp32-rnbo` | [`c2ec97b9a6c9fa2c3b2319beb8b0e1d4ce9a7519`](https://github.com/little-scale/esp32s3-rnbo/tree/c2ec97b9a6c9fa2c3b2319beb8b0e1d4ce9a7519), plus local changes described below |
| Historical FM1 RNBO | Referenced by the earlier handover | [`3b46afcd022f10a7f82be99a613bdc98b875c209`](https://github.com/little-scale/fm1-rnbo/tree/3b46afcd022f10a7f82be99a613bdc98b875c209) |

The current RNBO checkout has uncommitted changes, particularly the automatic Float32 ordinary-delay storage policy and associated Studio/provenance presentation. This handover distinguishes that work from the committed baseline. **Do not assume a fresh clone of `c2ec97b` includes it.** Reconcile and pin the desired RNBO working tree before implementation.

The companion [source snapshot manifest](RNBO_VOICE_PE_SOURCE_SNAPSHOT.json) records hashes of the relevant reviewed files and repository state. Paths from the RNBO project below are relative to its root; paths from this document's repository are relative to the SynthDef root. Copying the handover into a new project should include that manifest and the selected source/evidence files, rather than depending on these machine-specific absolute paths.

The older [RNBO ESP32-S3 handover](RNBO_ESP32S3_TECHNICAL_HANDOVER.md) is historical context. Its initial exporter/importer proposals and statements that an ESP32 RNBO loader had not yet been proven have been superseded. Similarly, early sections of Voice PE source-survey documents predate the successful native-16 experiment. Prefer the later dated evidence and [native-16 record](../ports/voice_pe/NATIVE_16K.md) when they differ.

### 2.2 What is established, and what remains unproven

| Area | Evidence available | Limit of that evidence |
| --- | --- | --- |
| Voice PE original-firmware recovery | Own-unit ESP flash backup, restoration and working ring/dial confirmed | ESP flash backup does not include XMOS flash or eFuses |
| Voice PE 48 kHz playback | Working codec/I2S backend, clean speaker listening tests and controls | Not RNBO playback; jack and microphone paths not qualified |
| Voice PE native 16 kHz | Custom XMOS image, matching codec/ESP build, measured clocks, clean listening sequence and cold-power controls | Not RNBO playback; no assumption that stock XMOS can switch rates at runtime |
| RNBO dynamic loader | Isolated AMOLED load/unload, reference comparisons and per-image context separation | Isolated test did not include active I2S/UI/Wi-Fi |
| RNBO native export player | Actual Max export compiled and loaded on XIAO, parameter changes, pause/resume, persistence | Existing qualified profile is 44.1 kHz / 256, not either Voice PE rate |
| RNBO Wi-Fi package upload | XIAO association/pairing, authenticated upload and wrong-key rejection | Loaded Voice PE networking still needs testing |
| RNBO AMOLED firmware installation | Studio backup/readback/startup evidence | Its installer layout is not suitable for Voice PE |
| Float32 ordinary-delay storage | Current local compiler policy; offline parity and undefined-behaviour checks | Hardware timing/listening still pending; not a universal buffer conversion |
| RNBO on Voice PE | Architecture and reusable sources identified | No RNBO image has been built, flashed or heard on Voice PE for this handover |

Relevant RNBO evidence files include `evidence/dynamic-loader.json`, `native-export-intake.json`, `xiao-native-export-player.json`, `xiao-max-export-parity.json`, `max-usb-upload-player.json`, `player-wifi.json`, `studio-firmware-uploader.json` and `native-retained-features.json`. Use each file's patch/build/profile identity when quoting its measurements.

Relevant Voice PE evidence is linked from [NATIVE_16K.md](../ports/voice_pe/NATIVE_16K.md), including [XMOS hardware](../evidence/voice-pe-native16-xmos-hardware-20261115.json), [audio hardware](../evidence/voice-pe-native16-audio-hardware-20261115.json), [SC integration](../evidence/voice-pe-native16-sc-hardware-20261115.json), [cold start](../evidence/voice-pe-native16-cold-start-20261115.json) and [final verification](../evidence/voice-pe-native16-final-20261115.json).

The commissioned Voice PE was identified as `VoicePE-0697d4`, ID `esp32-1020ba0697d4`. At the last recorded native-16 qualification it used the matched 16 kHz pair. This is a historical checkpoint, not a claim about a board's current connection, running patch or user-selected volume. Discover and inspect again before doing any hardware work.

## 3. The current RNBO system

### 3.1 Supported export route

The working route is **Cycling '74 RNBO C++ Minimal Export**, using the matching runtime files copied by Max, followed by the existing native compiler and module packer. The supported adapter has been qualified with **RNBO 1.4.4**.

For the existing 44.1 kHz player, the current export requirements are:

- Minimal Export enabled; Copy Library enabled.
- Fixed Sample Rate `44100`; Fixed Vector Size `256`.
- Main with zero signal inputs and two signal outputs.
- Generated header, `description.json`, `dependencies.json` and complete matching `common/` kept together.
- Numeric parameters, up to **32 in the player/Studio**. The SDK's larger declaration is not the product's parameter limit.
- No required external files, external data services or unimplemented message interfaces.

The Voice PE work must introduce the corresponding **48000/256 and 16000/256** export profiles. A wrapper prepared for one rate cannot repair generated C++ exported at another rate simply by changing a macro.

The `.rnbopat` importer and visual Gen translator have been retired from the supported audio compilation path. A `.rnbopat` can accompany an export as a **display drawing**. It does not regenerate DSP or override physical metadata in the actual export. Earlier importer object-count coverage is not a compatibility guarantee for the native-export player.

Cycling '74 describes Minimal Export as its reduced-footprint route for small targets with controlled allocation. The exact adapter and memory guarantees still come from this project's wrapper and tests, rather than from that description alone. [Official Minimal Export guide](https://rnbo.cycling74.com/learn/minimal-export), [C++ target overview](https://rnbo.cycling74.com/learn/the-cpp-source-code-target-overview).

### 3.2 Permanent player versus patch module

The player is a board-specific ESP-IDF application. A compiled patch is a self-contained **Xtensa ELF inside `.rnbopkg`**, loaded into that running application. Normal patch uploads do not reflash the bootloader or application.

The correct current entry point is **`firmware/main/player_main.c`**, selected by `RNBO_S3_PLAYER=ON`. The older `firmware/main/main.c` is a static/tone shell and is not the permanent player's implementation. Porting only that older shell would leave Studio's package workflow unsupported.

The player already provides:

- Validated package framing, hashes, staging, persistent Main selection and previous-package handling.
- A module descriptor, private image context/arena, module-local allocation and lifecycle handling.
- Numeric parameter schemas, actual/normalized conversion and generation-checked parameter events.
- One short-MIDI input port for capable packages; no arbitrary SysEx or MIDI output product interface.
- Audio-owner execution, parameter/event queues and physical-input coalescing.
- Output conversion, master volume, metering and faults.
- USB commands and paired Wi-Fi package/control transport.
- Boot guards for packages that fail startup verification.

Modules are **trusted native code**. Descriptor checks, source hashes and zero undefined imports reduce specific failure modes; they do not provide process isolation, an MPU sandbox or proof that arbitrary generated code will meet a deadline.

The current FM1/pi32v2 `.rnbom` binary cannot be loaded on the ESP32's Xtensa processor. Reuse the current Xtensa package and loader, rather than translating or copying fixed-address FM1 binaries.

### 3.3 Existing numerical and scheduler decisions

Keep Float32 signal calculation with **Float64 scheduler time**. `RNBO_USE_FLOAT32` does not mean every clock, timestamp and intermediate representing time should become Float32.

The current wrapper supplies private platform services and tracks late allocations. The dynamic entry has an explicit result field because the reviewed ELF request path does not propagate an entry point's C return value as a reliable result. Preserve the existing `DESCRIBE`/`BIND` protocol, descriptor-range validation and finalizer handling when adding the board.

Current source records also identify unresolved RNBO event corner cases:

- Event `line` can encounter endpoint/duration rounding behaviour that repeatedly schedules work and exhausts its queue. This is different from the signal object `line~`.
- A compound `curve~` case can exceed the inline active-ramp list and attempt a later allocation. Increasing one tested list capacity is not a general proof of bounded allocation.
- Keeping scheduler time as Float64 does not fix generated Float32 local arithmetic in every object.

Read `docs/native-ramp-diagnosis.md` and the native-wrapper tests before claiming general scheduler compatibility. Private experimental fixes should stay separately identified until parity and hardware deadline tests pass.

## 4. Voice PE hardware and clocking

### 4.1 Board resources and reserved pins

The reviewed Voice PE has an ESP32-S3 at **240 MHz**, **16 MiB flash** and **8 MiB PSRAM**. It also has a separate XMOS XU316 and a TLV320AIC3204 codec. It is not a generic XIAO with another I2S DAC attached.

| Function | ESP32 GPIO / address | Porting requirement |
| --- | --- | --- |
| Centre button | GPIO0, active low | Also affects ROM boot mode; debounce and preserve recovery use |
| Microphone mute sense | GPIO3 | Input only; not the speaker mute or panic control |
| XMOS reset | GPIO4 | Leave under explicit board-control ownership; no opportunistic reset |
| I2C SDA / SCL | GPIO5 / GPIO6 | Shared codec and XMOS control bus |
| Playback WS / BCLK / data | GPIO7 / GPIO8 / GPIO10 | ESP32 receives WS/BCLK and transmits data |
| Codec MCLK net | GPIO9 / shared hardware net | XMOS supplied; **do not drive it from the ESP32** |
| Microphone RX BCLK / WS / data | GPIO13 / GPIO14 / GPIO15 | Reserved; capture is outside the initial port |
| Encoder A / B | GPIO16 / GPIO18 | Quadrature PCNT, configure after safe board/audio GPIO setup |
| Jack detect | GPIO17 | Preserve; jack routing/listening needs separate qualification |
| LED data / LED supply enable | GPIO21 / GPIO45 | Addressable ring; not an ordinary activity LED |
| Speaker amplifier enable | GPIO47 | Keep disabled during uncertain clocks/startup/faults |
| Codec | I2C `0x18` | Use the verified board-specific clock and routing sequence |
| XMOS | I2C `0x42` | Version interrogation and explicit maintenance only |
| LED ring | 12 RGB LEDs | Logical RGB, hardware GRB, board-specific rotation |

The authoritative pin constants are in [voice_pe_pins.h](../ports/voice_pe/main/voice_pe_pins.h). The source register links the pinned official YAML, schematics and ESPHome codec implementation: [SOURCES.md](../ports/voice_pe/SOURCES.md). These references establish the board routing; the later bench evidence establishes the tested configuration.

**Do not implement Voice PE by selecting the existing RNBO `HEADLESS` branch unchanged.** Today that branch means XIAO: it selects an I2S master, XIAO pins and a GPIO21 activity LED. On Voice PE, GPIO9 and GPIO21 have entirely different jobs. Introduce an explicit board enum/configuration with separate display capability, audio backend, controls backend and installer layout.

### 4.2 Clock domains

XMOS is the **playback clock master**. The ESP32 is a standard Philips I2S **slave transmitter**, with **two 32-bit slots per frame**. The codec's MCLK is nominally 24.576 MHz in both reviewed profiles.

| Quantity | Native 48 kHz | Native 16 kHz |
| --- | ---: | ---: |
| WS / frame rate | 48,000 Hz | 16,000 Hz |
| Slots per frame | 2 | 2 |
| Bits per slot | 32 | 32 |
| BCLK = rate × 2 × 32 | 3.072 MHz | 1.024 MHz |
| Nominal codec MCLK | 24.576 MHz | 24.576 MHz |
| Codec NDAC | 2 | 6 |
| Codec MDAC | 2 | 2 |
| Codec DOSR | 128 | 128 |
| MCLK / (NDAC × MDAC × DOSR) | 48,000 Hz | 16,000 Hz |

The native-16 hardware record measured WS close to 16 kHz and BCLK close to 1.024 MHz. The startup survey is a coarse rate check, not an instrument-grade jitter or MCLK measurement. MCLK values above describe the reviewed configuration; do not represent them as a new oscilloscope measurement.

ESP-IDF supports standard-mode slave operation and separate slot/data configuration. Reuse the checked new-channel API backend rather than mixing it with the legacy driver. [ESP-IDF 5.5 I2S documentation](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32s3/api-reference/peripherals/i2s.html).

### 4.3 Why native 16 kHz needs two firmware images

The original installed XMOS image does not provide a demonstrated runtime playback-rate command. Source review found fixed-rate configuration in the application and no supported ordinary control command for switching this output between 48 and 16 kHz.

Native 16 kHz was achieved by building and installing a custom XMOS image, then using matching ESP32 I2S and codec settings. Both halves are now evidenced in the SynthDef project. The RNBO project must preserve that matched pair.

Consequently:

- An ESP32-only rate selector must not promise that it changes XMOS clocks.
- A 16 kHz module on a physically 48 kHz wire would run at the wrong effective pitch/time unless explicitly resampled; it must be rejected, not silently played.
- A 48 kHz codec-divider setup on a 16 kHz wire is not a valid alternate mode.
- A USB product-version marker is useful identification, but measured clock rate and verified image identity are stronger evidence.
- Switching a device between these profiles is initially a **maintenance workflow**, with explicit instructions for the internal USB selector and both firmware images. Routine patch upload stays separate.

## 5. Two complete sample-rate profiles

### 5.1 One source patch, two real exports/builds

For the initial fixed-rate export design, a patch intended for both rates needs two Max exports or a verified Max-helper operation that performs both fixed-rate exports. Compile each export with its matching runtime/configuration. Do not export at 44.1 kHz and edit a package's rate field to make it appear compatible.

Rate identity must agree at all of these boundaries:

1. Max export settings and generated sample-rate assertions.
2. Prepared source, generated `patch_config.h` and compiler manifest.
3. Compiled module descriptor and wrapper preparation rate.
4. `.rnbopkg` header and host-side parsed metadata.
5. Player build profile and device-reported rate/block size.
6. Voice PE audio backend and codec divider choice.
7. Actual external WS/BCLK and expected XMOS image profile.
8. Capture-file metadata, deadline calculation and telemetry labels.

Build caches must include the profile, export/runtime hashes, numerical policy, wrapper/ABI identity and relevant build options. Otherwise an apparently successful 16 kHz build can accidentally reuse a 48 kHz object or package.

### 5.2 Vector size and latency

Keep the current RNBO vector at **256 frames** during initial qualification. The SynthDef engine's 64-frame block size is a different engine choice and should not be copied automatically.

| Profile | Duration of 256 frames | Block-boundary control granularity, before other latency |
| --- | ---: | ---: |
| Existing RNBO 44.1 kHz | 5.805 ms | Up to roughly one block |
| Voice PE 48 kHz | 5.333 ms | Up to roughly one block |
| Voice PE 16 kHz | 16.000 ms | Up to roughly one block |

The proposed native-16 mode has a larger block-boundary control delay. Internally scheduled RNBO events can still have their own timing, but the current host-to-module parameter path applies boundary events. Do not advertise all incoming hardware/MIDI controls as sample-accurate without changing and testing that path.

The current Voice PE DMA design uses six buffers of 128 frames. Its total capacity is 768 frames: **16 ms at 48 kHz**, **48 ms at 16 kHz**. Capacity is not a measured end-to-end latency. The driver can split one 256-frame RNBO block into two 128-frame writes; DSP and DMA blocks do not need identical lengths.

If low-rate interaction later needs a smaller vector, introduce another explicitly qualified profile. That changes event granularity, overhead, output ramp timing and build/package matching, so it should follow the successful two-rate port.

### 5.3 Mixed-rate devices and broadcast

A rate-specific module may be board-independent for audio-only use, but it is not sample-rate independent. Host routing must resolve targets first, group them by compatible profile and choose the correct package for each group.

For an eventual "send to all" action:

- Build once per required rate/vector/runtime combination, not once per individual device.
- Send the identical 48 kHz package to compatible 48 kHz targets and the identical 16 kHz package to compatible 16 kHz targets.
- Reject missing variants with a clear per-device result; do not transcode or retag during upload.
- Apply physical-control capability checks independently from audio compatibility.
- Treat multi-device upload as separate acknowledged installations. It does not imply simultaneous sample-accurate starts or shared oscillator phase.

Current RNBO Wi-Fi delivery should be retained first. SynthDef Studio's group/omni behaviour is useful design experience, not an already implemented RNBO fleet API.

## 6. Audio driver and startup sequence

### 6.1 Reuse the successful backend

Start from [board_audio_voice_pe.c](../firmware/components/board_audio/board_audio_voice_pe.c), with its dependencies under `ports/voice_pe/main/`. Adapt its application-facing interface to the RNBO `board_audio` component instead of rewriting the electrical sequence.

Reuse these pieces deliberately:

| Source | Responsibility |
| --- | --- |
| `voice_pe_board.[ch]` | Early safe GPIO state and board ownership |
| `voice_pe_codec.[ch]` | I2C driver access and codec operations |
| `voice_pe_codec_sequence.[ch]` | Verified register sequence, rate dividers, startup checks |
| `voice_pe_format.[ch]` | S16 application PCM to signed 32-bit I2S words |
| `voice_pe_survey.[ch]` | External clock survey and startup validation |
| `board_audio_voice_pe.c` | I2S slave, DMA, write semantics, mute and restart integration |

The codec uses a board-specific input route; a generic AIC3204 example using only the conventional pin named DIN can leave this board silent. Preserve the verified routing, output-power sequence and readbacks.

The existing codec sequence includes approximately **2.5 seconds of analog startup delay**. This is initialization, not audio processing overhead. Do not remove it to improve a DSP benchmark. Keep outputs muted through it.

### 6.2 Preserve the application PCM contract

The RNBO player currently produces planar Float32, then interleaved S16 PCM. Keep that contract initially. Voice PE needs 32-bit I2S slots, but that does not require converting the whole RNBO signal engine to integer math or changing the module ABI.

The tested packing operation is:

```c
/* Defined for every signed 16-bit input; no left shift of a negative value. */
int32_t wire_sample = (int32_t)application_sample * 65536;
```

For one 256-frame stereo block:

- Caller PCM contains `256 × 2 × 2 = 1024` bytes.
- I2S wire data contains `256 × 2 × 4 = 2048` bytes.
- The Voice PE adapter can convert/write two chunks of 128 frames.
- On full success, the public `written` result is **1024 consumed caller bytes**, not 2048 wire bytes.

Preserve whole-frame alignment on partial writes. A short write or timeout must not report a full block consumed. Conversion should use fixed/preallocated storage, with finite checks and gain handling before packing.

The current Voice PE writer already chunks arbitrary frame counts; it is not inherently restricted to the SynthDef engine's 64 frames. Test 256 explicitly rather than inventing a new packing implementation.

### 6.3 Ordered startup

Recommended sequence, combining the proven board ordering with the RNBO player:

1. Early safe initialization: preload amplifier-enable and LED-power outputs low, then enable their output mode. Avoid brief enable pulses.
2. Establish board identity, profile and retained user settings. Leave audio muted.
3. Initialize I2C and inspect codec/XMOS where supported. Do not automatically replace XMOS because its version differs from stock.
4. Check external WS/BCLK against the requested profile using the tested clock survey. Missing or wrong clocks must produce a typed diagnostic while preserving USB recovery.
5. Initialize codec with the profile's clock dividers, routing and muted output state. Complete the analog delay/readback sequence.
6. Configure I2S slave TX, stereo 32-bit slots, finite timeouts and zeroed DMA storage.
7. Configure encoder PCNT and its pull-ups **after** the board/audio safe GPIO setup. The working SynthDef port changed to this order after earlier encoder input pulls were lost.
8. Validate/load the saved RNBO package or a safe empty state. Clear physical LED ownership until a valid module owns it.
9. Fill DMA with zeros and start the channel without an audible patch discontinuity.
10. Start/control the audio owner and verify progress. Unmute the codec and enable the amplifier only when clocks and DMA are valid, applying the startup/replacement fade.
11. Publish ready/profile/clock/module information. A responsive USB console should not depend on the patch producing sound.

The exact placement of package preparation relative to I2S startup may be adapted to the player's maintenance protocol. Its invariants are more important: no uninitialized output, no codec unmute before valid clocks/DMA, no live module processing during destruction, and no USB dead end if package preparation fails.

### 6.4 Gain, volume and output routes

The working SynthDef Voice PE codec path now uses **0 dB DAC gain**; the early bench path had substantial attenuation and sounded unexpectedly quiet. Preserve the intentional codec gain and perform user volume scaling in the common output path.

The current RNBO PCM renderer also has a **0.5 headroom factor**, equivalent to approximately −6.02 dB in amplitude gain, before user scaling. Document that factor in the new port; do not hide a low-level gain mismatch by turning the analog DAC above the proven setting.

A volume percentage describes gain, not the measured absolute level of the patch. A dB display should label **gain relative to unity**, using `20 log10(gain)` and `−∞` at zero, rather than implying a measured dBFS signal level without a meter.

For commissioning, start muted and use a brief low-amplitude tone at a small master setting, increasing only after output is verified. Preserve a user-selected level thereafter. The RNBO player currently keeps live master volume in RAM and restores package `initial_volume` on boot; the SynthDef port persists user volume separately. If adopting persistent user volume, specify precedence explicitly—e.g. saved device override over package startup default—and test it. Do not accidentally restore an old 100% setting on the first different-rate boot.

GPIO47 disables the built-in speaker amplifier. It does not by itself mute all codec analog outputs. Panic/fault recovery must cover the codec/output path as well as the amplifier. A clean built-in speaker test is not proof of independent left/right jack output.

## 7. Module ABI, package and compiler changes

### 7.1 Existing package/ABI contract

The existing `.rnbopkg` framing has a 128-byte little-endian header:

```text
magic[8] = "RNBOS3P1"
uint32: header_bytes, envelope_version, abi_major, role,
        sample_rate, block_frames, arena_bytes, metadata_bytes, elf_bytes
sha256(ELF)[32]
sha256(metadata)[32]
reserved[20] = zero
then: UTF-8 JSON metadata, then ELF, no trailing bytes
```

Current bounds: metadata up to 65,536 bytes, ELF up to 524,288 bytes, arena 4,096–4,194,304 bytes. Main is role 1, zero signal inputs and two outputs. The player parameter maximum is 32. These are actual admission limits, not estimates of every patch's resource needs.

Envelope v1 is an ordinary package, v2 carries XIAO physical-input bindings and v3 carries AMOLED patch-area touch bindings. New Voice PE bindings must be deliberately versioned/capability checked. An old player must reject a control-dependent package instead of accepting it and silently ignoring its inputs.

Rate and block fields already exist in the header and module descriptor. Supporting 16/48 kHz does not by itself require moving their offsets or inventing another binary format. It **does** require replacing hardcoded 44.1 kHz admission and retaining the parsed fields through the full host/player path. The current `player_package` representation validates and discards some profile information; add explicit retained fields so later checks cannot lose it.

The current C ABI uses a sized descriptor with ABI version, channel/rate/block/flag fields and callback pointers. Changing permitted values can preserve its layout. Appending an LED/control extension requires a separate sized/versioned contract; changing an existing callback's calling convention requires a real ABI revision.

### 7.2 Required changes by file

Paths in this table refer to the **RNBO repository**, unless marked SynthDef.

| File / area | Current assumption | Required work |
| --- | --- | --- |
| `firmware/CMakeLists.txt`, component CMake/Kconfig | XIAO or AMOLED | Add explicit Voice PE board and two rate profiles; no Waveshare display dependency |
| `tools/build_firmware.py` | Two board choices; 44100/256 report/config | Add Voice PE profile inputs, isolated build directories and truthful manifests |
| `module-sdk/include/rnbo_s3_module.h` | `RNBO_S3_SAMPLE_RATE=44100`, block 256 | Generate or select profile constants consistently for player and module |
| `module-sdk/dynamic/rnbo_s3_dynamic.cpp` | Compile-time matching and fixed preparation | Retain static assertions, prepare with selected rate, validate actual module interface |
| `host/native_export.py` | Guidance/intake for fixed 44100 | Recognize supported profile/export rate; reject disagreement before building |
| `host/compiler/prepare.py` | Generated 44100 config/manifests and source guards | Accept explicit profile, verify generated rate assertion, emit matching config/provenance |
| `host/compiler/build_module.py` / inspection | Existing wrapper/link settings | Include profile in build identity and verify resulting descriptor/config |
| `host/compiler/package.py` | `create`/`parse`/`build` enforce 44100/256 | Carry validated profile through all entry points; preserve header rate/block fields |
| `player_store.h` / `player_store.c` | Header admission fixed at 44100/256 | Retain parsed fields; reject incompatible packages before persistence/activation |
| `player_loader.c` | Descriptor equals current constants | Compare package, descriptor, player profile and physical controls; Main-only remains |
| `firmware/main/player_main.c` | Literal 256 and 44100 in processing/init/info/deadlines | Use one profile definition in every path, including sample position and telemetry |
| `pcm_output.c` | Rate-based volume ramp | Verify ramp remains a duration in seconds at both rates; integrate replacement gain |
| `board_audio` | XIAO master or Waveshare codec | Add adapted Voice PE slave backend and safe early initialization |
| Physical IO / LED components | XIAO pins or AMOLED touch | Add semantic Voice PE inputs and off-audio ring worker |
| `host/studio/server.py`, web UI, Max helper | Existing board list, rate labels, build/cache paths | Select/routable two-rate exports; package/device compatibility displayed before upload |
| Firmware installer/bundle parser | Generic erase/layout workflow | Add Voice PE-specific protected migration and paired-rate maintenance policy |
| Capture and reference tools | Some 44100-sized arrays/time conversions | Parameterize actual rate/frame count; label captured data correctly |

Use `rg` across source, tests, fixtures and UI for `44100`, `44.1`, `256`, `SAMPLE_RATE`, `HEADLESS`, `sample_rate`, `block_frames` and fixed-duration frame arrays. A literal 256 may remain intentional, but it should derive from or be asserted against the selected vector. Historical optimization reports at 44.1 kHz must stay historical, rather than being globally text-replaced.

The preparer contains rate-specific optimizations and reports, including an `exact_delay44100` path. Do not generalize them to new rates merely because they compile. Disable unqualified transformations or derive and test their rate dependence explicitly.

### 7.3 Proposed capability report

Extend `player-info` without removing existing fields. The following is an illustrative contract, **not an existing response**:

```json
{
  "runtime": "rnbo-esp32s3-player",
  "board": "voice-pe",
  "profile": "voice-pe-16000-256-v1",
  "rate": 16000,
  "output_rate": 16000,
  "block_frames": 256,
  "clock_source": "external-xmos",
  "clock_check": {"passed": true, "expected_ws_hz": 16000},
  "voice_pe_inputs_version": 1,
  "led_output_version": 0,
  "max_parameters": 32
}
```

Advertise `led_output_version:0` until programmable RNBO-to-ring output actually exists. Prefer explicit unavailable capabilities over a success-shaped placeholder. Add measured WS/BCLK, XMOS version and diagnostic stages when available, but distinguish measured data from configured expectations.

### 7.4 Admission invariants

Reject before changing the active package if any of these disagree: requested host profile, generated export rate/vector, package header, module descriptor, player build, channel counts, parameter IDs or board-control capability. Reject nonfinite metadata/parameter values, oversized storage/arena requests and unsupported flags.

Package hashes establish identity/integrity; they are not signatures. Preserve existing authenticated network pairing. Do not accept executable packages from arbitrary unauthenticated LAN broadcasts just because the firmware can parse them.

## 8. Real-time ownership and patch replacement

### 8.1 Keep one audio owner

Only the audio owner should invoke a module's process/event/panic operations or mutate its live RNBO state. The control/network/USB tasks submit bounded messages or coalesced snapshots. Codec I2C, LED RMT waits, flash writes, JSON parsing and ELF relocation must not occur in the render callback.

Retain generation checks. A parameter message for the previous module must not alter a newly loaded module that happens to reuse the same numeric parameter index. Bind physical controls by stable parameter identity and resolve them against the candidate's schema before activation.

The existing player uses monotonic maintenance request/acknowledgement epochs with a finite timeout. Preserve that design. A timeout means ownership is uncertain: do not free an image that the audio task may still be using.

### 8.2 Bring over the successful fade/drain design

The SynthDef firmware already improved audible Main replacement by fading out before replacement and fading back in. The RNBO permanent player currently parks/stops DMA at a boundary; its normal master-volume smoothing is **not** a complete patch-replacement transition.

Adapt the principles in [audio_transition.h](../firmware/components/instrument/include/audio_transition.h), rather than transplanting SynthDef renderer types:

1. Stage and validate the upload while the current patch remains active where memory allows.
2. Request a short sample-counted fade to zero on the audio owner. Approximately 5 ms is a reasonable starting policy, subject to listening tests.
3. Acknowledge only after the relevant faded samples and required queued output have reached the chosen drain point. A silent software buffer alone does not prove that DMA is no longer playing older samples.
4. Park processing and perform candidate loading/preparation/persistence using the existing transaction rules.
5. Switch the active generation and clear old pending control/LED ownership.
6. Queue zeros/start cleanly and fade the new module up when appropriate.
7. Destroy the old context, run finalizers and unmap/free it only after ownership has been transferred safely.

At 48 kHz a 5 ms envelope is 240 samples; at 16 kHz it is 80. Both may complete part-way through a 256-frame vector. Apply the envelope per sample; do not approximate it as one whole block at both rates.

A fade/brief gap is a practical first implementation. A true overlap crossfade requires both modules to process concurrently and increases peak CPU and memory; do not introduce it implicitly. Delay/reverb tails inside the outgoing Main end with that Main unless a separate tail policy is deliberately implemented.

Normal replacement should not toggle the amplifier for each package. Keep the established clock/codec path running through controlled silence when safe. Emergency faults may need immediate mute instead of a graceful fade.

### 8.3 Failure and persistence rules

Retain these separate outcomes:

- **Candidate invalid before commit:** keep the old running/saved package.
- **Candidate preparation returned an error:** report that exact stage; safely destroy the candidate, retain old package where the transaction permits.
- **Audio-owner acknowledgement timed out:** latch a fault, keep uncertain live memory allocated, require an explicit recovery path. Do not mistake a timeout for completed destruction.
- **New selection saved but output restart failed:** report the durable new selection and recovery requirement accurately; do not claim the old patch is still active.
- **Saved module fails boot guard:** retain USB diagnostics and a previous/empty recovery path; avoid an endless audible/crashing reboot loop.

The Voice PE SynthDef work encountered generic activation-acknowledgement errors that were hard to interpret from the host. The RNBO port should expose typed stages and a concise reason, including whether the saved selection changed and whether an audio task remains alive. A user should not have to infer all of that from "restart required".

## 9. Button, dial, mute switch and LED ring

### 9.1 Preserve the proven physical semantics

The SynthDef implementation deliberately uses this bus map:

| SynthDef control bus | Meaning |
| --- | --- |
| 0 | Debounced centre button, 0/1 |
| 1 | Dial normalized and clamped to 0–1 |
| 2 | Physical microphone-mute sense |
| 3–38 | Twelve RGB triplets, logical LED order |
| 39, 40, 41 | Shared red, green, blue for the whole ring |
| 42 onward | Reserved for future Grove sensor work |

This is useful as a **semantic reference**, not an RNBO API. RNBO has no SuperCollider `In.kr`/`Out.kr` bus namespace. Sending an audio signal to RNBO output 3 does not address LED bus 3.

The working dial starts at 0.5 and advances approximately 0.0125 per quadrature edge, clamping at both ends. With four edges per detent this is roughly 20 detents across the full range. The earlier smaller step appeared unresponsive to the user. Preserve this useful default and make any sensitivity change explicit.

The microphone switch is a microphone-state input. It must not automatically silence the speaker patch or overwrite the dial unless an authored mapping requests that behaviour. GPIO0's boot function must remain recoverable; a button press during normal operation is a module input, not an unconditional firmware reset.

### 9.2 Input mapping through RNBO parameters

Reuse the current RNBO parameter metadata mechanism and extend it with Voice PE semantic inputs, rather than exposing raw reserved pins as arbitrary XIAO GPIO bindings.

For example, the following metadata shape is a **proposal requiring compiler/player implementation**, not currently accepted syntax:

```text
param dial 0.5 @min 0 @max 1
  @meta "{'esp32': {'type': 'voice_pe', 'input': 'dial'}}"

param button 0 @min 0 @max 1
  @meta "{'esp32': {'type': 'voice_pe', 'input': 'button'}}"

param mic_mute 0 @min 0 @max 1
  @meta "{'esp32': {'type': 'voice_pe', 'input': 'microphone_mute'}}"
```

Choose the final spelling to fit the existing parser; the important contract is semantic source, stable parameter identity, normalized range and explicit board capability.

Controls should reach RNBO through its normalized parameter conversion so the authored min/max/exponent/step behaviour remains meaningful. A dial normalized to 0–1 can then control a frequency parameter in hertz without the board layer duplicating parameter scaling rules.

Poll/accumulate hardware in the control task, publish fixed-size snapshots and apply changes at the audio boundary. Coalesce rapidly changing dial position, but ensure button down/up edges are not both lost between observations. Define whether a press that occurs while parked is discarded or delivered after resume; avoid a stuck gate. Initialize each candidate from a coherent physical snapshot and attach its generation before enabling updates.

PCNT setup and input pull-up ordering are already proven. Reuse them and test both clamped endpoints plus recovery when turning back into range. Include a stress case where rapid encoder movement crosses a PCNT watch point; avoid interpreting counter wrap as a huge dial jump.

### 9.3 LED hardware path

The working SynthDef ring implementation provides useful constraints:

- Twelve logical RGB LEDs, wire order GRB, physical index `(logical + 7) % 12`.
- A physical brightness cap of approximately 20% in the packer; normalized authored values still use 0–1.
- Nonfinite/negative values clamp to zero; values above one clamp to one.
- A bounded audio/control mailbox, approximately 50 Hz publication and at most 40 Hz hardware refresh.
- Stale data timeout of approximately 200 ms, after which the ring goes dark.
- RMT transfer and waits on a control worker, never inside audio processing.

Reuse [voice_pe_leds.c](../firmware/components/headless_io/voice_pe_leds.c) and [voice_pe_controls.c](../ports/voice_pe/main/voice_pe_controls.c) as the tested basis. The existing RMT timings are part of that basis; replacing them with a generic library is unnecessary initial risk.

The SynthDef bus resolver has explicit per-LED versus shared-colour precedence and Main/FX writer rules. With one RNBO Main, the new contract can be simpler: a complete twelve-LED frame plus an optional shared-colour command, with documented precedence. Do not claim that RNBO inherits SynthDef's graph writer masks automatically.

### 9.4 Programmable RNBO-to-LED output requires an extension

The current RNBO product does **not** support arbitrary message output ports. Its 32-parameter limit also means that 36 individual RGB channels plus three shared-colour values cannot simply be added as 39 hidden parameters. Parameters are primarily an input interface anyway.

Recommended progression:

1. Bring up a board-owned ring status/dial indicator first. This validates physical hardware without pretending patch-authored LED output exists.
2. Prototype a bounded RNBO output-message adapter for explicit LED messages. Verify the exact RNBO Minimal Export callback path against the pinned runtime before choosing an API.
3. Add a versioned module/host contract that captures those messages into module-owned fixed storage and transfers a complete LED snapshot at a block boundary.
4. Publish the snapshot to the board worker with generation/sequence identity. Clear it on replacement, panic, fault and stale timeout.

A useful proposed authored convention would be `led_rgb` with either three normalized values for a shared colour or a 36-value RGB frame, with a fixed payload limit and documented update rate. Names, event encoding and timestamps must be finalized by the prototype. This handover does not claim an existing `outport led_rgb` patch will work unchanged.

Do not depend on variable-size heap allocation, formatting JSON, or calling an RMT driver from an RNBO event callback. If the selected Minimal runtime cannot deliver the required output messages under those constraints, implement a narrow sized C-ABI extension around fixed storage instead of enabling all message services indiscriminately. Keep old ordinary packages loadable and reject packages requiring unavailable LED capabilities.

Grove sensor activation remains deferred until actual sensors are available, as requested during the Voice PE work. Preserve pin reservations and document future expansion; do not fabricate tested sensor support.

## 10. Memory, timing and numerical behaviour

### 10.1 Useful fixed-size estimates

These are engineering estimates for the proposed 256-frame stereo path, not a complete linker/heap report:

| Item | Approximate storage |
| --- | ---: |
| Two planar Float32 output vectors | 2,048 bytes |
| Interleaved S16 application vector | 1,024 bytes |
| One 128-frame stereo S32 conversion chunk | 1,024 bytes |
| Six 128-frame stereo S32 DMA buffers, payload only | 6,144 bytes |
| Current RNBO audio/control task stacks, 24,576 bytes each | 49,152 bytes total |
| One-second stereo S16 capture at 16 kHz | 64,000 bytes |
| One-second stereo S16 capture at 48 kHz | 192,000 bytes |

DMA descriptors, driver queues, synchronization objects, RMT storage, network buffers, code, module state, arena overhead and allocator alignment are additional. Task stack use must be measured; allocated size is not actual high-water use.

The dynamic module's state/context and arena use the established external-memory policy, but executable image allocation, relocation needs and DMA-capable memory have separate constraints. Report both free bytes and **largest available contiguous block by capability**, not only total PSRAM.

Patch replacement is a peak-memory problem: current image, candidate image, upload buffer, metadata, inactive storage operations and shared runtime all coexist at points in the transaction. A patch that fits at cold boot may fail hot replacement. The package's arena field is not the whole cost of loading it.

The reviewed dynamic loader defaults to a smaller arena policy and permits explicit larger requests up to the package limit; do not allocate the maximum for every patch. Establish measured state/arena peaks and an admission margin. File/storage limits and instantaneous heap feasibility are separate checks.

### 10.2 What 16 kHz saves

At the same 256-frame vector, native 16 kHz calls processing approximately one third as often as 48 kHz. Sample-based algorithms and delay storage sized in seconds can benefit substantially. Vector arrays and many per-instance data structures remain the same size. Event work based on time or external input does not necessarily fall by a factor of three.

Native 16 kHz has a Nyquist frequency of 8 kHz and a different sonic bandwidth. Oscillator antialiasing, filters, delays, feedback networks and rate-sensitive coefficients must be tested at that rate. Do not promise exactly one-third CPU or bit-identical sound between the two rates.

The 32-bit wire slots are a framing requirement, not proof of 32-bit analog precision. The initial path still quantizes final output to S16 while retaining Float32 internal audio calculations. The project should first reproduce the known output quality; a later direct Float32-to-S32 output path is a separate numerical/gain qualification.

### 10.3 CPU reporting

Use the actual profile in the denominator:

```text
budget_us = block_frames × 1,000,000 / sample_rate
render_cpu_percent = measured_busy_us / budget_us × 100
```

For 256 frames the budgets are 5,333.333 µs at 48 kHz and 16,000 µs at 16 kHz. Report DSP-only time, PCM/conversion overhead and total producer busy time separately if possible. Exclude blocking I2S wait from the busy-time CPU measure, but track its duration/timeouts and DMA errors independently.

Include current/rolling average, peak with a reset action, deadline misses, nonfinite output, clipping, event/parameter drops, late allocations, audio progress and heap/stack information. A peak above 100% has a deadline implication even when DMA briefly masks the audible consequence.

Existing RNBO XIAO tests include a native sine export around 737.5 µs median producer time at 44.1 kHz/256, roughly 12.7%, over the recorded observation. Other isolated patches have different costs. These measurements validate instrumentation and that specific workload, not a forecast for a Voice PE reverb patch at 48 or 16 kHz.

Similarly, SynthDef Voice PE Saw/Impulse optimizations and their hardware CPU improvements do not optimize RNBO's generated oscillator implementation. The two engines share the board and processor, not their DSP routines.

### 10.4 Compiler transformations and long-running events

The current RNBO checkout's automatic Float32 conversion is restricted to recognized **ordinary internal `delay~` rings** with matched ownership/reference/sizing forms. Unknown forms retain their native storage and record a fallback. Comb, allpass, Gen and external buffers are outside that policy. Preserve these bounds and manifests if adopting the uncommitted work.

Requalify its patterns at both rates. Capacity in seconds, power-of-two allocation, interpolation, feedback stability and actual byte savings must be derived from the generated export, not inherited from one 44.1 kHz example. A global textual replacement of `double` with `float` is inappropriate.

Use `uint64_t` processed sample positions and Float64 conversions to elapsed time. Test event scheduling across block boundaries, long duration, late triggers, repeated parameter changes, active-ramp growth, silence/restart and wrap-sensitive conversions. Warmup without faults is not proof that every later event or delay resize is allocation-free.

## 11. Flash layout, recovery and XMOS deployment

### 11.1 Do not use the generic RNBO first-install recipe

The RNBO XIAO/AMOLED installer has a generic first-install path that backs up flash, erases the chip and writes its own bootloader, partition table and application layout. **That is not the reviewed Voice PE recovery/migration policy.**

The original Voice PE has different OTA/NVS boundaries, a separate XMOS flash and a proven path for preserving the original configuration. Add a Voice PE-specific installer; do not present it as another label pointing at the AMOLED bundle.

### 11.2 Reviewed ESP32 partition layouts

The commissioned unit's original table used:

| Partition | Offset | Size |
| --- | ---: | ---: |
| `otadata` | `0x009000` | `0x002000` |
| `phy_init` | `0x00b000` | `0x001000` |
| `app0` | `0x010000` | `0x7c0000` |
| `app1` | `0x7d0000` | `0x7c0000` |
| `nvs` | `0xf90000` | `0x06d000` |

A later official image uses a `0x070000` NVS extent. The helper recognizes these as explicit layouts rather than assuming they are interchangeable.

The reviewed SynthDef project table preserves `app0`, shortens `app1` to `0x3c0000` and places a **4 MiB storage partition at `0xb90000`**, retaining NVS at `0xf90000`. The original `app1` area was verified empty before its tail was repurposed. That emptiness is a per-device fact to check on a fresh migration, not a universal factory guarantee.

Reusing this project layout for RNBO is a reasonable proposal, subject to app-size and storage tests. Do not copy the RNBO AMOLED table, whose storage begins elsewhere. Do not assume that the existing SynthDef filesystem or package records are RNBO-compatible.

### 11.3 Port the guarded installer policy

Use [host/voice_pe_firmware.py](../host/voice_pe_firmware.py) as the basis. Preserve:

- Exact recognized stock/project partition layouts and table checksums.
- Flash-size, image identity and supported-device checks, plus the uploader's security-state checks.
- An own-unit full ESP flash backup before initial layout migration, with verified identity/checksum.
- Explicit protection of bootloader, NVS, PHY and unrelated regions.
- Per-device empty-region checks before shortening/reusing an OTA area.
- App-only updates once the project layout is recognized, with appropriate backup/readback.
- Accurate OTA selection handling and startup verification after flash.

The current helper recognizes expected SynthDef/stock application identities. Port that validation for the new RNBO application; do not remove the check or call it unchanged against an unrelated image.

Existing nonempty storage must never be automatically formatted merely because it is not an RNBO store. Options include preserving the filesystem and using a distinct RNBO namespace, or a deliberately reviewed backup/migration operation. First inspect the RNBO store's mount/format rules: its blank-storage fallback is only safe after verifying the entire intended region is erased. A magic mismatch is not permission to erase user data.

Backups may contain Wi-Fi credentials and pairing secrets. Keep them in an ignored, clearly named recovery directory outside public artifacts. A manifest may record sizes and hashes without committing private flash contents. An ESP backup cannot restore XMOS or change eFuses.

### 11.4 Proven XMOS native-16 build

The custom image was built from official Voice Kit XMOS **v1.3.1**, source commit:

```text
1a1df7c2b3e578431b1550a8defe8ae2c8b54d93
```

The reviewed native-16 upgrade image is **278,528 bytes** with SHA-256:

```text
5fde08cbb8fb1c051cc03b697b103e173831155ca9370f55c917f90ba8247927
```

Its identifying firmware version is `1.3.116`, with USB `bcdDevice` marker `0x1610`. The stock v1.3.1 upgrade image has SHA-256:

```text
11b563d6c51424f49f1e1d3585ba03a073e2802798e6aa067c6734d7ecb6935b
```

Build scripts and patches are [build_voice_pe_xmos.py](../host/build_voice_pe_xmos.py) and [ports/voice_pe/xmos/native16](../ports/voice_pe/xmos/native16). The pinned XTC 15.3 builder image is:

```text
ghcr.io/xmos/xcore_builder@sha256:cb301ec2c847d622a4a779a7fbbb131eba0c8f1931f53b938516b09529065e16
```

Preserve the exact submodule and compatibility patches recorded by the script/build evidence. The patches cover application rate/marker and reviewed upstream build compatibility; do not substitute a different XMOS toolchain or current branch while simultaneously debugging the new RNBO board backend.

The build helper's `prepare`, `verify` and `build` operations are build-only. Firmware writing is a separate explicit maintenance operation. See [NATIVE_16K.md](../ports/voice_pe/NATIVE_16K.md) for commands, checksums, source dependencies and the successful readback sequence.

### 11.5 XMOS backup and selector procedure

The internal **USB SELECT / SW3** is a small slide switch on the dial/LED face, near the corner opposite USB-C. It selects ESP32 or XU316 USB data. It is not one of the GPIO header pads and does not require soldering.

With power disconnected, selecting XU316 exposes the XMOS DFU interface. Normal ESP32 development uses the ESP32 position. In the proven maintenance sequence the centre button was held while reconnecting when it was necessary to keep the ESP32 application stopped. Normal post-update boot is without holding it.

Use [voice_pe_xmos_dfu.py](../host/voice_pe_xmos_dfu.py) to inspect and identify the exact device path. The observed USB VID/PID was `2886:0019`; its serial string was not unique, so serial alone must not select a board when multiple units are present.

The reviewed DFU alternatives are factory, upgrade and data. Backup/read twice before writing. Only the upgrade alternative was written in the successful experiment; the factory readback remained unchanged. Empty/zero reads from an unused or unexposed alternative are not a complete physical flash dump. Preserve that distinction in recovery documentation.

The upload helper has bounded read behaviour, including a process file-size limit; a tool's nominal upload-size flag alone was not accepted as a complete bound. Retain those precautions when reusing the script.

A safe rate change is a coordinated transaction: identify/backup → install and verify the intended XMOS upgrade image → move USB back to ESP32 → install matching ESP app muted → verify measured clocks → test → save the successful pair identities. A partially completed rate change remains muted and diagnosable until repaired.

Do not automatically flash stock XMOS from ESPHome merely because a custom version is detected; that would undo native-16 clocking. Recovery back to the Home Assistant base state may need **both** original ESP32 content and stock-compatible XMOS, not just the ESP restore.

## 12. Studio, Max and networking

### 12.1 Keep the two products distinguishable

Current RNBO Studio is launched from the RNBO repository with `./host/studio.sh`, normally at **`http://127.0.0.1:8788`**. SynthDef Studio normally uses port **8765**. They are separate host services and protocols.

The same ESP MAC can underlie a familiar device identity, but installing RNBO changes the application's protocol and stored package format. The SuperCollider `ESP32` extension does not automatically control RNBO modules. If SC-driven RNBO control is desired, add a deliberate parameter/MIDI bridge against the RNBO player API later; do not promise existing `.playESP32` uploads work.

The RNBO Max helper already exports the live `rnbo~`, including unsaved edits, and submits the native export to Studio. Extend that workflow with profile selection rather than introducing a new private source-code generator.

### 12.2 Studio features required for Voice PE

- Firmware choices explicitly named **Voice PE — 48 kHz / 256** and **Voice PE — native 16 kHz / 256**.
- A note on the 16 kHz option that matching XMOS maintenance is required. A fresh stock unit should not appear ready for native-16 merely because its ESP app can be flashed.
- Bundle board/profile/app identity, build-source inventory, freshness check and protected layout validation.
- Device information showing DSP/output rate, block size, external clock status, firmware identity and active package.
- Export/build controls that select or verify a genuine fixed-rate Max export; no silent default to 44.1 kHz.
- Package upload compatibility checks before transfer and again in the device.
- Volume gain slider, output meter and explicit panic/pause state.
- Current/average/peak producer load, resettable peak, deadline misses and useful memory limits/peaks.
- Per-stage load/install errors, including whether old package selection was retained.
- Recovery instructions that distinguish ESP32 flashing, XMOS maintenance and ordinary patch upload.

A rate label alone is insufficient. A user should be able to tell that their connected device is physically clocked for the chosen profile before hearing output.

### 12.3 Preserve existing transport semantics

The current RNBO USB commands include `player-info`, bounded `player-begin`/`player-data`/`player-commit`, `player-volume`, pause/resume, generation-checked parameter commands and short MIDI. Retain their compatibility where possible. Do not substitute the SynthDef binary exchange framing or accidentally consume its responses as RNBO JSON.

Existing Wi-Fi setup is provisioned through USB and uses a random pairing key. Upload/control over the LAN already has a working RNBO host/device path. Port it after USB/audio qualification, with the Voice PE profile included in information and admission. Do not log passwords or keys in evidence.

The RNBO Wi-Fi work previously found an undersized system-event task stack. Its fix moved work to a mailbox and enlarged the relevant stack. Preserve that fix and measure stack high-water marks with Voice PE audio and LED work active.

No internet connection is required between Max/Studio and devices on an isolated performance router, once the software/toolchains are installed. The host service must still be running locally. Loss of the host service is different from failure to discover a device; show those states separately. No automatic public-cloud dependency should be added to patch playback or module startup.

## 13. Implementation sequence

Each milestone should produce checked-in source, build instructions and a small evidence record with exact source/export/profile identities. Proposed names below do not imply commands already exist.

### Milestone A — Freeze the reusable baseline and profile contracts

1. Create the new project or working branch from the current RNBO player, retaining its loader tests and toolchain pins.
2. Reconcile the RNBO checkout's uncommitted changes; choose an explicit numerical/delay-storage baseline.
3. Copy only needed Voice PE components, tests and recovery manifests, preserving licence notices and provenance.
4. Define explicit board/rate/vector profile configuration and expected control capabilities.
5. Build both 48 kHz and 16 kHz player variants and matching simple Max exports on the computer.
6. Implement package/descriptor/host rejection tests before hardware activation.

**Gate:** both profile builds are reproducible; the old XIAO/AMOLED builds still compile; incompatible export/package/profile combinations reject in host tests.

### Milestone B — Silent Voice PE backend at both rates

1. Add safe early GPIO setup, shared I2C, codec sequence and I2S slave backend.
2. Keep the new player muted with an empty/silent package.
3. Bring over clock survey, codec readbacks and encoder setup ordering.
4. Add the protected Voice PE installer and private recovery backup handling.
5. Verify the connected unit's current XMOS pair before selecting which ESP image to install first.

**Gate:** matching 48 kHz and 16 kHz configurations can boot silently, report expected clocks and remain recoverable over USB; wrong-clock startup remains muted with a useful error.

### Milestone C — Real RNBO audio and persistence

1. Load a genuine Minimal Export sine/parameter patch by USB at each rate.
2. Verify PCM packing, volume scaling, frequency, stereo framing and process counters.
3. Test package replacement fade/drain and candidate rejection without damaging the active selection.
4. Test a delay/feedback/reverb export, event scheduling and panic.
5. Test saved Main startup and previous/empty recovery after a deliberately invalid candidate.

**Gate:** clean, correctly pitched audio at both rates; normal cold-power restart restores the documented package/volume policy; no faults, late allocations or unexplained drops in the agreed observation windows.

### Milestone D — Physical controls and ring

1. Bind dial, button and mute through validated semantic metadata and stable parameter identities.
2. Test normalized conversion, edge handling, endpoint recovery and module replacement.
3. Implement board-owned status/dial ring feedback.
4. Prototype and qualify the bounded programmable RGB extension, including stale/fault clearing.

**Gate:** authorable controls work without pin conflicts or audio-thread peripheral calls; programmable RGB support is advertised only once demonstrated.

### Milestone E — Studio/Max/Wi-Fi integration and release

1. Add both player bundles and genuine rate-specific export/build routing.
2. Validate USB and paired Wi-Fi package replacement while controls and ring are active.
3. Test wrong profile/board/package downgrade and interrupted upload paths.
4. Run the efficient two-rate regression matrix below and update the compatibility/evidence ledger.
5. Document first install, routine upload, rate maintenance and full base-state recovery separately.

**Gate:** a fresh supported Voice PE can be commissioned through documented guarded steps; subsequent packages can be replaced without reflashing the player; both required rates have actual hardware evidence.

## 14. Test plan and acceptance gates

### 14.1 Computer-side tests before using limited hardware time

Build all fixtures first. Use identical source and deterministic seeds where an A/B comparison is intended. Generate distinct fixed-rate exports, rather than modifying an existing binary fixture's header and calling it a valid second-rate module.

| Test family | Required cases |
| --- | --- |
| Profile matrix | 16→16 and 48→48 accepted; 16→48, 48→16 and legacy 44.1→either rejected; wrong vector rejected |
| Layer disagreement | Package header versus ELF descriptor, export assertion versus generated config, stale cache, wrong output channels/ABI/flags |
| Package parser | Truncated header/payload, trailing bytes, hash mismatch, integer overflow, oversized metadata/ELF/arena, invalid UTF-8/JSON |
| Control metadata | Missing/duplicate parameter IDs, wrong board, unsupported capability/envelope version, nonfinite/invalid ranges |
| PCM | Zero, ±1 LSB, extrema, alternating signs, independent channels, 1/64/128/256 frames, partial writes, aligned consumption counts |
| Transition envelope | Exact endpoints at both rates, fade within a block, repeated requests, zero volume, pause/panic during replacement |
| Loader/lifecycle | Repeated load/unload, simultaneous staged/live images, private state, constructor/finalizer order, failed prepare and timeout ownership |
| RNBO scheduling | Events at boundary, zero/long duration, repeated curves, parameter extremes, MIDI lengths, no later allocation in exercised paths |
| Physical inputs | Dial clamp/re-entry, counter watch points, button press/release across parking, generation changes |
| Ring | RGB/GRB mapping, rotation, clamp/nonfinite handling, broadcast/frame precedence, stale clearing, old-generation rejection |
| Persistence | Power interruption before/after durable selection, corrupt inactive bank, boot-guard fallback, nonempty foreign storage not formatted |

Reuse the current loader's portable/sanitizer tests. A sanitizer failure to start is not a test pass; the delay-storage investigation explicitly distinguishes its completed undefined-behaviour checks from an address-sanitizer environment failure.

### 14.2 Efficient hardware session

Avoid switching XMOS rates for every individual patch. Prepare all software and exports, then complete a compact sequence for one matched rate, perform one deliberate rate maintenance change, and repeat for the other. If separate already-matched units are available, use them to reduce maintenance risk/time.

Suggested order per profile:

1. **Silent inspection:** identity, profile, clocks, codec readbacks, blank/saved startup and DMA progress.
2. **Short audible check:** low-amplitude left, right and both tones; verify pitch and stop/panic. Built-in speaker listening alone cannot establish jack channel separation.
3. **One composite RNBO fixture:** oscillators, filter, dynamic parameters, envelope/event activity and an internal delay/reverb. Capture metrics before and after peak reset.
4. **Control sweep:** dial full range and back, repeated button presses, mute-switch input, ring updates; no audio crackles or stuck gate.
5. **Replacement sweep:** sine → composite → silence → same patch again, including a rejected wrong-rate package. Confirm fade and retained state rules.
6. **Persistence:** one normal unplug/reconnect with a saved auto-playing test package, confirming expected volume and ring ownership.
7. **Network burst if available:** paired Wi-Fi upload, parameter changes and information polling while audio/ring run.

This can fit a short listening session once the software is ready, but backup/DFU/clock recovery time is variable. Do not skip recovery checks to promise a fixed duration. Run longer silent soak/capture tests outside the user's active listening window where possible.

### 14.3 Small, representative patch set

Prepare the following as actual Max RNBO exports at both rates:

| Fixture | Purpose |
| --- | --- |
| Stereo sine with numeric frequency/level parameters | Pitch, output packing, gain, parameter schema and USB path |
| MIDI-gated simple voice | Gate/trigger handling, message lengths, repeat notes, panic and stuck-note recovery |
| Multi-oscillator + filter | Sustained render cost, parameter extremes and finite output |
| Ordinary delay + feedback/decay tail | Rate-dependent sizing, ring storage policy, wrap and tail stability |
| Internal reverb/comb network | Larger state, hot replacement memory and tail cutoff/fade |
| Event `line` / compound `curve~` regression | Known scheduler/late-allocation corner cases, separately labelled if still unsupported |
| Dial/button/ring patch | Semantic IO mapping and bounded LED output extension |

Do not call a Max patch using unimplemented services a player regression merely because it exports. For example, arbitrary file dependencies or unsupported output messages need a declared expected rejection until their adapters exist.

### 14.4 Evidence required for each rate

Record firmware ELF/app identity, module/package/export/runtime hashes, profile, XMOS image/version identity, measured clocks, codec divider readbacks, device identity and observation length. Record average/peak producer time, deadline/DMA/queue errors, late allocations, invalid samples/clipping, stack/heap measurements and listening result.

Minimum completion criteria:

- Both **native 48 kHz and native 16 kHz** have working RNBO hardware evidence.
- The actual generated export, package, descriptor, player, wire clocks and codec agree.
- Wrong-rate or unsupported IO packages reject before replacing a valid Main.
- Startup/fault paths remain muted and USB-recoverable.
- The exercised workload has no unexpected late allocations, invalid samples, queue losses or deadline misses during its recorded run.
- Parameter, MIDI, physical controls and supported LED functions behave consistently through replacement and cold power.
- Persistent selection, user volume policy and recovery are documented and tested.
- XIAO/AMOLED RNBO profiles have no accidental regression from the shared changes.

No finite suite proves all possible RNBO exports safe. Maintain a compatibility ledger by runtime version, feature and tested fixture, alongside explicit unsupported/known-failing cases.

## 15. Diagnostics and known traps

| Symptom | Likely checks and useful response |
| --- | --- |
| CPU rises but no sound | Inspect output meter, active/paused state, volume/headroom, codec mute/route, amplifier and measured external clocks; CPU alone proves no analog output |
| Correct package rejected as wrong rate | Compare actual Max export assertion, prepared config, package header, descriptor and player profile; do not edit only the header |
| Wrong pitch or envelope speed | Verify physical WS, descriptor/export rate and absence of accidental 44.1 kHz conversions |
| Dial seems stationary | Check pull-up/PCNT ordering, raw count and normalized value; verify sensitivity rather than assuming wiring failure |
| Dial reaches zero and patch becomes invalid | Inspect authored mapping: normalized zero can become an illegal exponential-random bound or unstable filter/time parameter; hardware clamping is not domain validation |
| Very quiet output | Check codec attenuation versus 0 dB sequence, RNBO 0.5 headroom, user gain and patch amplitude separately |
| Click at package replacement | Check DMA drain and sample-wise replacement fade; ordinary master-volume smoothing is insufficient |
| Activation acknowledgement error | Report failed stage, audio-task progress, selection state and recovery requirement; distinguish a returned candidate error from a true timeout |
| Dark ring after recovery flash | Check USB selector, ROM-loader versus app mode and normal cold restart before reflashing repeatedly |
| USB stopped responding | Confirm physical presence/port identity; use one bounded software attempt, then request normal reconnect if needed; do not write another board by path guess |
| Native-16 image reports custom XMOS version | Expected if it matches the qualified pair; do not trigger automatic stock DFU |
| Patch starts once but faults later | Exercise later events/ramp growth/delay resize; warmup did not prove permanent allocation freedom |
| Wi-Fi failure only with active DSP | Check task stacks, mailbox work, resource pressure and render deadlines; separate host-service loss from radio discovery |

A visible identify ring and low-level test tone are useful eventual support features. They should use an explicit bounded action with saved/restored gain/state, not interrupt a performance merely because Studio polls a device.

## 16. Source navigation and delivery checklist

### 16.1 Voice PE donor sources

All links in this subsection are to the SynthDef repository containing this document.

- [Voice PE overview](../ports/voice_pe/README.md), [porting notes](../ports/voice_pe/PORTING.md), [codec](../ports/voice_pe/CODEC.md), [controls](../ports/voice_pe/CONTROLS.md), [native 16 kHz](../ports/voice_pe/NATIVE_16K.md), [recovery](../ports/voice_pe/RECOVERY.md), [source register](../ports/voice_pe/SOURCES.md).
- [Audio backend](../firmware/components/board_audio/board_audio_voice_pe.c), [board pins](../ports/voice_pe/main/voice_pe_pins.h), [board safety](../ports/voice_pe/main/voice_pe_board.c), [codec sequence](../ports/voice_pe/main/voice_pe_codec_sequence.c), [format packing](../ports/voice_pe/main/voice_pe_format.c), [clock survey](../ports/voice_pe/main/voice_pe_survey.c).
- [Input adapter](../firmware/components/headless_io/headless_io_voice_pe.c), [LED worker](../firmware/components/headless_io/voice_pe_leds.c), [LED mapping/control helpers](../ports/voice_pe/main/voice_pe_controls.c), [transition helper](../firmware/components/instrument/include/audio_transition.h).
- [ESP installer](../host/voice_pe_firmware.py), [XMOS builder](../host/build_voice_pe_xmos.py), [XMOS DFU](../host/voice_pe_xmos_dfu.py), [rate tests](../host/test_voice_pe_rates.py), [native-16 tests](../host/test_voice_pe_native16.py), [codec tests](../host/test_voice_pe_codec.py), [controls tests](../host/test_voice_pe_controls.py), [ESP recovery tests](../host/test_voice_pe_firmware.py), [DFU tests](../host/test_voice_pe_xmos_dfu.py).

### 16.2 RNBO donor sources

Browse the [pinned RNBO tree](https://github.com/little-scale/esp32s3-rnbo/tree/c2ec97b9a6c9fa2c3b2319beb8b0e1d4ce9a7519). The snapshot manifest identifies reviewed working-tree files that differ from it.

| Area | RNBO paths |
| --- | --- |
| Product/current evidence | `README.md`, `docs/STATUS.md`, `docs/native-export.md`, `docs/native-wrapper.md`, `docs/native-export-comparison.md` |
| Known scheduler faults | `docs/native-ramp-diagnosis.md` |
| Package/USB/Wi-Fi | `docs/player-protocol.md`, `docs/player-wifi.md`, `docs/firmware-uploader.md` |
| Current physical metadata | `docs/physical-inputs.md`, `docs/touchscreen-inputs.md` |
| Player ownership | `firmware/main/player_main.c` |
| Audio conversion | `firmware/components/pcm_output/pcm_output.c` and `include/pcm_output.h` |
| Board abstraction | `firmware/components/board_audio/board_audio.c`, `board_audio_i2s.c`, `include/board_audio.h`, component CMake |
| Persistent package | `firmware/components/player_store/player_store.c`, `include/player_store.h` |
| Module loading | `firmware/components/player_loader/player_loader.c`, `include/player_loader.h` |
| C ABI / dynamic entry | `module-sdk/include/rnbo_s3_module.h`, `rnbo_s3_dynamic.h`, `module-sdk/dynamic/rnbo_s3_dynamic.cpp` |
| Private module services | `module-sdk/dynamic/` allocator/platform/lifecycle sources and corresponding tests |
| Export / compiler | `host/native_export.py`, `host/compiler/prepare.py`, `build_module.py`, `inspect_module.py`, `package.py` |
| Studio / Max | `host/studio/server.py`, `host/studio/web/`, `host/max/README.md` and helper files |
| Firmware builds | `tools/build_firmware.py`, firmware CMake/Kconfig/config defaults |
| Dependency pins | `loader-spike/dependencies.json`, toolchain/build manifests |
| Local pending delay policy | `docs/native-delay-storage.md`, `host/compiler/float32_delays.py`, preparation/Studio tests and evidence |

The RNBO builder currently requires **ESP-IDF 5.5.0**. Preserve the actual installed toolchain/component hashes, including the reviewed ELF loader 2.0.0, for the initial port. A simultaneous SDK/runtime upgrade would expand the debugging surface unnecessarily.

### 16.3 Initial project handover package

Deliver the following with the new project:

1. This document and source snapshot manifest.
2. Pinned RNBO player/module/compiler sources, with any chosen local pending changes reconciled.
3. Selected Voice PE components, host tests, recovery scripts and source/firmware hash manifests, with required licences.
4. Two documented build profiles and matching real Max export fixtures.
5. Protected installer and separate XMOS maintenance instructions; private backup location policy.
6. Host-side compatibility tests, portable audio/control tests and a short hardware checklist.
7. Evidence ledger separating computer checks, board measurements and user listening confirmation.
8. An explicit list of pending features: programmable RGB until its extension exists, jack qualification, loaded Wi-Fi qualification, microphone capture, Grove sensors and any known RNBO scheduler failures.

Source licences differ across the inherited projects. Voice PE donor C files carry GPL-3.0-or-later notices; hardware references have their own licences; RNBO generated/runtime files and the loader have separate notices. Preserve each and review the combined project's distribution obligations before release. This handover does not replace that review.

The first useful outcome is a small native RNBO patch audibly running through the verified Voice PE path at **both required rates**, with protected recovery and honest resource reporting. The existing loader/compiler makes that a focused board/profile port; clock matching, safe installation and complete rate propagation are the parts that need the most care.
