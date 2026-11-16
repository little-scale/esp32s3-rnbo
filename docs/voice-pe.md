# RNBO on Home Assistant Voice Preview Edition

16 November 2026. **Native 16 kHz has passed its first playback checks on a
Voice PE.** The built-in speaker's 440 Hz sine was confirmed clean at 30% master
volume. Native 48 kHz and the remaining hardware gates are still unqualified.
See the [first-session record](../evidence/voice-pe-hardware-16000.json);
the [software readiness receipt](../evidence/voice-pe-readiness.json) remains the
historical computer-only checkpoint before that session.

## Profiles and what is ready

| Profile | Genuine Max export | Player / output | Block budget | XMOS requirement |
| --- | ---: | ---: | ---: | --- |
| `voice-pe-48000-256-v1` | 48,000 Hz / 256 | native 48,000 Hz | 5,333.33 µs | matching 48 kHz playback image |
| `voice-pe-16000-256-v1` | 16,000 Hz / 256 | native 16,000 Hz | 16,000 µs | separately installed native-16 image |

Both extend the permanent Main player. There is no new interpreter, resampler,
separate FX slot or requirement to reflash the player for ordinary patch changes.
The existing XIAO/AMOLED profile remains `esp32s3-44100-256-v1`.

The implementation includes the donor's codec sequence and routing, 0 dB DAC
gain, clock survey, I²S slave TX, stereo 32-bit slots, bounded S16 packing,
button/dial/mic-mute inputs, and a board-owned status/dial ring. Native RNBO DSP
and buffers remain separate from board drivers. The common output retains its
0.5 headroom factor. Signal processing uses Float32 and scheduler time Float64.
Known `line`/compound `curve~` limitations remain separately documented in the
[wrapper notes](native-wrapper.md).

The ESP32 never drives GPIO9/MCLK, resets XMOS opportunistically, or changes its
firmware. Missing/wrong WS/BCLK keeps output muted and leaves the USB player
console available with a startup-stage/clock diagnostic. The initial clock
survey is coarse, with a ±2% acceptance window; it is not a jitter measurement.
XMOS version interrogation is not implemented in this port yet.

Startup always pauses Voice PE playback, including saved Main restoration.
New Studio Voice PE builds default to **0% master volume**. Select Resume and a
small master setting explicitly for commissioning. Volume is not independently
persisted: the saved package's initial volume is restored at boot, then playback
stays paused. The microphone switch is an input, not a speaker-mute command.
The saved-Main startup guard is checked with two callbacks on the real audio
owner while PCM is forced silent. The patch remains paused and then freezes
again; this adds 512 frames to the existing detached preparation advancement.
Only a healthy, generation-matched check can release the guard for radio
startup. This corrects the first build's need for USB Resume before Wi-Fi could
start. Two consecutive native-16 restarts now pass silent PCM capture at a
packaged 30% volume, paused-state freezing and authenticated Wi-Fi access without
USB Resume. See the [follow-up receipt](../evidence/voice-pe-wifi-stress-16000.json).
Power interruption and native-48 wireless startup remain unqualified.
`player-info` exposes `paused_boot_check_version`, its generation and completion;
`boot_verified` also requires the control owner to commit the cleared guard.

Replacement renders a 5 ms outgoing fade, sends zeros past the six 128-frame
DMA buffers plus a FIFO margin, then parks the audio owner before destruction or
storage work. The incoming block fades up sample by sample. There is no overlap
crossfade or retained outgoing reverb tail. Fade endpoint tests pass on the
computer; audible replacement and physical DMA drain still need hardware checks.

`player-info` reports the explicit profile, native output rate, expected/measured
WS/BCLK, cached actual codec divider readbacks and startup stage, render/peak CPU percentage, conversion time, largest
free internal/PSRAM blocks, stack high-water marks and physical-control state.
The render figure excludes blocking I²S wait; wire-conversion time is reported
separately. No comparative CPU saving has been measured on Voice PE hardware.

