# RNBO ESP32 S3 technical handover

> **Historical handover.** The implementation has moved to [Max C++ Minimal Export only](docs/native-export.md). This document records the original design, not the current importer or qualification scope. See [current status](docs/STATUS.md).

Prepared 2 November 2026 for a new project implementing an RNBO instrument on two targets:

1. Waveshare ESP32 S3 Touch AMOLED 1.8 V2, with display, touch, battery status and onboard speaker output.
2. Seeed Studio XIAO ESP32S3, with no display, external stereo I²S output and optional physical controls.

The recommended design combines the RNBO export and compatibility work from `fm1-rnbo` with the board support, audio ownership, USB and Wi-Fi control, persistence and qualification approach from the ESP32 SynthDef project. RNBO patches become **Xtensa native modules**. They do not become SynthDef graphs and cannot use the SynthDef interpreter as an execution engine.

**Initial audio profile: 44,100 Hz, 256 samples per RNBO block, float32 audio, stereo between Main and FX.** This deliberately retains the FM1 RNBO exporter's existing vector size. The ESP32 framework currently uses 64 samples; its scheduling, work buffers and diagnostics must be adapted consistently. Smaller RNBO vectors are later benchmark profiles, not a prerequisite for the first working port.

**Implementation status:** this is a source-based design and implementation handover. Existing FM1 and SynthDef results below describe those projects. No RNBO module has been compiled, loaded or timed on either ESP32 target as part of this handover. Proposed APIs, budgets, filenames and milestones are identified as proposals.

## 1 Source baselines

Use these immutable baselines before reviewing later changes:

