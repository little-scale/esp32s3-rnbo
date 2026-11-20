# XIAO SC/RNBO dual boot in Studio

17 November 2026. Studio now supports an **already commissioned** XIAO ESP32-S3
pair with both SynthDef and RNBO installed at **44,100 Hz** or native
**16,000 Hz**. Both installed apps must agree. Its new host
workflow is computer-tested; physical Studio switching/updating/loading still
needs a hardware session. The earlier XIAO listening/paired-rate checks are in
[XIAO qualification](xiao-qualification.md#native-16-khz-pcm5102a--dual-runtime-experiment--17-november-2026).
The [Studio readiness record](../evidence/xiao-dual-boot-studio.json) records
computer checks, the genuine 16 kHz Max-export build and the connected device's
refusal for lack of a verified pair inventory. No firmware or boot selection was
changed in this session.

## Build a patch

In Max, export genuine C++ Minimal Export with **256 frames**, Copy Library and
the usual Float32 settings. Match Fixed Sample Rate and Studio Audio profile:

| Installed pair | Max fixed sample rate | Studio Audio profile | RNBO block budget |
| --- | --- | --- | --- |
| 44.1 kHz | `44100` | XIAO + SC dual boot · 44.1 kHz / 256 | 5.805 ms |
| Native 16 kHz | `16000` | XIAO ESP32-S3 · 16 kHz / 256 | 16 ms |

Then compile. This explicitly selects the XIAO backend and retains its normal headless startup
volume, initially 50%. Set Startup volume before compiling as usual.

For 16 kHz, the internal package ABI is still named `voice-pe-16000-256-v1` for historical
compatibility. This does not select Voice PE hardware, its controls or XMOS.
The Max-helper message is `profile xiao-16000-256-v1`; Studio accepts that
selection name too and resolves it to XIAO plus the existing shared package ABI.
XIAO uses the existing I²S DAC pins and native 16 kHz PCM5102A configuration.
RNBO always uses 256-frame callbacks; SynthDef's blocks remain 64 frames
(4 ms at 16 kHz, about 1.45 ms at 44.1 kHz). The 44.1 kHz package ABI remains
`esp32s3-44100-256-v1`.
Selecting a profile never resamples a mismatched export or changes firmware rate.

## Use the paired board

1. Start `./host/studio.sh`, select the XIAO's USB device, then choose **SC / RNBO**
   in the Instrument column. Release the SynthDef Studio USB connection first.
2. Click **Inspect selected XIAO**. The harmless common `@RT1 HELLO` query shows
   the running engine, native rate and copyable board ID. It also requires the
   companion checkout's verified pairing inventory. Inspection selects the
   installed rate in **Paired firmware / package rate**; reviewing a different
   rate does not reflash or retune the pair. Inspection does not reboot
   or send any parameter/note data. It releases an RNBO USB session owned by this
   Studio so the pairing tools can obtain exclusive USB access.
3. Use **Start RNBO** / **Start SuperCollider** to select an installed runtime.
   Changing engines acknowledges a RAM-only fade, changes the guarded boot
   selection, restarts and checks the returning runtime. Selecting the already
   running engine does not reboot. Each engine keeps its own saved program and
   output setting. A previous saved sound can resume in the incoming engine.
4. **Start RNBO & load package** validates this exact Main package before any
   USB switch, selects RNBO if needed and uses its existing verified uploader
   once. Wrong-rate and wrong-board physical metadata reject before switching.
   A same-engine package load does not reboot. USB re-enumeration is resolved by
   the permanent MAC rather than assuming the port name stays the same.
5. After any paired action, inspect again before another. For RNBO live sliders,
   output volume or Wi-Fi setup, choose **Load & play** and **Connect USB**.
   Wi-Fi package loading works while RNBO is running; Wi-Fi does not switch engines.

Inspecting and loading are explicit actions, not background discovery triggers.
Notes, OSC, parameter changes and status polling never select another runtime.
Inspections expire after ten minutes, are bound to the exact USB identity and
port, and are consumed once by an action. A changed engine, busy device, missing
pair inventory, changed build/package or failed verification stops the action.
Mutations are not automatically retried. Retain the private recovery receipts
and inspect the device before retrying a failed firmware operation.

## Update RNBO within the pair

The **RNBO player update** review shows the current same-rate image size and
SHA256. **Refresh build review** only checks local files. After inspecting the
board, **Update RNBO slot** invokes the companion's existing guarded updater for
RNBO only. It backs up the old application and boot records, verifies readback
and protected regions, preserves SynthDef/storage/settings and restores the
previously selected engine. It does not install a bootloader, replace the table,
erase flash or update SynthDef. A stale review or oversized image rejects.

Both matching complete local build folders are required:

```sh
# Native 16 kHz, in this RNBO checkout:
python3 tools/build_firmware.py xiao --player --variant dual-native16 \
  --profile voice-pe-16000-256-v1

# Native 16 kHz, in the companion SynthDef checkout:
bash host/xiao_native16.sh build

# For a 44.1 kHz pair instead:
# RNBO checkout:
python3 tools/build_firmware.py xiao --player
# SynthDef checkout:
bash host/xiao.sh build
```

Studio looks beside this checkout for `WaveShareAmoled18-synthdef` or
`esp32s3-synthdef`. Set `SYNTHDEF_PROJECT_ROOT` before starting Studio if it lives
elsewhere. Its original `build/host/private/dual-apps/<MAC>/installed-apps.json`
and backups stay in that checkout. Do not invent or copy an inventory for an
unknown board. No private inventory or credential data is served by Studio.

**Initial pairing and changing the pair between 44.1 and 16 kHz remain in the
companion commissioning tools.** See its
[dual-runtime guide](https://github.com/little-scale/esp32s3-synthdef/blob/main/docs/DUAL_RUNTIME.md#xiao-native-16-khz-pair).
Studio's new section requires both installed apps to already match the selected
16 or 44.1 kHz rate and never performs a table migration. Do not use the generic **First install** or
factory-layout **Update player** paths on a commissioned pair. The regular firmware menu also offers a native-16k XIAO player for ordinary
single-runtime factory layouts. That choice does not commission or update a
pair. Use the paired section for an existing SC/RNBO installation.