## Physical controls as parameters

Write these **inside the RNBO parameter object** using inline `@meta`:

```text
param frequency 550 @min 100 @max 1000 @meta "{'esp32':{'type':'voice_pe','input':'dial'}}"
param gate 0 @min 0 @max 0.1 @meta "{'esp32':{'type':'voice_pe','input':'button'}}"
param microphone_mute 0 @min 0 @max 1 @meta "{'esp32':{'type':'voice_pe','input':'microphone_mute'}}"
```

Each source may bind one stable parameter ID. Values go through RNBO's normalized
parameter conversion, retaining authored min/max/exponent/steps. Button edges
use the generation-checked event queue. Presses occurring entirely while paused
are discarded; on resume the current held/released state is delivered, avoiding
a stale gate. A candidate starts from one coherent physical snapshot.

| Source / peripheral | Physical mapping | Behaviour |
| --- | --- | --- |
| `dial` | encoder A GPIO16, B GPIO18 | starts 0.5; 0.0125 per edge; clamped 0–1; PCNT overflow accumulation |
| `button` | GPIO0, active low | debounced press/release, normalized 0/1; ROM boot use retained |
| `microphone_mute` | GPIO3 | physical switch sense 0/1; does not automatically mute output |
| Codec / XMOS control | SDA GPIO5, SCL GPIO6; addresses 0x18 / 0x42 | reserved board ownership |
| Playback | WS GPIO7, BCLK GPIO8, data GPIO10 | ESP32 slave TX; GPIO9 is XMOS MCLK and is never driven |
| Speaker enable | GPIO47 | starts disabled; codec/output fault muting is also required |
| Ring | GPIO21 data, GPIO45 power | 12 LEDs, logical RGB → physical GRB, rotation +7, 20% cap |
| Capture / jack | GPIO13/14/15 and GPIO17 | reserved; microphones/jack routing are not qualified |

Voice PE bindings require package envelope **v4**, so old players reject them.
Audio-only packages retain envelope v1, with rate checks. GPIO/touchscreen plans
for other boards cannot be combined with Voice PE controls.

Ordinary patches retain the board status/dial ring. **`outport led_rgb` now
supports patch-authored colours**: 3 values set the ring, 4 values select an
index 0–11 plus RGB, and 36 values replace all twelve RGB triplets. This requires
the LED-capable player and envelope v5. See the [LED guide](voice-pe-leds.md).
Audio output 3 is not an LED channel. Grove sensors and microphone input are
outside this implementation. No raw XIAO pin mapping is accepted on Voice PE.

## Build and export

```sh
python3 tools/build_firmware.py voice-pe --player --profile voice-pe-48000-256-v1
python3 tools/build_firmware.py voice-pe --player --profile voice-pe-16000-256-v1
```

The isolated outputs are `build/firmware-voice-pe-player-48000` and
`build/firmware-voice-pe-player-16000`. The build requires the pinned ESP-IDF
5.5.0 and existing loader dependencies. Neither command accesses hardware.

In Studio choose the explicit audio profile before compiling the matching Max
Minimal Export. **Restart an already running Studio after updating its source.**
Changing a rate label does not convert exported DSP or switch XMOS clocks.
Wrong-rate exports reject during preparation; uploads check the player/profile
before staging and the device independently checks package and descriptor.
Opening a saved package or changing its startup volume preserves its rate.

For the Max helper, reopen the updated abstraction/scripts and send:

```text
profile voice-pe-16000-256-v1
build
```

Use `profile voice-pe-48000-256-v1` for 48 kHz. This configures Max's actual export
rate; it never rewrites a 44.1 kHz export. Choosing a Voice PE profile resets the
helper's startup volume to zero. After qualification, the usual explicit
`upload usb` / `upload wifi <board_id>` paths are retained. Loaded Wi-Fi on Voice
PE remains untested. The reviewed ordinary-delay storage converter matches the
new native control/delay fixture at both rates; six host comparisons are exact,
saving 16 KiB for its 4,096-frame ring. Unknown forms still retain native storage.

