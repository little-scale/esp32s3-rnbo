# Implementation status — native export migration

**16 November 2026 — Voice PE USB stress and Wi-Fi:** Twelve alternating
replacements, 288 synthetic parameter updates and twelve Pause/Resume pairs
pass without reported runtime faults. Saved paused startup now verifies two
audio-owner callbacks with PCM forced silent, freezes again, then permits radio
startup. This removes the first build's USB-Resume dependency. An early explicit
Resume consumes the same bounded verification count. Native-16 restart checks,
authenticated wireless uploads/controls and a 44.95-second wireless soak pass;
the soak measured 6.55% mean / 11.69% peak render load. Invalid pairing keys
reject. Binary identities and measurement scopes are kept separate in the
[follow-up receipt](../evidence/voice-pe-wifi-stress-16000.json). No native-48,
physical power-cycle, rapid physical-edge or analog click qualification is
implied. Small internal-RAM variation during repeated loads remains flagged
for a longer soak; PSRAM use stayed stable.

**16 November 2026 — first Voice PE native-16 hardware session:** Protected
application installation and backup/readback passed without changing XMOS,
bootloader, partition table, storage or NVS. The built-in speaker's 440 Hz sine
is user-confirmed clean at 30%; post-volume capture verifies silence at 0% and
Pause, and approximately 440 Hz at 30%. Button/dial/ring and microphone-switch
behaviour are user-confirmed. A 119.94-second idle controls/delay run with USB
polling measured 5.99% mean / 8.26% peak render load, no reported fault counters
and no observed heap loss. Host and device reject a 48 kHz package without
replacing the active/saved native-16 patch. Normal reset restores that patch
paused at 0%; deliberate Resume succeeds. This is initial native-16 evidence,
not full qualification or a native-48 pass. See the
[hardware receipt](../evidence/voice-pe-hardware-16000.json).

**16 November 2026 — Voice PE hardware-test preparation:** Two explicit native
profiles now propagate through Max export settings, host preparation/rendering,
Xtensa modules, package headers, player admission and rate-correct telemetry.
The port reuses the donor's safe GPIO/clock/codec/I²S backend, adds semantic
dial/button/microphone-mute bindings (envelope v4), board status ring, muted
startup, replacement fades/drain, protected ESP-only installation and bounded
digital capture. Genuine Max exports are built at both rates. Hardware audio,
clocks, controls, persistence, loaded Wi-Fi and CPU qualification are pending;
programmable LED output remains unavailable. See the [guide](voice-pe.md) and
[readiness receipt](../evidence/voice-pe-readiness.json).

**13 November 2026 — automatic native delay storage:** Future Studio/Max builds
and default CLI preparation now use Float32 storage for reviewed internal
ordinary `delay~` rings. Unsupported forms and other buffer families retain
native storage, with conversions, fallback reasons and memory savings recorded
in build provenance. Delay sizes, algorithms and scheduler precision are
unchanged. Existing packages/firmware are unchanged; hardware timing and audio
checks remain pending. See the [policy](native-delay-storage.md).

**13 November 2026 — native delay storage research:** A separate computer-only
SawSAHArpy trial changes its reviewed internal delay ring from Double to Float32
storage, saving 128 KiB while preserving its capacity and generated algorithms.
Host numerical comparisons and ESP32-S3 cross-builds are recorded separately
from pending hardware timing/listening checks. Studio defaults and installed
firmware were unchanged during that trial; the later default change is recorded
above. See the [investigation and hardware follow-up](native-delay-storage.md).

**7 November 2026 — AMOLED patch-area parameters:** Inline
`@meta "{'esp32':{'type':'touchscreen','axis':'x'}}"` (also `y` and `pressed`)
now binds parameters to the patch drawing rectangle only. Buttons, output volume
and the Params multisliders retain their own controls. Leaving the rectangle,
changing pages, pause and maintenance cancel held gestures; coordinates hold on
release. Packages require envelope v3 and updated AMOLED capability admission.
Both firmware profiles compile; real Max export/build preserved all three
example bindings. Native gesture/parser, package, upload and regression checks
pass. Physical finger interaction and listening remain pending; no board was
flashed for this change. The example is installed in the Max Library helper
folder and the current firmware ZIPs have been rebuilt. See the
[touchscreen guide](touchscreen-inputs.md) and
[receipt](../evidence/amoled-touchscreen-inputs.json).

