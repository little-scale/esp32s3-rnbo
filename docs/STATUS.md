# Implementation status — native export migration

**7 November 2026:** A Max 9.1.4 session returned no native patcher object to
V8, including in an independent minimal probe (`JS peer class of jspatcher not
found`). The Max helper now stops with an actionable message before export and
drives its panel status without that API. Its 15 helper tests and two package
tests pass. Restart recovery is awaiting the user's saved/restarted Max session;
this is not yet a verified repair of Max's native bridge. See
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