## Protected installation and recovery

**Do not use `idf.py flash`, generic erase/first-install, or the AMOLED bundle
for Voice PE.** The generic Studio firmware installer rejects this board. The
initial port uses the separate protected CLI below; browser firmware selection
for Voice PE is still pending. Normal package uploads do not use this installer.

An offline plan validates the exact build/profile, application identity, source
freshness, artifacts and reviewed partition table without opening any device:

```sh
python3 host/voice_pe_firmware.py \
  --build-dir build/firmware-voice-pe-player-16000 \
  --profile voice-pe-16000-256-v1
```

The corresponding explicit flash action additionally requires `--flash`, the
exact `--port`, the lower-case 12-digit `--mac`, and
`--confirm-xmos-profile voice-pe-16000-256-v1` (or the matched 48 kHz profile).
The confirmation acknowledges separately checked XMOS state; it is not an XMOS
rate-change command. Do not run it against a guessed USB path or rate pair.

The writer checks ESP32-S3 identity, security/encryption state and 16 MiB flash.
Stock migration first makes an independently verified full ESP flash backup,
checks every byte of the future filesystem is erased, and changes only table,
OTA selection and application. Existing recognized project layouts get an
app-only update, preserving the table/OTA selection and nonempty storage. NVS,
PHY, bootloader and XMOS are protected. It never invokes chip erase. Recognized
6d000/70000 NVS extents remain intact. Failed backups or unknown layouts stop
before writing. These behaviours are tested with simulated flash only.

Private backups go to ignored `build/private/voice-pe-recovery`. The RNBO store
uses separate NVS names and `rnbo-main*.pkg` filenames. It does not erase an
unknown nonempty filesystem after a failed mount. A successful mount is reused
without deleting unrelated files. Keep the original Voice PE recovery records;
an ESP backup cannot restore XMOS or eFuses.

XMOS maintenance remains deliberately separate. `host/voice_pe_xmos_dfu.py`
provides read-only inventory and repeat-verified private backups; select the
exact physical USB path, since its serial string is not unique.
`host/build_voice_pe_xmos.py` and the pinned patches under
`ports/voice_pe/xmos/native16` reproduce the donor's native-16 build. Do not
automatically restore stock XMOS when encountering a custom version.
The [handover](../RNBO_VOICE_PE_TECHNICAL_HANDOVER.md) records the selector
procedure, image identities and matched-pair recovery requirements.
The two checksum-matched donor XMOS upgrade images are staged separately under
`build/dist/voice-pe-xmos-reference`; they are not ESP firmware and are not
automatically flashed by either test kit.

## First hardware session

Use the kits under `build/dist/voice-pe-*` and the
[computer-side receipt](../evidence/voice-pe-readiness.json).

1. Identify the exact board, existing ESP layout/recovery backup and current
   XMOS pair. Inspect first; do not assume the last SynthDef native-16 state is
   still installed. Choose one rate and finish its checks before changing XMOS.
2. Validate/install the matching player through the protected path. Boot muted.
   Read `player-info`: profile, external clocks, codec/startup stage, storage,
   physical controls and DMA/audio progress must be sensible. A wrong clock
   must remain muted and USB-recoverable.
3. Load the matching `sine-<rate>.rnbopkg`, initially at 0%. Resume and set a
   small master level (start at 5%) for a brief clean 440 Hz listening/capture
   check (Resume only if paused). Check Pause/Resume and speaker output before increasing volume.
4. Load `controls-<rate>.rnbopkg`, ensure playback is resumed at a small master level, press/release
   the centre button and turn the dial through both ends and back. Check the
   ring and readback. The microphone switch should update its own parameter
   without muting the authored speaker patch.
5. Replace sine ↔ controls/delay ↔ sine. Listen for transition clicks, verify
   counters and saved identities, and deliberately try the other rate package:
   it must reject without altering the active/saved Main.