| Project | Reviewed commit | Purpose |
| --- | --- | --- |
| [FM1 RNBO](https://github.com/little-scale/fm1-rnbo/tree/3b46afcd022f10a7f82be99a613bdc98b875c209) | `3b46afcd022f10a7f82be99a613bdc98b875c209` | RNBO exporter, runtime adaptations, native module ABI, player, browser converter, compatibility fixtures |
| [ESP32 SynthDef instrument](https://github.com/little-scale/synthdefs-for-esp32-s3-touch-amoled-1.8/tree/59e19441408a4df14cf2f5b6e8ba527929e74d9b) | `59e19441408a4df14cf2f5b6e8ba527929e74d9b` | Both board profiles, audio drivers, transport, persistence, controls, display and hardware evidence |
| [Espressif ELF loader source](https://github.com/espressif/esp-iot-solution/tree/d2d935d0ee3e78deffa3981cc8c39ac8f534932b/components/elf_loader) | `d2d935d0ee3e78deffa3981cc8c39ac8f534932b` | Candidate native loader; reviewed component declares version `2.0.0` |

The current SynthDef firmware build identity is `e4d101e1934112da5b9f13a6c7938b918a6e3ce804d3878a15d77e6e8464c2e3`. This identifies the firmware represented by the latest XIAO qualification evidence; it is distinct from the Git commit.

The working local SynthDef checkout is `/Users/a1106632/Documents/WaveShareAmoled18-synthdef`. Local FM1 development files also exist under `/Users/a1106632/Documents/FM1 Firmware`, but that directory contains several projects and revisions. Prefer the pinned GitHub snapshot, or verify local file hashes against it. Build scripts must not depend on these absolute paths.

### Existing toolchain versions

| Area | Reviewed baseline |
| --- | --- |
| RNBO | 1.4.4; internal exporter APIs are explicitly version checked |
| FM1 host compatibility environment | Node 26.7.0, Apple Clang 17.0.0, Python 3.14.7 on Apple Silicon |
| ESP-IDF | 5.5.0 dependency; build report identifies `v5.5` |
| ESP32 target compiler | Xtensa GCC 14.2.0, `esp-14.2.0_20241119` |
| Waveshare BSP | `waveshare/esp32_s3_touch_amoled_1_8` 2.0.3 |
| LVGL | 8.4.0 |
| MCU CPU configuration | 240 MHz on both ESP32 profiles |

The relevant files are the FM1 [exporter](https://github.com/little-scale/fm1-rnbo/blob/3b46afcd022f10a7f82be99a613bdc98b875c209/fm1-base/rnbo/tools/export.cjs), FM1 [compatibility report](https://github.com/little-scale/fm1-rnbo/blob/3b46afcd022f10a7f82be99a613bdc98b875c209/fm1-base/rnbo-loader/COMPATIBILITY.md), ESP32 [component manifest](https://github.com/little-scale/synthdefs-for-esp32-s3-touch-amoled-1.8/blob/59e19441408a4df14cf2f5b6e8ba527929e74d9b/firmware/main/idf_component.yml) and [XIAO build report](https://github.com/little-scale/synthdefs-for-esp32-s3-touch-amoled-1.8/blob/59e19441408a4df14cf2f5b6e8ba527929e74d9b/evidence/xiao-build.json).

## 2 Product baseline

Use the current ESP32 product model as the starting point:

- One saved **Main** module.
- One saved **FX** module.
- An explicit FX bypass option, initially enabled.
- A module-wide scaled output volume, initially 100%.
- A stable device ID, friendly name and host aliases.
- USB and Wi-Fi deployment to one module, an explicit group, or all selected online modules.
- Persistent standalone operation after loading a suitable autonomous patch.
- Named parameters, MIDI events, telemetry and a dependable Panic operation.

The FM1's three instrument slots and eight physical knob controls are useful implementation references, but they are not the proposed ESP32 storage or UI specification. Additional library management can remain on the host. Main and FX should remain separate from a host library of available patches.

RNBO supports instruments whose sound follows MIDI, and autonomous patches driven by clocks, noise or internal sequencers. **Do not impose a universal touch gate or require a first touch to start audio.** An autonomous patch must run hands off when its configured startup policy says to run. A MIDI patch will naturally remain quiet until its own MIDI or parameter logic produces sound.

For the new project, make startup policy explicit: `autostart`, `manual`, and optionally `start_on_midi`. Recommended first release behaviour is to reload the last committed Main and FX, apply saved parameters, honour the saved startup policy, and restore FX bypass and module volume. Saving a module and starting an instance should be distinguishable operations even if the browser offers a combined Build and Run action.

## 3 Architecture

```text
Max RNBO editor or standalone .rnbopat
                   |
          Local RNBO exporter
                   |
      Generated C++ and description.json
      Audited runtime adaptations and provenance
                   |
          ESP32 S3 module compiler
                   |
      Versioned package containing Xtensa ELF
      Parameter metadata, optional patch layout/source
                   |
       Local browser service and deployment manager
                   |
           USB or authenticated Wi-Fi
                   |
          Persistent ESP32 runtime shell
                   |
       Validate -> stage -> prepare -> activate
                   |
           Audio owner on CPU core 1
          Main -> FX or bypass -> volume
                   |
          Board-specific PCM conversion
          /                         \
  AMOLED ES8311 mono          XIAO stereo I2S
```

Keep board GPIO, display calls, network sockets and flash access in the shell. A patch should receive audio buffers, parameter/MIDI events, time and narrowly defined host services. It should not own I²S or call the display directly.

A board-independent RNBO module can serve both targets if the runtime ABI, sample rate, block size and supported services match. The runtime firmware remains board specific. An AMOLED firmware image must never be offered as a XIAO firmware update, even if their RNBO patch package is identical.

## 4 What the FM1 RNBO project actually implements

### 4.1 Export and compilation

The exporter uses the user's installed RNBO 1.4.4 package through `@rnbo/xam` and `@rnbo/xam-runner`. It checks the installed version, reconstructs supported patch metadata, exports C++, copies the runtime to a build directory, applies checked adaptations to those copies, and records provenance. It does not modify the installed RNBO package.

Its code-generation invocation fixes the sample rate at 44,100 Hz and block size at 256. It enables MIDI, disables presets, state restore and probing, and can generate mono, two-voice or four-voice configurations through the surrounding builder. An embedded polyphonic group with a shared effect follows a separate export path. These details are visible in [export.cjs](https://github.com/little-scale/fm1-rnbo/blob/3b46afcd022f10a7f82be99a613bdc98b875c209/fm1-base/rnbo/tools/export.cjs).

Useful outputs include:

- `rnbo_source.raw.h`: original generated C++.
- `rnbo_source.h`: adapted C++ used in the build.
- `common/`: a prepared RNBO runtime copy.
- `originals/`: runtime headers preserved before adaptations.
- `description.json`: exported parameter and patch description.
- `patch_config.h`: patch identity and compile configuration.
- `provenance.json`: source/runtime hashes, versions, topology and applied changes.
- Optional original/reference generated variants for numerical comparison.

Preserve this separation in the ESP32 port. A failed adaptation match should stop conversion and identify the unsupported source pattern. It must not quietly run a broad replacement over an unrecognised RNBO version.

Also accept a **manual RNBO Minimal C++ Export** as an initial import route. That route is useful before porting the internal exporter and when validating a new RNBO release. It does not automatically inherit the FM1 importer's visual Gen conversion or its recorded adaptations. Cycling '74 documents the minimal export as generated source plus the `common` runtime, with fixed sample rate/vector options and custom platform support. [RNBO Minimal Export](https://rnbo.cycling74.com/learn/minimal-export?v=1.3.1)

### 4.2 Native FM1 module format

FM1 `.rnbom` packages are fixed-address **pi32v2 native code**, not portable RNBO bytecode. Their checks include:

| FM1 property | Value |
| --- | --- |
| ELF machine checked by the builder | 241 |
| Code/image base | `0x01c34000` |
| State base | `0x01c44000` |
| Maximum image | 65,536 bytes |
| Maximum state | 180,224 bytes, or 176 KiB |
| Package header | 64 bytes |
| Native API table | 84 bytes on that target |
| ABI 1 | Mono-priority MIDI policy |
| ABI 2 | Unmerged/raw MIDI notes for polyphonic use |
| Format sample rate and vector | 44,100 Hz and 256 samples |

The player reserves those RAM regions, copies a validated image there, clears state, calls the API's initializer and then invokes its callbacks. Its flash storage uses three logical patch slots with four physical records to support updates. The address reservations, image format and execution guard are FM1-specific. [Module ABI](https://github.com/little-scale/fm1-rnbo/blob/3b46afcd022f10a7f82be99a613bdc98b875c209/fm1-base/rnbo-loader/module.h), [linker script](https://github.com/little-scale/fm1-rnbo/blob/3b46afcd022f10a7f82be99a613bdc98b875c209/fm1-base/rnbo-loader/modules/module.ld), [package parser](https://github.com/little-scale/fm1-rnbo/blob/3b46afcd022f10a7f82be99a613bdc98b875c209/fm1-base/rnbo-loader/tools/package.py), [loader](https://github.com/little-scale/fm1-rnbo/blob/3b46afcd022f10a7f82be99a613bdc98b875c209/fm1-base/rnbo-loader/engine.c).

**An FM1 `.rnbom` cannot execute on ESP32-S3.** Reuse its source design, export pipeline and validation approach, then recompile for Xtensa. Reject the old package format before attempting to interpret any of its native pointers.

### 4.3 Runtime wrapper and allocation policy

The [FM1 bridge](https://github.com/little-scale/fm1-rnbo/blob/3b46afcd022f10a7f82be99a613bdc98b875c209/fm1-base/rnbo/bridge.cpp) provides initialization, rendering, MIDI, Panic, parameter access and statistics. Its platform flags include `RNBO_USE_FLOAT32`, `RNBO_NOSTDLIB`, `RNBO_NOSTL`, `RNBO_NOTHROW`, `RNBO_USECUSTOMPLATFORM`, `RNBO_NO_PATCHERFACTORY` and `RNBO_FIXEDLISTSIZE 16`.

Important implementation properties:

1. A monotonic arena supports allocation, realloc-by-copy and whole-instance reclamation.
2. The wrapper counts total and late allocations; late allocation or invalid output makes the render path fail closed.
3. It overrides global `operator new`, `operator new[]` and delete operations for its native module environment.
4. It uses placement construction for the generated patch and logger.
5. It explicitly runs constructor tables on the target because the original firmware has C startup.
6. It initializes and warms the patch before allowing normal rendering.
7. It requires exactly zero audio inputs, two outputs and no more than 16 exported parameters.
8. It requires a 256-frame render and produces interleaved **signed 24-bit-scale values in 32-bit integer words**.
9. It deliberately retains an eight-byte `RNBO::MillisecondTime` despite float32 audio.
10. The target's explicit reconstruction resets a fixed PRNG seed; it is not a fresh-random-state policy by itself.

Items 3, 5, 7 and 8 require substantial adaptation. In particular, the old wrapper cannot implement the proposed external master FX stage because it rejects input channels and always calls `process` with no audio input.

### 4.4 Existing adaptations worth preserving

Port these as independently enabled, tested transformations rather than one opaque optimisation switch:

| Adaptation | Why it matters on ESP32-S3 |
| --- | --- |
| Compiler-derived `size_t` and pointer integer types | Avoid assuming all 32-bit ABIs use identical typedefs |
| Float literal and generic math corrections | Avoid unintended double arithmetic in signal loops |
| Float32 delay buffers | Reduce delay memory and bandwidth where the generated implementation is qualified |
| Bounded comb/allpass buffers | Allocate from a declared maximum rather than unnecessarily large defaults |
| Bounded averaging buffers | Avoid oversized history storage for known constant windows |
| List inline/overflow copy fixes | Prevent incorrect list copying at and beyond the inline capacity |
| Nested MinimalEngine clock dispatch | Deliver clock events to the recorded nested target |
| Block clock and peak interval hoisting | Remove repeated work while retaining timing semantics |
| Removal of proven unread mtof tables | Avoid allocating large unused tables |
| Embedded visual Gen conversion and portability fixes | Retain the supported Gen workflow and graph semantics |

The FM1 fast-phase, saw truncation, downsample counter and integer-conversion changes need their own Xtensa evaluation. Its old compiler workarounds, multiply/load hazard checks and linker addresses must not be carried over as presumed ESP32 requirements. Start with a conservative numerical profile; add target-specific optimisations after measuring actual Xtensa output.

The source files are under `fm1-base/rnbo/tools/`, especially `runtime.cjs`, `float32.cjs`, `float32-delays.cjs`, `bounded-filters.cjs`, `bounded-averages.cjs`, `gen-graph.cjs`, `gen-portability.cjs` and `audit.py`. See the [bounded buffer report](https://github.com/little-scale/fm1-rnbo/blob/3b46afcd022f10a7f82be99a613bdc98b875c209/fm1-base/rnbo-loader/BOUNDED-FILTERS.md).

### 4.5 Meaning of the existing compatibility evidence

The historical host sweep covers 222 patches: 212 normal-profile passes, five conservative-profile routes, four expected bridge rejections and an original visual-Gen gate. A later Gen expansion reports 165 passing fixtures exercising 144 of 155 catalogue entries in the tested forms. That later expansion does not mean the entire earlier 222-case sweep was rerun.

The hardware collection contains 15 playable test designs with separately recorded outcomes. Its CSV includes observations and a case without a distinct hardware-playback confirmation. Treat the host matrix, generated-code audits, native FM1 builds, user-reported auditions and timed physical tests as separate evidence categories. None is an ESP32 performance guarantee. [Compatibility](https://github.com/little-scale/fm1-rnbo/blob/3b46afcd022f10a7f82be99a613bdc98b875c209/fm1-base/rnbo-loader/COMPATIBILITY.md), [Gen coverage](https://github.com/little-scale/fm1-rnbo/blob/3b46afcd022f10a7f82be99a613bdc98b875c209/fm1-base/rnbo-loader/GEN-SUPPORT.md), [hardware results](https://github.com/little-scale/fm1-rnbo/blob/3b46afcd022f10a7f82be99a613bdc98b875c209/fm1-base/rnbo-loader/hardware-tests/HARDWARE-RESULTS.csv).

This port should compile RNBO-generated implementations, not reimplement an RNBO object whitelist. Object support is constrained by the exporter, generated code, available services, resource budgets and tested forms. A previously passing object needs to pass the new target's build and runtime checks as well.

## 5 What to reuse from the ESP32 project

| Existing area | Reuse | Required RNBO change |
| --- | --- | --- |
| `firmware/components/board_audio/` | I²S ownership, codec setup, mono/stereo sinks, capture | Accept the new runtime's block size and float output path |
| `firmware/components/headless_io/` | BOOT polling, optional ADC, atomic snapshots | Map snapshots to RNBO parameters instead of SynthDef buses |
| `firmware/main/main.c` | Task placement, maintenance handshake, diagnostics | Replace SynthDef graph/voice preparation and render calls |
| `firmware/components/instrument/output_volume.c` | Final gain ramp, finite handling, PCM conversion | Extract engine-neutral interfaces; support 256 samples |
| `firmware/components/patches/` | Framing, integrity checks, bounded staging, durable update approach | Introduce a native-module manifest and loader |
| `device_network.c` | Identity, pairing, discovery and network control structure | Advertise an RNBO runtime and compatible capabilities |
| `firmware/components/ui/touch_ui.c` | Header, touch ownership, Controls, volume, status, Panic | Replace the SC source renderer with RNBO overview/parameters |
| `host/studio.py`, browser assets | Local service, USB ownership, upload lifecycle | RNBO export/build jobs and native artifact review |
| `host/ide_bridge.py` | Per-device locking, target resolution, revisions, ordered streams | Extract generic control infrastructure; add MIDI/RNBO actions |
| `host/control_client.py` | Acknowledged delta baselines, revisions and bounded event patterns | Remove SynthDef control/gate assumptions |
| `host/capture.py`, protocol checker | Capture integrity, format and recording-ID checks | New runtime capability/protocol negotiation |
| `host/qualify_headless.py` | Backup/restore and actual PCM assertions | RNBO fixtures and native package handling |
| Build profiles and provenance | Separate targets and source/config hashes | Rename profiles and include RNBO and loader identities |

Do not bring `fm_load`, `fm_render`, UGen dispatch, SynthDef parsing, SC compilation or the copied FM1 SynthDef engine into the RNBO render path. Some reusable C files include engine headers or use engine-specific structures; extract their useful behaviour rather than leaving a hidden interpreter dependency.

## 6 Audio profile and scheduling

### 6.1 Start with 256 samples

ESP32-S3 can render 256-sample blocks. The software render vector and the I²S DMA descriptor size do not need to match. The existing 128-frame DMA buffers can carry a 256-frame render as two successive DMA-sized portions through the driver.

At 44,100 Hz:

| Render vector | Render period | Suggested initial 70% busy-time budget |
| --- | ---: | ---: |
| 64 | 1,451.25 microseconds | 1,015.87 microseconds |
| 128 | 2,902.49 microseconds | 2,031.75 microseconds |
| 256 | 5,804.99 microseconds | 4,063.49 microseconds |

A larger vector can reduce per-block overhead and give the scheduler more room. It does not divide the arithmetic cost of a patch by four. Boundary-only controls become coarser. Correctly implemented RNBO event timestamps can still place events within a vector; arriving after rendering has begun cannot be repaired by a timestamp alone. DMA buffering adds latency independently of the render period.

The initial acceptance target should cover **Main plus FX plus event dispatch, volume and PCM conversion** within the chosen budget. Measure worst cases and overruns as well as averages. Report audio busy time as a percentage of one audio core's available time, not a percentage of both CPUs combined.

Use `CPU_percent = 100 * busy_microseconds * sample_rate / (rendered_frames * 1000000)` for that load calculation. Ordinary blocking while waiting for I²S pacing is not DSP busy time; track it separately. Report maximum block time, blocks beyond the full render period, driver failures and queue events as separate diagnostics. A sampled CPU percentage or an empty error counter alone cannot establish a worst-case timing bound.

### 6.2 Changes required when moving the framework from 64 to 256

Audit all of these together:

- The exporter invocation and generated patch configuration.
- Runtime prepare and render vector checks.
- Input, output, temporary and PCM buffer dimensions.
- Event offset bounds and sample-to-time conversion.
- CPU percentage divisors and budget comparisons.
- Snapshot cadence and output statistics.
- Fade durations, which should be expressed in samples or time.
- Park/drain state transitions and DMA occupancy calculations.
- Capture's last partial block.
- Host admission, package manifests, test fixtures and reference outputs.

Do not globally change the upstream SynthDef engine's `FM_BLOCK` and assume that creates an RNBO runtime. Give the new project its own engine-neutral audio configuration, passed consistently to the wrapper and host compiler.

The current maintenance state machine uses block counts. Copying the same counts at four times the vector length would make its transitions four times longer. Recalculate them using the fade interval and actual DMA drain requirement. With six 128-frame descriptors, nominal descriptor capacity is 768 frames, approximately 17.4 ms at 44.1 kHz. That capacity is not a measurement of complete end-to-end latency.

For 256-frame stereo buffers, two float32 channels occupy 2,048 bytes. Separate Main and FX buffers plus an interleaved int16 sink need 5,120 bytes before additional scratch or optional zero-input buffers. Keep these buffers out of deep stack frames. Recheck stack high-water marks; the current 64-frame measurements cannot qualify the new configuration.

### 6.3 Thread ownership

Retain the existing broad arrangement:

- Audio task on core 1, high priority; current shell uses priority 20.
- Control/maintenance task on core 0; current shell uses priority 3.
- UI, network, ADC polling, compiler work and flash storage outside the render path.
- Internal RAM for DMA-critical buffers, task stacks and required control structures.
- Deliberate placement of large state in PSRAM.

Only the audio owner should mutate a running RNBO instance. USB, Wi-Fi, MIDI and touch producers enqueue bounded events. Construction and destruction occur while the instance is detached and audio ownership is explicitly transferred or parked. UI drawing and network handlers must not call `setParameterValueNormalized` directly on a concurrently processing patch.

A double-buffered parameter snapshot or fixed atomic input bank can serve high-rate physical controls, but the audio owner still performs the RNBO parameter update at the defined point. Event-like messages, especially MIDI and triggers, need queues rather than a last-value mailbox.

## 7 Runtime and module ABI

### 7.1 Separate the runtime from the final PCM sink

The runtime should process planar float32 audio. Proposed flow:

```text
Main outputs L/R float32
         |
FX inputs L/R float32 -> FX outputs L/R float32
         |                  |
         +--- bypass -------+
                  |
           module gain ramp
                  |
         finite checks and saturation
                  |
      AMOLED mono or XIAO stereo int16
```

Do not convert the Main signal to FM1's 24-bit integer words and back to float before FX. Reuse the ESP32 output conversion behaviour once, at the final sink. Decide and document headroom/downmix gain; 100% module volume means unity on that module control, not permission to remove fixed output headroom or saturation handling inherited from the sink.

Initial module contracts can be deliberately narrow:

| Role | Audio inputs | Audio outputs |
| --- | ---: | ---: |
| Main | 0 | 2 |
| FX | 2 | 2 |
| Bypass | No module required | Route Main directly |

Support for an external ADC/audio-input device is a later feature. FX receiving Main internally does not require physical audio input hardware.

### 7.2 Proposed C boundary

Define a new versioned C ABI. Do not expose `RNBO::CoreObject`, STL containers, C++ vtables or generated class names across the boundary. The following are required operations, not an implemented header:

| Operation | Purpose and ownership |
| --- | --- |
| Obtain descriptor | ABI size/version, role, channel counts, rate, vector, required services and limits |
| Create instance | Prepare an opaque context while detached from audio |
| Prepare | Allocate bounded state, prepare engine and perform declared warm-up |
| Process | Caller-owned planar buffers, exact frame count, authoritative sample position |
| Deliver event | MIDI, parameter or supported message; called by the audio owner |
| Read parameter metadata | Stable IDs, names, units, bounds, defaults, steps and conversion functions |
| Read parameter snapshot | Actual and/or normalized values without UI retaining module-owned pointers |
| Reset or Panic | Defined stop/reset behaviour without unbounded work in the immediate mute path |
| Statistics | Allocations, late allocations, errors, invalid samples and timing counters |
| Destroy | Release or retire state after the audio owner has detached it |

Every descriptor needs an explicit byte size and ABI major/minor compatibility rule. Use fixed-width integers for stable fields and validate pointer width and target ABI. A native function table is an in-memory structure; it is not the serialized package header. Parse wire/package fields with explicit lengths and byte order rather than casting incoming bytes to C structs.

The host should copy parameter strings and display metadata into shell-owned storage before releasing a module. Do not retain pointers into unloaded ELF memory. Parameter conversion must remain available even when a patch has no visual layout; the FM1's optional visual footer is not an adequate permanent location for that service.

### 7.3 Parameter semantics

Use the exported stable parameter identity/path as the canonical key; display labels can be duplicated and can change. Maintain a revision-specific mapping to compact indices for events.

Support both forms explicitly:

- **Actual value:** Hz, milliseconds, dB, enumeration index or the parameter's native units.
- **Normalized value:** 0 to 1 for sliders, XY and physical controls.

RNBO's conversion functions handle ranges, exponents and stepped parameters. Do not assume a linear mapping from normalized values or show `normalized * 100` as the native value. The FM1 bridge already uses RNBO's normalized conversion and setter; preserve that behaviour. Keep bounds and conversion available to the browser and the display.

The FM1 wrapper's 16-parameter limit and eight-knob view are adapter limits. A proposed ESP32 first release can support a bounded 128 exported parameters, subject to measured metadata and event storage. Make the limit a capability and reject larger exports clearly. The exact value is a new project budget, not existing tested support.

### 7.4 MIDI and event timing

Deliver complete MIDI messages with their channel intact. Test note-on, note-off, note-on with velocity zero, sustain, pitch bend, pressure and CC routing as supported by the wrapper. Do not reuse the FM1 ABI 1 mono-priority merger for a polyphonic patch.

Use a 64-bit sample-frame clock in the shell. Convert scheduled event positions to the RNBO time representation at a defined boundary. Preserve double-precision scheduler time even when signal values are float32. Handle past events and queue saturation explicitly; do not turn them into unrelated parameter writes.

For an event targeted inside a 256-sample block, prove the selected RNBO API and wrapper honour its offset. If the first version only supports block-boundary delivery, declare and measure that granularity. Splitting a fixed-vector patch into arbitrary process lengths is not an acceptable shortcut unless that export is qualified for it.

Reserve a path for immediate mute/cancellation even when the ordinary event queue is full. Define overflow handling for note-offs and sustain release so congestion does not silently leave notes held. Route MIDI to Main by default; delivery to FX should be an explicit supported choice rather than an accidental duplicate.

### 7.5 Main and FX isolation

There must be independent instances, state, random generators, parameter sets, clocks and allocation accounting for Main and FX. Loading an FX module must not overwrite Main's logger, arena or global state. Test two copies generated with the same class name and test the same compiled module loaded into two independent contexts if that is advertised.

The original bridge has file-level globals, a shared static arena, `RNBO::console` and `RNBO::s_globalRandom`. Simply linking it twice into one application is not an instance-isolation design. For dynamically loaded modules, require module-local symbols and verify the loader's binding behaviour. Do not export an unrestricted C++ runtime namespace into a global symbol registry.

A module may support only one instance per loaded image in the first implementation. If so, declare that limitation and load independent images for Main/FX. General multi-instance support must be separately implemented and tested.

## 8 Allocation and initialization

### 8.1 Do not copy the global allocator overrides into ESP-IDF

ESP-IDF, LVGL and network code also allocate memory. A process-wide replacement of global `new` with the FM1 bump arena could redirect unrelated allocations, make normal deletes ineffective, or exhaust a patch arena during UI/network activity.

For the first statically linked bring-up, use the official custom-platform mechanisms and a deliberate allocation strategy. Normal IDF C++ allocation can remain available during detached initialization, with task-aware heap tracing to identify allocations missed by the RNBO platform hooks. Measure actual placement rather than assuming every allocation reached PSRAM.

For native modules, an isolated module-local allocator is appropriate only after proving that every allocation route and imported symbol binds as intended. This includes generated `new`/`new[]`, arrays, buffer wrappers, lists, event queues and nested/polyphonic patch objects. A counter around `RNBO::Platform::malloc` alone does not necessarily cover them all.

A monotonic arena is useful for patch lifetime storage. Realloc-by-copy consumes additional space, and no-op free does not reclaim it until retirement. Long-running patches that grow lists or reschedule through allocating paths can exhaust such an arena even if their instantaneous live state is small.

Use the modern compiler's C++ allocation and initialization contracts. The freestanding FM1 declarations can conflict with standard placement-new declarations or omit sized/aligned deallocation forms expected by a newer compiler. Audit the actual undefined symbols, including any `__cxa_*`, static-guard or exception support routines, and either provide an intentional compatible path or reject the module. Do not resolve an unexpected C++ dependency by exporting the entire firmware symbol space.

### 8.2 Preparation is a measured lifecycle

Recommended preparation sequence:

1. Validate package metadata and reserve all declared resources.
2. Load and relocate code, then perform the selected loader's initialization lifecycle.
3. Construct the generated patch with allocation permitted.
4. Initialize and prepare at 44,100 Hz and 256 samples.
5. Set initial parameter values and required external data bindings.
6. Run declared warm-up blocks while detached from the audible pipeline.
7. Exercise first-event paths in qualification: first note, first release, first clock, list growth boundaries and parameter extremes.
8. Record allocated bytes and high-water marks, then enforce the real-time allocation policy.
9. Hand the ready instance to the audio owner and fade in.

Warm-up advances clocks and oscillator/envelope state. Record how many blocks were processed, and use the same preparation sequence for reference comparisons. It is not a substitute for testing delayed allocations that occur seconds later.

Do not use the FM1 wrapper's watchdog spin as the normal ESP32 allocation-error policy. Mark the instance faulty, suppress its output through the shell, and arrange safe retirement or reconstruction. Arbitrary faults in native code may still require a reset; a recoverable return status cannot contain every C++ memory error.

### 8.3 Constructors and destruction

In a normal statically linked ESP-IDF C++ application, the framework handles static initialization. Do not additionally walk the FM1 constructor tables.

The reviewed Espressif loader source runs pre-init/init arrays once when requesting the entry point and runs finalizers during deinitialization. Verify that behaviour in the exact locked version. Do not call both its lifecycle implementation and an unmodified FM1 manual constructor loop. Also verify that any initialization preceding the module handshake has a valid allocation path. [Reviewed loader lifecycle](https://github.com/espressif/esp-iot-solution/blob/d2d935d0ee3e78deffa3981cc8c39ac8f534932b/components/elf_loader/src/esp_elf.c).

Destruct the patch while its code, runtime globals and allocator still exist. Only then deinitialize/unmap the ELF image and release its memory. Wait for the audio owner to acknowledge detachment before doing either operation.

### 8.4 Randomness

Offer an explicit seed policy:

- Deterministic seed for comparisons and reproducible patches.
- Fresh seed on instance creation for musical variation.

The old FM1 bridge reseeds its target helper to a constant on reconstruction. Do not accidentally preserve that as a promise of fresh random values. Conversely, do not make reproducible test output depend on uncontrolled hardware randomness. Seed once per instance or explicit reset, not once per block, and keep Main and FX streams separate.

## 9 Native loading strategy

### 9.1 Recommended sequence

First establish one statically linked RNBO patch on each board. This proves export, compilation, sample format, state allocation and audio independently of a loader. It is a bring-up milestone, not the final patch deployment architecture.

Then qualify the Espressif ELF loader for a permanent runtime plus uploaded native modules. Its reviewed component supports ESP32-S3 and loading executable code into PSRAM. This avoids treating scarce internal instruction RAM as the only possible module storage. It still needs a real audio performance and lifecycle test on these targets. [Espressif ELF loader](https://github.com/espressif/esp-iot-solution/tree/d2d935d0ee3e78deffa3981cc8c39ac8f534932b/components/elf_loader).

Keep full-application firmware builds as a development fallback. They are less convenient for frequent patch updates and change the storage/reboot model, especially if Wi-Fi firmware OTA is required.

### 9.2 Loader proof before a large UI effort

Build a small Xtensa test module before adapting a complex RNBO export. It should prove:

- Integer and float callbacks from the host.
- Float arrays in PSRAM and shell-owned audio buffers.
- Global initialized data, BSS and static constants.
- Constructor execution exactly once and finalization in the right order.
- C++ virtual calls used internally by the generated runtime.
- Stable function pointers returned by the module's C entry point.
- Two simultaneous modules with identical internal symbol names.
- Repeated load, process, detach and unload without memory loss.
- Correct instruction/data address aliases and cache synchronization.
- Defined rejection of unsupported imports and relocation types.

Use the loader's build examples and generated compiler flags as the starting point. Do not invent a flat binary loader by changing FM1 addresses to guessed ESP32 addresses. Xtensa literal pools, relocations, call conventions and long-call handling must be correct for the selected compiler and loader.

The normal application should expose a narrow, versioned host service table. An example-module entry can populate a descriptor through a validated handshake, or a supported dynamic-library interface can resolve a single C entry symbol. These are alternative integration mechanisms; neither the FM1 API table address nor POSIX `dlopen` behaviour should be assumed without testing the selected loader path.

### 9.3 Version and API details

The inspected component manifest declares `2.0.0` and an IDF dependency of `>=4.4.3`. That declared range is not qualification with this project's IDF 5.5 configuration. Pin the chosen component and all transitive dependencies after the loader spike passes.

The reviewed header uses the length-aware signature:

```c
int esp_elf_relocate(esp_elf_t *elf, const uint8_t *pbuf, size_t size);
```

Older examples show a two-argument function. Use the header from the locked source, not a tutorial from another version. The component's PSRAM configuration includes `CONFIG_ELF_LOADER_LOAD_PSRAM`; the reviewed Kconfig selects the required cache-offset support for ESP32-S3. Verify the resolved sdkconfig and generated component version in every build. [Manifest](https://github.com/espressif/esp-iot-solution/blob/d2d935d0ee3e78deffa3981cc8c39ac8f534932b/components/elf_loader/idf_component.yml), [header](https://github.com/espressif/esp-iot-solution/blob/d2d935d0ee3e78deffa3981cc8c39ac8f534932b/components/elf_loader/include/esp_elf.h), [Kconfig](https://github.com/espressif/esp-iot-solution/blob/d2d935d0ee3e78deffa3981cc8c39ac8f534932b/components/elf_loader/Kconfig).

### 9.4 Code memory and PSRAM

Do not assume a pointer returned by ordinary PSRAM allocation is directly callable as a function. Use the loader's supported mapping and relocation path. Whole-application instruction relocation to PSRAM is also different from loading an arbitrary patch image at runtime.

Keep hot shell code in internal instruction memory where measured necessary, but preserve internal RAM for stacks, DMA and Wi-Fi. Executable module code and large delay state can compete for the external memory/cache system. Measure performance with the display and Wi-Fi active, not only with a tiny isolated patch.

PSRAM and cached flash have restrictions around flash operations; the existing maintenance/park design should be retained for module persistence and code changes. IDF documents explicit internal/DMA allocation capabilities and instruction-from-PSRAM options. [IDF 5.5 external RAM guide](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32s3/api-guides/external-ram.html).

### 9.5 Native code trust

A loaded native module is not a sandboxed graph. It can fault or corrupt the runtime despite using a narrow documented API. Treat the compiler and approved module source as trusted, authenticate remote deployment, and validate all container/ELF sizes before loading. Hashes and CRCs detect corruption; they do not establish who authorised an executable.

Do not export the entire ESP-IDF symbol table just because an example enables it by default. Start with the smallest supported import set and record it in the review output. Restricting imports improves compatibility and reduces accidental dependencies; it is not memory isolation.

## 10 Proposed module package

Use a distinct format and extension, for example `.rnbos3`. The name is a proposal; it must not be confused with `.rnbom`, `.scsyndef`, or an ESP32 application `.bin`.

Suggested manifest fields:

```json
{
  "format": "rnbo-esp32s3-module",
  "format_version": 1,
  "runtime_abi": {"major": 1, "minor": 0},
  "architecture": "xtensa-esp32s3",
  "sample_rate": 44100,
  "block_frames": 256,
  "role": "main",
  "audio_inputs": 0,
  "audio_outputs": 2,
  "rnbo_version": "1.4.4",
  "polyphony": 1,
  "startup_policy": "autostart",
  "elf_bytes": 0,
  "required_host_services": [],
  "limits": {"state_bytes": 1048576},
  "hashes": {"elf_sha256": "<computed>", "source_sha256": "<computed>"}
}
```

This is a schema illustration, not a valid upload: lengths and digests must be generated from the actual artifact. Add measured section sizes, initialization peak, parameter schema hash and the exact toolchain/loader ABI identity to the build review.

Package contents should distinguish:

1. Mandatory executable ELF.
2. Mandatory parameter/role metadata needed for admission.
3. Optional editable `.rnbopat` source.
4. Optional bounded layout metadata.
5. Provenance and applicable license notices.
6. Optional external-data assets only after that feature is implemented.

Validate architecture, ABI, vector, sample rate, channels, role, image/state budgets and dependencies before staging activation. Use checked arithmetic for all offsets and lengths. Verify every region fits the package without overlap. Define deterministic JSON encoding or another explicit canonical format if the manifest itself is hashed or signed.

The initial native image/state budgets should be configurable. A reasonable experiment is a 512 KiB executable-container ceiling and 1 MiB state ceiling per stage, then adjust from measured exports and whole-system admission. These are proposed ceilings, not measured RNBO requirements. Serialized ELF size, loaded text/data/BSS size and initialization peak are separate quantities.

Source attachment must not silently inherit the SynthDef tool's source-size assumptions. Real `.rnbopat` files can be much larger than a short SC snippet; the FM1 saw/cutoff/delay source in the reviewed tree is already over 128 KiB. Make attachment limits explicit, allow source omission, and keep source recovery separate from the minimum executable package.

## 11 Memory and numerical policy

### 11.1 Existing XIAO results

The current SynthDef XIAO has 8 MiB flash and 8 MiB octal PSRAM. Its five-minute combined Comb Cloud KR plus MiVerb test applied 2,400 control events, captured actual output buffers seven times, and reported no increases in audio/DMA/clipping/nonfinite fault counters.

| Measurement during that SynthDef workload | Result |
| --- | ---: |
| Maximum sampled average audio CPU | 67.9% |
| Maximum sampled peak audio CPU | 80.7% |
| Free internal RAM | 164,867 bytes, constant across samples |
| Largest internal free block | 90,112 bytes |
| Free PSRAM | 5,261,472 bytes, constant across samples |
| Audio stack remaining | 12,680 bytes of 16,384 |
| Control stack remaining | 2,836 bytes of 8,192 |

Those are **64-frame SynthDef results**, not RNBO or 256-frame results. The new runtime removes some SynthDef storage and adds executable-module, C++ and RNBO state costs. Re-measure the complete system. [Qualification report](https://github.com/little-scale/synthdefs-for-esp32-s3-touch-amoled-1.8/blob/59e19441408a4df14cf2f5b6e8ba527929e74d9b/evidence/xiao-dsp-qualification.json).

### 11.2 State budgets and delays

The SynthDef implementation reserves 1 MiB per stage for its large arena. An RNBO arena must also hold object state, tables, event structures and allocation headers, so equal arena sizes do not imply equal available delay time.

For raw float32 storage at 44.1 kHz:

| Delay duration | Mono data | Stereo data |
| --- | ---: | ---: |
| 1 second | 176,400 bytes | 352,800 bytes |
| 2 seconds | 352,800 bytes | 705,600 bytes |
| 5 seconds | 882,000 bytes | 1,764,000 bytes |

These are sample data calculations before power-of-two capacity rounding, interpolation guards, object state and allocator overhead. With two power-of-two rings, a two-second stereo delay can consume a full 1 MiB. Float64 buffers double sample storage. Do not equate float32 signal processing with every RNBO Data or delay object automatically using four-byte storage.

Retain bounded delay and averaging adaptations where their semantics have been qualified. The FM1 visual Gen importer has its own 24 KiB conservative per-graph estimate and a default 2,048-sample delay. Those are FM1 export policies, not natural ESP32 limits. Make them configurable in the new target and include their values and inferred changes in provenance. Do not silently shorten an explicit user delay to fit a budget.

Admission needs room for the shell, Wi-Fi, display, capture, Main, FX and any temporary replacement image. If old and new instances coexist for validation, include both in the peak. If that cannot fit, document the alternative: park, retire, construct, and restore the durable old package if construction fails. That path has a longer audible interruption and must not be called seamless.

### 11.3 Precision

Keep audio calculations float32 initially. Preserve double scheduler time and any intentional data types that the generated design requires. Use strict floating-point options as the reference configuration; avoid global fast-math when finite checks and comparison semantics are part of fault detection.

Audit generated sample loops and their callees for unintended double math. Some float64 helpers are legitimate for block clocks and must not be banned globally. Record any changed literal, overload, buffer type or fast-phase routine and compare its output against a matching reference.

Global conversion to 16-bit internal processing is not the starting optimisation. It would require a different arithmetic implementation and would change filter, envelope and feedback behaviour. Final output remains int16 for the existing sinks; RNBO and Main/FX routing remain float32.

## 12 Headed target using the Waveshare AMOLED V2

### 12.1 Hardware baseline

Use the V2 ESP32 S3 Touch AMOLED 1.8 board with 16 MiB flash and 8 MiB PSRAM. Keep the validated BSP, codec and power setup together. The current panel is 368 by 448 pixels; the existing application drives it through the pinned BSP/LVGL components.

The checked audio adapter uses ES8311 output, mono 16-bit Philips I²S, MCLK enabled and a 256-times sample-rate MCLK setting. It owns the I²S channel and codec; a second call to `bsp_audio_init()` must not create another owner.

The pinned BSP header defines these audio/control pins:

| Function | GPIO |
| --- | ---: |
| I²C SCL | 14 |
| I²C SDA | 15 |
| I²S BCLK | 9 |
| I²S MCLK | 16 |
| I²S word select | 45 |
| I²S data out | 8 |
| Power amplifier enable | 46 |

Use the BSP macros in source rather than duplicating literals through the application. GPIO 10 is defined for I²S input by the BSP, but the checked adapter does not configure audio capture. That does not establish an RNBO physical-input feature. The board pins above come from the installed pinned BSP; its package/version and source provenance should be retained in the new build. [Audio adapter](https://github.com/little-scale/synthdefs-for-esp32-s3-touch-amoled-1.8/blob/59e19441408a4df14cf2f5b6e8ba527929e74d9b/firmware/components/board_audio/board_audio.c), [Waveshare provenance](https://github.com/little-scale/synthdefs-for-esp32-s3-touch-amoled-1.8/blob/59e19441408a4df14cf2f5b6e8ba527929e74d9b/upstream/WAVESHARE_SOURCES.json).

GPIO 21 illustrates why board-specific initialization must stay separate: it is the Waveshare touch interrupt in the pinned BSP and the XIAO activity LED in the headless driver. A common unconditional LED initializer on that pin would interfere with the headed target.

Retain a stereo internal graph even though the built-in speaker sink is mono. Apply a documented downmix at the output boundary. Avoid doubling the signal by summing left and right without accounting for gain. The same stereo module should remain valid on the XIAO sink.

### 12.2 Power, display and audio initialization

Reuse the board's working initialization sequence before making cosmetic or power optimisations. Prior development encountered black-screen and startup-memory problems; restarting from a generic ESP32 display example would discard useful board-specific work.

The current audio adapter stops DMA after codec initialization and records pre-owner startup overflow events separately. The audio task starts the measured stream. Its codec mute path verifies the register transaction because the codec-device layer used by the project does not propagate every mute callback result. Preserve those behaviours while swapping the DSP engine.

The existing LVGL configuration has a 64 KiB heap and disabled theme transitions/grow behaviour. Keep the working cache and buffer settings for initial RNBO bring-up. A snapshot of the full RGB565 panel is about 330 KiB; account for that optional allocation separately from regular partial draw buffers.

### 12.3 Proposed two-screen interface

Use two main screens:

**Patch overview:** a bounded diagram derived from the original RNBO patch, patch name, CPU load, battery state, Wi-Fi state and receive cue. Keep Controls at bottom left and Panic at bottom right. Touch in the play area can update explicitly bound XY parameters.

**Controls:** scrollable parameter controls, module ID/name, output volume, Main/FX selection or replacement status, FX bypass, and explicit run/stop/resume controls.

The original SC code screen is not an RNBO patch renderer. Do not present generated C++ or raw `.rnbopat` JSON as its default substitute. Reuse the FM1 layout extraction concepts, with the RNBO description supplying parameter identities and labels.

The FM1 visual format is fitted to 240 by 166 pixels with limits of 96 objects and 384 wire segments. Recompute layout for the AMOLED content area, with deterministic bounds and a parameter-list fallback for dense or unsupported layouts. Embedded subpatches can remain boxes initially. Preserve source coordinates in host metadata if scrolling or later zooming is planned. [Layout compiler](https://github.com/little-scale/fm1-rnbo/blob/3b46afcd022f10a7f82be99a613bdc98b875c209/fm1-base/rnbo-loader/tools/layout.py).

Keep the existing readable title and battery insets. The activity dot should track the Wi-Fi symbol's position as the RSSI text changes. Background queries stay dark; validated data/control reception flashes the cue. A receive cue confirms receipt, not successful audio generation.

Use the proven single-touch interaction model with dedicated scroll regions where necessary. The existing hardware/workflow did not establish reliable two-finger scrolling. A drag that starts on a scrollbar, parameter slider, Controls or Panic must remain owned by that control until release and must not become an XY note halfway across the screen.

### 12.4 Touch bindings

Keep a board-independent logical input vocabulary, for example `touch_x`, `touch_y` and `touch_gate`. The proposed normalized values are X/Y in 0 to 1 and gate in 0 or 1, with orientation declared in metadata.

Bind these to selected RNBO parameter IDs through module metadata or host configuration. An RNBO patch uses ordinary `param` objects and can be tested from Max with the same parameters. It does not need to know GPIO numbers or the Waveshare touch driver.

Touch need not generate MIDI unless a module explicitly requests that mapping. Preserve autonomous playback when no bindings exist. Releasing the finger should update the gate binding and stop only the sound the authored patch associates with that gate.

### 12.5 Panic and resume

Panic should latch final output silent promptly, invalidate pending events and initiate bounded cleanup for both stages. Reconstructing delay state or dispatching thousands of potential note-offs must not delay the immediate mute.

Provide a clear resume path on Controls or through the network API. For autonomous patches, a new touch is not a reliable or appropriate universal restart command. Document whether a fresh note-on can resume a MIDI instrument; do not let an old queued note release the Panic latch.

Battery status must use the existing board power-monitor path outside the audio task. Preserve unknown/disconnected states; do not infer a battery percentage from USB presence.

## 13 Headless target using the XIAO ESP32S3

### 13.1 Board and I²S output

The checked XIAO has an ESP32-S3, 8 MiB flash and 8 MiB embedded octal PSRAM. It uses the same 240 MHz CPU configuration as the AMOLED build. Removing display and codec support frees background work and memory; it does not make RNBO arithmetic intrinsically faster.

Retain the established pin assignment:

| Function | XIAO label | GPIO |
| --- | --- | ---: |
| I²S BCLK | D8 | 7 |
| I²S word select | D9 | 8 |
| I²S data out | D10 | 9 |
| MCLK | Not provided | Unused |
| BOOT input | BOOT | 0 |
| Activity LED | Onboard | 21, active low |
| Optional analog input 0 | D0 | 1, ADC1 channel 0 |
| Optional analog input 1 | D1 | 2, ADC1 channel 1 |

The current sink is stereo, 44.1 kHz, signed 16-bit Philips I²S with six 128-frame descriptors. It configures I²S TX only. A connected external DAC must support this format and operation without MCLK, or the board adapter needs an explicitly different clock/output profile. Do not assume the board provides an analog audio output. [Headless guide](https://github.com/little-scale/synthdefs-for-esp32-s3-touch-amoled-1.8/blob/59e19441408a4df14cf2f5b6e8ba527929e74d9b/docs/HEADLESS.md), [I²S implementation](https://github.com/little-scale/synthdefs-for-esp32-s3-touch-amoled-1.8/blob/59e19441408a4df14cf2f5b6e8ba527929e74d9b/firmware/components/board_audio/board_audio_i2s.c).

Display, Waveshare BSP, touch and ES8311 components should be absent from this target's dependency graph. Verify the map file and component list; leaving the UI task unused is not the same as excluding those dependencies.

### 13.2 Physical control mapping

The existing logical input assignment is useful to preserve in external metadata:

| Logical input | Existing SynthDef bus | RNBO proposal |
| --- | ---: | --- |
| Analog 0 | 8 | Bind normalized snapshot to a chosen parameter ID |
| Analog 1 | 9 | Bind normalized snapshot to a chosen parameter ID |
| BOOT held | 10 | Bind 0/1 to a gate, trigger or other chosen parameter |

These bus numbers are a project convention, not RNBO's built-in audio or control buses. RNBO bindings can expose the same logical controls to Max or another host without hardware. Store GPIO-specific assignments in the board/runtime layer.

The current IO implementation polls at approximately 100 Hz, debounces BOOT and publishes atomic float snapshots. Analog input is optional and disabled by default. When enabled, it reads 12-bit ADC1 values, normalizes by 4,095 and smooths with an IIR coefficient of 0.2 per poll. It is a basic control path, not a calibrated voltage/CV acquisition system. Preserve the ability to build without analog inputs when no controls are connected. [IO implementation](https://github.com/little-scale/synthdefs-for-esp32-s3-touch-amoled-1.8/blob/59e19441408a4df14cf2f5b6e8ba527929e74d9b/firmware/components/headless_io/headless_io.c).

External controls must respect the board's 3.3 V input limits. A bipolar or higher-voltage modular CV input needs suitable analog circuitry. Keep that hardware design outside a software-only ADC mapping claim.

Define input ownership. For example, a bound potentiometer can continuously own a parameter, or the binding can suspend after a remote edit until pickup. Without a rule, ADC polling can immediately undo a value set from Wi-Fi. Define how unavailable inputs initialize and whether a physical button edge sends a trigger or a sustained gate.

BOOT is also a bootstrapping control during reset. Its musical use while firmware is running must not change recovery instructions. Activity LED behaviour should follow accepted data traffic, with status queries remaining dark.

### 13.3 Operation without a host

Standalone startup must need neither a browser nor Max after the compiled package has been saved. Load Main and optional FX, apply persisted parameters, restore volume/bypass, and follow startup policy. If Wi-Fi is absent, local audio and physical controls should still run.

Expose identity, CPU, memory, faults, current module IDs, active state and input values through USB and Wi-Fi status APIs. Report battery status as unavailable unless a measured battery-monitor path is actually implemented; the headless board has no display or established battery-reading implementation in this project.

### 13.4 Validate without a DAC

Retain the existing post-volume PCM capture facility. It records the exact PCM buffer after a successful I²S driver write, allowing stereo, gain, silence and waveform checks on the computer.

The current implementation stores up to 44,100 stereo frames: 176,400 bytes of int16 PCM. It negotiates 1,024-byte reads and uses a recording ID so another controller cannot silently replace the recording during download. A 256-frame runtime must correctly copy only the remaining frames at the end of a one-second recording.

This proves software rendering and the submitted output buffers. It does not prove electrical clock/data waveforms, DAC compatibility, analog noise, speaker level or physical listening quality. Current XIAO Wi-Fi operation, driven ADC inputs and external DAC output remain distinct hardware qualification tasks.

The SynthDef implementation downloaded full captures alongside an 8 Hz pattern and separately checked capture IDs, legacy reads, invalid ranges and chunk negotiation. Reuse those adversarial checks for the new protocol. Do not let a multi-second download monopolize the USB lock; lock one transaction at a time and validate that the connection still belongs to the intended module.

## 14 Build and dependency separation

Keep separate build directories, sdkconfig files and partition tables for the two targets. The existing XIAO helper deliberately avoids inheriting the AMOLED configuration and disables IDF Component Manager after using its required local dependencies. A new ELF-loader dependency changes that assumption.

Choose one reproducible approach:

- Resolve and lock the required components with Component Manager for each target, while excluding display dependencies from XIAO.
- Vendor the exact permitted loader and helper component sources, record their provenance, and build offline with the manager disabled.

Do not copy `IDF_COMPONENT_MANAGER=0` and then assume a newly declared registry dependency will be fetched. Do not allow an existing sdkconfig from one board to override the other board's defaults unnoticed. [Existing target guard](https://github.com/little-scale/synthdefs-for-esp32-s3-touch-amoled-1.8/blob/59e19441408a4df14cf2f5b6e8ba527929e74d9b/firmware/CMakeLists.txt), [XIAO helper](https://github.com/little-scale/synthdefs-for-esp32-s3-touch-amoled-1.8/blob/59e19441408a4df14cf2f5b6e8ba527929e74d9b/host/xiao.sh).

Reuse the checked QIO flash, octal PSRAM, 80 MHz PSRAM and 240 MHz CPU configurations as the initial hardware baseline. Current cache settings include 32 KiB instruction cache and 64 KiB data cache with 64-byte lines. Profile changes to code placement/cache policy against representative RNBO modules rather than assuming the SynthDef layout is optimal.

For DSP compilation, start with a known optimisation level, disabled exceptions/RTTI where compatible, `-fno-fast-math` and `-ffp-contract=off`. Record the final flags actually used. Obtain the compiler executable from the selected IDF toolchain; the reviewed tool is named `xtensa-esp-elf-gcc`, not necessarily a hardcoded older toolchain prefix.

Replace JieLi-specific Docker/compiler SDK steps. Native ESP-IDF compilation on the configured Mac is sufficient for a first exporter service; a pinned container can be added for reproducibility. The FM1's Linux compiler cache and platform installer are not ESP32 dependencies.

### USB ownership and recovery during bring-up

Disconnect the local service from USB before opening the same port with a direct diagnostic tool or flasher. Do not run a second serial reader beside Studio. Re-enumerate ports after resets rather than treating a development port such as `/dev/cu.usbmodem101` as a permanent device identity.

The working XIAO development flow used esptool's `watchdog_reset` after writing; normal serial-control-line resets were not consistently sufficient in this setup. Pin and document the actual esptool version and reset behaviour used by the new project. If software recovery fails, retain a physical USB reconnect and BOOT-mode recovery procedure for each board.

An application-only write can preserve NVS and module storage when the existing partition layout remains compatible. Changing partitions or erasing flash has different consequences. Keep known-good firmware and package backups before experimenting with the loader or storage layout, and verify the board model/flash size before selecting a firmware artifact.

## 15 Storage and maintenance

### 15.1 Existing partitions

Both checked ESP32 layouts use NVS at `0x9000` for `0x6000` bytes, PHY data at `0xf000` for `0x1000`, and one factory app at `0x10000` for `0x300000`. SPIFFS begins at `0x310000`:

| Board | SPIFFS size | Flash size |
| --- | ---: | ---: |
| AMOLED | `0xcf0000` | 16 MiB |
| XIAO | `0x4f0000` | 8 MiB |

These partition tables do **not** provide OTA application A/B slots. Uploading RNBO modules into data storage can reuse the broad layout. A fallback design that updates whole application firmware over Wi-Fi needs a new partition strategy and its own migration/recovery work. [AMOLED partitions](https://github.com/little-scale/synthdefs-for-esp32-s3-touch-amoled-1.8/blob/59e19441408a4df14cf2f5b6e8ba527929e74d9b/firmware/partitions.csv), [XIAO partitions](https://github.com/little-scale/synthdefs-for-esp32-s3-touch-amoled-1.8/blob/59e19441408a4df14cf2f5b6e8ba527929e74d9b/firmware/partitions-xiao.csv).

### 15.2 Durable package installation

Preserve the existing approach of bounded transfer, integrity checks, compare-and-swap destination metadata and readback verification. Adapt it to native package sizes and schemas.

Recommended sequence:

1. Resolve and confirm the exact device and runtime capabilities.
2. Compare the expected Main/FX generation with the destination.
3. Receive a bounded staged package; reject malformed lengths early.
4. Verify digest and metadata, then perform native admission checks.
5. Enter maintenance as required for flash work and large state changes.
6. Write an inactive generation and verify it from storage.
7. Prepare the replacement, accounting for peak memory.
8. Detach the old instance and activate the new one through the audio owner.
9. Commit the durable selection at a deliberately chosen point.
10. Refresh parameter metadata and resume with a gain ramp.

Document what happens if power or USB fails at each step. A CRC-valid package may still fail native initialization. Retain a known-good generation and a boot policy that avoids an endless crash/retry cycle. A proposed solution is an unconfirmed activation marker plus a known-good pointer, with explicit confirmation after successful preparation and initial processing.

Do not commit NVS/flash for every parameter or LFO update. Persist settings on explicit save or another documented bounded policy. Use a new RNBO storage namespace/schema so old SynthDef files cannot be mistaken for executable modules.

### 15.3 FX bypass and tails

Stopping Main should feed silence to a still-running FX instance so reverb/delay tails can continue. Panic is different: it silences the complete pipeline and initiates full cleanup.

Define bypass precisely. Continuing to process wet audio while routing dry output preserves FX state but retains CPU cost. Suspending FX saves CPU but requires a policy for stale tails when re-enabled. Recommended initial behaviour is direct dry routing in bypass, with FX reset/preparation under maintenance when re-enabling, preserving its parameters. State the short transition behaviour in the UI and tests.

An RNBO Main patch can already contain its own shared master effect. A separate shell FX module comes after that patch; it is not automatically the same internal effect. Display both identities clearly.

## 16 USB Wi-Fi and browser tools

### 16.1 Reuse the local service model

The current ESP32 browser tool talks to a local service which owns USB. The FM1 browser uses Web MIDI/SysEx for its hardware. The ESP32 USB Serial/JTAG interface is not a drop-in Web MIDI transport.

Keep the ESP32 local service as the first browser integration. It can provide export/build status, device discovery, parameter metadata, package review, upload, capture and logs without requiring the browser to directly manage all platform-specific tools.

The existing Studio normally uses localhost port 8765. Give the RNBO service a distinct configurable port if both projects may run together, for example 8766. Use separate session descriptors and tokens. Do not overwrite the SynthDef service's private configuration as an incidental side effect of launching the new project.

The exporter/compiler should run as a background job. Hash the source/configuration, isolate its build directory, report progress, cancel cleanly and check that the artifact still belongs to the source and destination the user reviewed. Build Only must work without a device. Source export, native compilation and upload are three distinguishable stages.

### 16.2 Capabilities and identity

Extend discovery/status with at least:

- Runtime family, such as `rnbo-esp32s3`.
- Board model and stable MAC-derived device ID.
- Friendly name and current network address.
- Runtime ABI, firmware identity and loader version.
- Supported sample rates/vector sizes and active profile.
- Mono/stereo physical sink capability and internal channel contract.
- Package, code/state, parameter and event limits.
- Main/FX generation, running state, bypass and volume.
- Capture, physical-input and UI capabilities.

Preserve permanent IDs independently from DHCP addresses. Require runtime-family compatibility as well as matching IDs. Give pairing credentials and protocol namespaces an explicit migration policy rather than assuming the old SynthDef uploader can speak RNBO.

### 16.3 Remote controls

Provide clearly separate operations for module upload, instance start/stop, parameter update, MIDI/event delivery, FX bypass, Panic, module volume and explicit settings save. A proposed parameter command should state the stage, stable parameter ID and whether the value is actual or normalized.

The existing SC `ESP32` API provides useful target/stream behaviour, but its compiler and note/gate semantics are SynthDef-specific. It should not be advertised as supporting RNBO unchanged. A Max-facing client, generic OSC/HTTP client or new SC adapter can later target the same new control service.

Keep per-device transaction locks. Shared USB capture must release the lock between chunks, and a borrowed connection must reject commands after its owning device is disconnected or replaced. Reuse these tested invariants from `host/ide_bridge.py` and `host/studio.py`.

After an upload, refresh the control schema before starting a new event stream. Existing streams retain their old revision and must fail safely if a patch changes. Do not reinterpret an old compact index against a new parameter list.

### 16.4 Efficient events and omni deployment

Retain acknowledged, revision-specific float32 delta baselines for parameters. Reset them after reboot, reconnect, failed acknowledgements or module changes, and periodically send a complete baseline. Never cull a repeated MIDI note, trigger or note-off merely because its payload equals the previous one; those are events, not persistent values.

An omni upload should compile once and upload the same compatible module bytes to all selected recipients, with per-device verification and failures. First implementations can fan out authenticated unicast transfers with bounded concurrency. Reliable large-file delivery does not require sending raw Wi-Fi broadcast packets.

Identical code does not imply simultaneous activation. Sample-aligned multi-node starts need staged installation plus a future activation time and clock-synchronisation policy. Make that a separate milestone from ordinary group deployment.

RNBO native packages are likely much larger than small SynthDef graphs. A 512 KiB artifact over 256-byte chunks needs 2,048 request/ack transactions before overhead. Do not promise the same upload duration. Negotiate larger or binary transfers only after checking protocol limits, timeout behaviour and task-stack usage; keep live parameter/MIDI traffic small and separate from bulk transfer.

## 17 Browser conversion and patch description

Reuse the FM1 local converter's input validation, job isolation, source hashing, version checks and build review concepts. Replace its pi32v2 build and `.rnbom` output with the new ESP32 compiler/package path.

Support these input modes explicitly:

1. Self-contained `.rnbopat`, using the pinned local converter.
2. A validated Minimal C++ Export directory, using a manifest of required files.
3. A precompiled compatible `.rnbos3` package.

Do not call arbitrary Max `.maxpat` contents or external abstractions supported unless implemented. The FM1 importer has specific support for embedded subpatches and visual/codebox Gen. External sample files, abstractions and external Gen dependencies remain additional integration work.

For the first RNBO FX export, prove two signal inputs and two outputs through the wrapper and description metadata. An export that silently omits or zeros its inputs is not a valid FX implementation.

Show before upload: target(s), Main/FX destination, source identity, RNBO/compiler version, vector/rate, input/output channels, voice topology, parameter count, artifact size, loaded/state budget, applied adaptations and any unsupported dependency. Retain source/layout metadata when requested, but keep executable admission independent from whether a diagram can be drawn.

## 18 Suggested repository structure

This is a proposed structure for the new project, not a directory already implemented:

```text
README.md
LICENSE
THIRD_PARTY.md
UPSTREAM.json
firmware/
  CMakeLists.txt
  sdkconfig.amoled.defaults
  sdkconfig.xiao.defaults
  partitions-amoled.csv
  partitions-xiao.csv
  main/
    main.c
  components/
    audio_runtime/
    rnbo_host/
    rnbo_module_loader/
    module_store/
    control_protocol/
    device_network/
    board_audio_amoled/
    board_audio_xiao/
    physical_inputs/
    ui/
module-sdk/
  include/rnbo_s3_module.h
  wrapper/
  cmake/
host/
  export/
  compiler/
  package/
  service/
  clients/
  web/
examples/
  sine/
  midi-envelope/
  polyphonic/
  delay/
  fx-pass-through/
  fx-delay/
tests/
  host/
  target/
  fixtures/
docs/
evidence/
build/                         # ignored
build/private/                 # ignored credentials and recovery backups
```

An initial reuse map should list every imported file, original URL/commit, license and local changes. Keep generated RNBO exports and tool downloads separate from original integration source. Use an application/module SDK ABI identity rather than linking new packages against whatever firmware happened to be built last.

## 19 Implementation milestones and acceptance gates

### Milestone 0 Establish a reproducible project

Create the new repository and capture the source baselines, license inventory and board profiles. Confirm both builds select the intended flash size and dependencies. Record the actual compiler, resolved config and component lock.

**Exit:** two clean board-specific firmware builds and an explicit map of reused source. No RNBO compatibility claims yet.

### Milestone 1 Restore the hardware shell

Use a simple engine-neutral test signal through the reused float-to-PCM and board adapters. Start with XIAO because capture can verify it without a DAC, then confirm the AMOLED codec/display path. Keep the original projects and known-good binaries available for recovery.

**Exit:** stereo separation on XIAO, correct mono downmix on AMOLED, smooth volume, explicit Panic, stable DMA and correct 256-frame buffer handling.

### Milestone 2 Run a statically linked RNBO minimal patch

Export a two-output oscillator patch at 44.1 kHz/256 frames. Build it with a small C wrapper and measured initialization. Prove parameter changes and compare captured float/PCM output with a matching host build.

**Exit:** clean signal, finite samples, repeatable initialization and no allocation after the permitted preparation phase.

### Milestone 3 Add instrument events and polyphony

Add MIDI envelope, two-voice and four-voice cases. Test repeated note-ons, overlapping releases, sustain, voice stealing, per-channel routing and Panic. Test long-running scheduler time and a declared within-block timing case.

**Exit:** event semantics match the selected RNBO export and no MIDI/control path corrupts state or allocates unexpectedly.

### Milestone 4 Qualify the native loader

Run the small loader fixture, then load the same oscillator module dynamically. Test constructors, imports, address aliases, late callbacks and repeated unloading. Confirm two independent module images can coexist.

**Exit:** dynamically loaded output matches the static build within the declared comparison policy; load/unload memory stays bounded; malformed inputs fail before execution.

If this gate fails, keep static builds as the development route and resolve the loader before investing in a complete patch-upload UI. Do not hide the fallback as if it already provided permanent-player module uploads.

### Milestone 5 Add native package storage and recovery

Implement the versioned package parser, transfer limits, two-generation storage, compare-and-swap install, preparation and known-good recovery. Test interrupted transfer, interrupted commit, constructor failure and incompatible packages.

**Exit:** one saved Main survives reboot, and a failed replacement cannot destroy the durable known-good package.

### Milestone 6 Add the separate FX stage

Begin with a two-input/two-output pass-through FX, then a simple delay. Prove Main stop leaves tails, bypass routes dry, Panic silences both stages, and loading FX leaves Main's state and parameters independent.

**Exit:** float32 Main-to-FX routing, defined bypass transitions and working independent lifecycle/state.

### Milestone 7 Port the host converter and browser

Add `.rnbopat` conversion, raw/prepared export provenance, Xtensa compilation, package review, Build Only and USB deployment. Retain connection ownership and refresh metadata after uploads.

**Exit:** a fresh self-contained patch moves from Max/RNBO source to running Main through the browser, with source and package identity verified.

### Milestone 8 Complete the XIAO controls

Add binding metadata, BOOT, activity LED and optional ADC. Prove autonomous reboot behaviour with no network or host. Add captured-output tests to the repeatable qualification runner.

**Exit:** physical bindings and host parameter edits follow a documented ownership rule; analog-disabled operation remains clean.

### Milestone 9 Complete the headed interface

Add the overview renderer, fallback parameter list, Controls, volume, transport, battery/network/CPU state and Panic. Reuse dedicated scroll ownership. Test with long names, many parameters and layout overflow.

**Exit:** the board can identify, play/control and manage Main/FX without relying on the browser for basic operation.

### Milestone 10 Add Wi-Fi and multiple modules

Pair and discover by stable identity, deploy to one device and a bounded group, and deliver scheduled MIDI/parameters. Separate bulk transfer from live-event limits. Test reconnect, changed DHCP address, a missing node and poor signal.

**Exit:** failures are per-device and visible; stale events cannot affect replacement modules; group success is not inferred from a single acknowledgement.

### Milestone 11 Optimise and broaden compatibility

Run the imported RNBO/Gen fixtures and representative playable patches. Profile generated hot loops on Xtensa, compare 256/128/64-frame exports, and change only routines with measured benefit and reference tests.

**Exit:** documented support inventory and performance envelope for each board/profile. Publish raw versus optimised evidence separately.

## 20 Detailed qualification matrix

| Area | Required checks |
| --- | --- |
| Basic audio | Distinct left/right tones; mono output; zero output; full-scale bounds; no channel swap |
| PCM | Gain 0/25/50/100%; ramp shape; finite protection; saturation; capture format and length |
| Vector | Exact 256-frame path; rejection of a 64/128/256 mismatch; capture ending mid-vector |
| Initialization | Cold boot, warm-up, first note, first clock, first list operation, parameter defaults |
| Allocation | Initialization peak; late allocations; repeated reconstruction; longest delay; largest declared list |
| Scheduler | Delayed events, line/ramp timing, nested clocks, long uptime, queue overflow, cancellation |
| MIDI | Overlap, repeated pitch, velocity-zero release, sustain, voice stealing, multiple channels |
| Parameters | Actual versus normalized values, exponents, steps, duplicate display names, boundaries, invalid NaN/Inf |
| Main and FX | Pass-through, stereo routing, wet tail, bypass/re-enable, Main stop, full Panic, independent globals |
| Loader | Constructor/finalizer order, imported symbols, relocation bounds, two copies, unload after detachment |
| Persistence | Readback, source attachment, changed generation, interrupted transfer, power interruption, known-good recovery |
| Physical inputs | BOOT bounce/release; optional ADC endpoints and smoothing; binding/manual edit ownership |
| Display | Empty/large layouts, long names, scroll ownership, icon spacing, no UI calls on the audio task |
| Network | Target ID, aliases, DHCP change, offline node, group fan-out, reconnect, stale revision, authentication |
| Capture | Recording ID replacement, bad offsets/counts, negotiated chunks, concurrent live controls |
| Stress | Main plus FX, frequent events, capture, UI updates and Wi-Fi active; heap and stack high-water marks |

For every physical test, record firmware/module hashes, board revision, rate/vector, Wi-Fi/UI state, initial/final settings, counters and whether external DAC/listening or only buffer capture was used.

A useful initial stress workload is five minutes at eight parameter or note events per second, with periodic captures. Follow with a longer soak and controlled module replacements. Keep expected negative-test rejections separate from unexpected audio faults.

Back up Main/FX packages and settings before destructive qualification. Restore exact graph-equivalent module bytes, source/metadata, selection, volume and running state afterward, and verify them. Instance phase, random evolution and effect tails cannot be restored from a package backup. Refuse to overwrite an unrelated package uploaded by another session while the test was running.

## 21 Optimisation priorities

Prioritise these after a conservative working port:

1. Remove accidental double arithmetic in sample loops while retaining precise clocks.
2. Bound delay/history storage from valid declared limits.
3. Prevent per-event and per-block allocation.
4. Share effects across polyphonic voices where the patch topology intends that.
5. Keep processing in planar float buffers until the final sink.
6. Hoist invariant parameter and coefficient work where a reference proves equivalence.
7. Measure code/state placement and instruction/data cache pressure.
8. Compare vector sizes using the same patch and active services.
9. Optimise measured hot routines with regression coverage.

Do not assume that FM1 CPU percentages predict ESP32 percentages, or that headless processing is twice as fast because it has two cores. The initial design uses one audio owner for deterministic Main-to-FX order. Splitting Main and FX across cores would introduce synchronization and buffer-transfer costs and should be a separate measured experiment.

## 22 Licensing and distribution

Preserve per-file licenses when importing source. The FM1 project's original integration work is MIT, while its included components have additional licenses. Much of the ESP32 SynthDef integration is GPL-3.0-or-later and the Waveshare-derived parts retain Apache-2.0 notices. Copying those files does not make them MIT merely because the new repository has an MIT root file.

The FM1 license inventory distinguishes RNBO runtime code, generated C++, original patch designs, platform sources, fonts and compiler dependencies. Cycling '74 states that the RNBO runtime is MIT while generated code has its stated export-license/GPLv3 alternatives. Keep generated notices intact and review the selected distribution path before publishing firmware/modules. [FM1 licensing inventory](https://github.com/little-scale/fm1-rnbo/blob/3b46afcd022f10a7f82be99a613bdc98b875c209/LICENSING.md), [Cycling '74 export licensing](https://support.cycling74.com/hc/en-us/articles/10730637742483-RNBO-Export-Licensing-FAQ).

The local converter requires an authorised Max/RNBO installation as described by the reviewed project. Do not bundle application licenses, credentials, private pairing files or proprietary installed-package contents as if they were original integration source. The RNBO runtime's MIT terms and notices should be assessed separately from generated C++ rather than treating both as one license category.

Use fonts whose redistribution terms fit the release. The FM1 local release switches to bundled OFL Barlow assets; its locally rasterized Arial path should not be copied into a public binary release without the corresponding rights assessment.

## 23 Decisions to record in the new project

The following defaults are recommended here; record changes as explicit architecture decisions:

| Decision | Starting position |
| --- | --- |
| Audio rate/vector | 44,100 Hz / 256 samples |
| Signal format | Float32 internally, int16 at the existing physical sinks |
| Execution model | Static bring-up, then qualified native ELF modules |
| Loader candidate | Reviewed Espressif ELF loader 2.0.0 source; pin after spike |
| Stored programs | One Main, one FX, direct bypass |
| Parameter limit | Proposed bounded 128; validate memory and protocol cost |
| Initial state budget | Proposed 1 MiB per stage, with measured whole-system admission |
| Code container budget | Proposed 512 KiB per stage, revised from real exports |
| Startup | Explicit policy; autonomous operation can start without touch or host |
| Input mapping | Logical normalized inputs bound to ordinary RNBO parameter IDs |
| Allocation | Detached preparation; no unqualified allocation in running audio |
| Randomness | Explicit reproducible or fresh-instance seed policy |
| Transport | Local service owns USB; authenticated Wi-Fi; separate bulk and event paths |
| Multi-node deployment | Compile once, verified bounded fan-out; synchronized activation later |
| Headed view | RNBO overview plus Controls, not generated C++ as the default display |
| Headless qualification | Post-volume PCM capture before external DAC testing |

## 24 First instructions for the next implementation session

1. Read this handover and the pinned source files. Confirm the new repository path and hardware currently available.
2. Import only the reusable hardware/runtime-shell pieces with their license and source provenance. Do not begin by copying both full firmware trees into one application.
3. Establish independent AMOLED and XIAO builds. Keep the existing working projects untouched as references and recovery sources.
4. Make 44.1 kHz/256 frames the explicit initial profile throughout the new audio shell and RNBO export.
5. Feed a small generated test signal through each available sink and verify PCM/capture before introducing RNBO.
6. Export and statically compile one RNBO oscillator, then add a MIDI/envelope case with allocation instrumentation.
7. Run the ELF-loader spike before promising uploadable patches. Preserve a static development route until that gate passes.
8. Add native packaging/persistence and a pass-through FX before a complex reverb or broad polyphony test.
9. Implement browser conversion and UI around the proven runtime rather than using them to obscure unresolved DSP/loading behaviour.
10. Record each result with its actual source and firmware identity. Keep host, loader, target DSP, electrical audio and listening results distinguishable.

The first concrete success should be small: a 256-frame RNBO oscillator rendered by a statically linked wrapper through the XIAO's existing stereo PCM/capture path, with parameter changes, clean Panic and no late allocations. The permanent-player module architecture follows once the independent loader tests pass.
