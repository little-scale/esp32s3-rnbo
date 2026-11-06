# Implementation status — native export migration

**6 November 2026:** Cycling ’74’s C++ Minimal Export from Max is now the only
supported patch frontend. Studio accepts complete export folders/ZIPs, validates
and compiles C++, runs a native startup screen and creates `.rnbopkg` for the
existing player. `.rnbopat` is optional drawing data only. See
[export instructions](native-export.md) and the [wrapper review](native-wrapper.md).

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
cannot install firmware. Lifecycle/failure tests and real Studio HTTP checks with
simulated USB/Wi-Fi transports pass; physical uploads from Max remain unqualified.

Remaining wrapper work includes dynamic list allocation and scheduler/ramp
semantics. Native export reproduces the compound curve late allocation and line
ramp platform error; it does not resolve those faults by itself. Runtime version
qualification is still pinned to RNBO 1.4.4.

The previous 1,072/1,455 scoped inventory outcomes and optimisation gains remain
historical importer-route evidence. The [public dashboard](https://little-scale.github.io/esp32s3-rnbo/)
links them separately. Previous [status prose](../archive/docs/docs/STATUS.md)
and the complete [`fcef6af` checkpoint](https://github.com/little-scale/esp32s3-rnbo/tree/fcef6af) preserve their context.
The broad testing goal is **paused**, and is not restarted by this migration.