6. Run a silent soak with parameter sweeps and USB polling. Record render/peak
   load, overruns, allocation/queue/DMA errors, largest free blocks and stack
   margins. Capture post-volume PCM using `player-capture-begin N`,
   `player-capture-info`, then bounded
   `player-capture-read <capture_id> <byte_offset> <byte_count>` (≤1024 bytes).
   Capture proves the digital buffer, not the analog output or listening result.
7. Reboot normally: saved Main returns **paused**. Confirm deliberate Resume,
   volume and control-state recovery. Check foreign files and NVS remained intact.
8. Qualify Wi-Fi pairing/uploads under DSP/control/ring load when a network is
   available. Then deliberately commission the other matched XMOS/player rate
   and repeat. Jack channel separation and microphone capture require separate
   work; do not infer them from the speaker. For patch-authored lighting, follow
   the separate [LED ring checks](voice-pe-leds.md).

Record device/firmware/module/package/export/XMOS identities, measured clocks,
codec readbacks, observation duration and user listening result separately.
The two-rate software build is ready for these checks. The first-session record
identifies the individual native-16 checks completed so far; it is not a blanket
pass for this checklist or for native 48 kHz.

## Dual-app update protection

A deliberately paired Voice PE can keep SynthDef in app0 and RNBO in app1.
The legacy RNBO app0 updater refuses that arrangement before any backup/write,
so it cannot replace the SynthDef companion application. Use the dual-app
installer (`host/voice_pe_apps.py` in the SynthDef companion project) for RNBO
app1 installation/updates and application selection. Both images must match the
installed XMOS clock rate. USB boot selection and automatic payload routing
are separate features; this guard alone does not enable either.

The companion project now also supplies an experimental `host/dual_upload.sh`
USB entrypoint for validated SynthDef source/SCgf or RNBO packages. Both installed
apps must use its read-only `@RT1 HELLO` identification protocol. The player now
reports engine/model/native rate/busy without changing playback. Muted automatic
Main uploads now pass in both directions on native-16k
VoicePE-0697d4, with same-engine uptime preservation and busy/exclusive-USB
refusal. The original programs, paused RNBO state, FX bypass/settings and 36%
SynthDef volume were restored, followed by a verified software restart. XMOS
was not changed. Existing RNBO Studio/Max entrypoints do not automatically
switch to the SynthDef app; native-48k and XIAO/AMOLED hardware remain pending.

XIAO and AMOLED V2 pairing/migration/update tools are also prepared in the
SynthDef companion (`host/dual_apps.sh`). Their simulated flash tests and both
board builds pass; physical partition migration is pending. The split preserves
the existing filesystem/settings geometry and checks compatible SPIFFS formats.
Use paired update tools after commissioning: a first-install/erase operation
would destroy the pair. Voice PE still uses its existing app0/app1 layout and
requires matching XMOS/native-rate images. See the companion's
[dual-runtime guide](https://github.com/little-scale/esp32s3-synthdef/blob/main/docs/DUAL_RUNTIME.md)
for commands and qualification boundaries.

The companion SynthDef Studio now has a **Runtimes** tab for identity-bound,
single-use reviewed Main uploads, with progress recoverable after browser reload.
Its existing SC `.sendESP32` / `.playESP32` Main path can also select SynthDef for
the explicitly inspected paired USB node while RNBO is running. A native-16k
hardware check discovered RNBO, refused control-only switching, then completed a
quiet SC definition deployment in 65.9 seconds; autonomous Function playback and
parameter readback passed afterward. The user's original setup and 36% SynthDef
volume were restored. This is a host-side integration, not a new XMOS/player
image, and does not add automatic routing to this project's Max/RNBO frontend.
Wi-Fi handoff, other-board hardware checks and quiet boot before the incoming
Main is installed remain pending. The target app follows its normal startup
behavior; no seamless or audible cross-engine transition qualification is made.