**7 November 2026 — current firmware selector:** Studio's **Player firmware**
section now lists current local XIAO and AMOLED USB/Wi-Fi builds. The list checks
source freshness and image integrity; choosing an option stages the exact checked
bundle without building or flashing. Missing/stale builds are marked unavailable,
and the file picker remains available. A real browser selection prepared the
current AMOLED image successfully; no new board write was performed. Server
checks (127) and browser checks (34) pass. See the
[firmware guide](firmware-uploader.md#choose-the-current-player).

**7 November 2026 — firmware ZIP correction:** The initially supplied AMOLED ZIP
was a valid older player build without Wi-Fi. It has been replaced locally with
a current-source build including `player_network` and `esp_wifi`; the XIAO ZIP
already matched current sources. The ZIP builder now refuses stale builds and
requires the network component. Both current bundles pass image validation;
the replacement AMOLED image has not been flashed or functionally checked on
hardware in this correction. See the
[build receipt](../evidence/current-player-firmware-bundles.json).

**7 November 2026:** A Max 9.1.4 session returned no native patcher object to
V8, including in an independent minimal probe (`JS peer class of jspatcher not
found`). The Max helper now stops with an actionable message before export and
drives its panel status without that API. Its 15 helper tests and two package
tests pass. A full Max restart restored the API, and a fresh embedded-sine export
and Studio build completed with its six-node drawing and a verified 48,855-byte
package. No board was touched. This records recovery of that session, not a fix
inside Max. See the [receipt](../evidence/max-patcher-startup.json) and
[troubleshooting](../host/max/README.md#max-patcher-scripting-unavailable).

**6 November 2026:** Cycling ’74’s C++ Minimal Export from Max is now the only
supported patch frontend. Studio accepts complete export folders/ZIPs, validates
and compiles C++, runs a native startup screen and creates `.rnbopkg` for the
existing player. `.rnbopat` is optional drawing data only. See
[export instructions](native-export.md) and the [wrapper review](native-wrapper.md).

The page is now **RNBO ESP32 Studio**. Its visible **Player firmware** section
accepts checked prebuilt player ZIPs without compilation, alongside local builds.
**Update** preserves the existing RNBO layout and saved data; **First install /
replace other firmware** requires an explicit erase acknowledgement, backs up
the complete flash, then installs bootloader/table/player and verifies readback
and startup. It uses the ROM bootloader without requiring old RNBO firmware.
Both paths have simulated-device coverage. A user-initiated physical AMOLED first
install passed full backup, all image readbacks and player startup checks; physical
XIAO first install and listening remain pending. See the
[receipt](../evidence/studio-firmware-uploader.json) and
[firmware guide](firmware-uploader.md).

Retained: the shared module ABI, player, saved Main, package loader, audio drivers,
USB/Wi-Fi, live parameters, physical-input metadata, MIDI infrastructure and
AMOLED drawing/multisliders/meter. The wrapper itself is unchanged. The old
importer/custom visual Gen lowerer is in `archive/importer`; Auto/Trial and
importer-specific rewrites are no longer supported Studio profiles.

The [real Max comparison](native-export-comparison.md) covers eight programs.
Five complete output pairs agree exactly; two share runtime faults. Native Gen
modulo now compiles, with tiny recorded rounding differences against its original
zero-tolerance oracle. Three matched XIAO contexts pass all 12 A–B–B–A runs;
medians are unchanged at 318, 141 and 42 µs. No general performance gain or
complete-object qualification is claimed.

A fresh native Max sine Main also passes the migrated Studio HTTP build and
XIAO load/control/Pause-Resume checks: 31.41 seconds observed without runtime
or deadline faults, 737.5 µs polled median player render (12.70%). Listening
confirmation remains pending; the previous package and controls are restored.
See the [player receipt](../evidence/xiao-native-export-player.json).

The [Max build helper](../host/max/README.md) now exports live embedded RNBO
patches, captures their drawing and submits a Studio build without a separate
`.rnbopat`. An actual unsaved `*~ 0.5` edit produced a checked package and seven-node
drawing while the saved source retained six nodes. All 8,192 captured Float32
words match the original native sine scaled by exact 0.5. This is host integration
evidence; no new hardware upload or listening claim is made. See the
[integration receipt](../evidence/max-embedded-build.json).

The helper also accepts explicit `upload usb` / `upload wifi` messages and
`build_upload usb` / `build_upload wifi` for compile-then-load. Optional USB ports
or paired Wi-Fi IDs select the target; ambiguous boards reject. The extension
uses the existing package upload paths, preserves plain build-only behaviour and
cannot install firmware. An actual Max-triggered USB upload now passes on XIAO,
including parameter readback, Pause/Resume and saved-package persistence across
an actual reboot. A 12.32-second, 24-poll observation records zero faults at zero
output volume; the polled render median is 647.5 µs (11.15%). This is a separate
workflow check, with no listening or captured-output claim. The previous package,
firmware and controls are restored. Wi-Fi upload from Max remains pending because
the saved network is unavailable. See the
[USB receipt](../evidence/max-usb-upload-player.json).

The helper also has a reproducible [Max package ZIP](https://little-scale.github.io/esp32s3-rnbo/downloads/esp32s3-rnbo-max.zip)
with the abstraction, scripts, example and help patch; Studio remains separate.

Actual Max exports also preserve all three inline physical-input bindings in
the example through native package preparation. The native silent MIDI monitor
passes software delivery and UART1 internal loopback on XIAO: 206 delivered
messages, zero drops/overflows/errors, running status, 96 software plus 96 UART
clocks, system messages and note recovery. The original Main, volume, parameters
and UART setting are restored. External MIDI, USB-host and physical input-response
checks remain pending. See the [retained-feature receipt](../evidence/native-retained-features.json).

Remaining wrapper work includes dynamic list allocation and scheduler/ramp
semantics. Native export reproduces the compound curve late allocation and line
ramp platform error; it does not resolve those faults by itself. Runtime version
qualification is still pinned to RNBO 1.4.4.

The [ramp diagnosis](native-ramp-diagnosis.md) now identifies the event-rate `line`
fault as a Float32 clock-endpoint loop exhausting the queue, and compound `curve~`
as active-ramp list growth beyond 16 inline elements. Private candidates complete
both runs; timeline disagreement and reservation bounds remain separate work.
Neither production wrapper nor Studio's arithmetic baseline is changed.

The previous 1,072/1,455 scoped inventory outcomes and optimisation gains remain
historical importer-route evidence. The [public dashboard](https://little-scale.github.io/esp32s3-rnbo/)
links them separately. Previous [status prose](../archive/docs/docs/STATUS.md)
and the complete [`fcef6af` checkpoint](https://github.com/little-scale/esp32s3-rnbo/tree/fcef6af) preserve their context.
The broad testing goal is **paused**, and is not restarted by this migration.
