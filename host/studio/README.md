# RNBO ESP32 Studio

Start `./host/studio.sh` from the repository and open
[localhost:8788](http://127.0.0.1:8788). The launcher uses the installed ESP-IDF
Python environment when available. Install ESP-IDF 5.5, CMake, a C++17 compiler
and the pinned Xtensa module dependencies. Serial uploads also need pyserial.
Max/RNBO and Node are not needed on the receiving computer when the export is complete.

The **Player firmware** section lists current local XIAO and AMOLED USB/Wi-Fi
builds in a dropdown, and also supports supplied ZIPs and local source builds.
Selection prepares the checked firmware; the separate Update/Install button
flashes it. Refresh rechecks source freshness and marks stale builds unavailable.
Select **First install / replace other firmware** for a blank unit or one
running another project, then explicitly acknowledge the erase. A ROM-level
full-flash backup precedes the erase; no RNBO connection is needed. **Update RNBO
player** keeps the existing RNBO layout, saved packages and Wi-Fi settings.
See the [firmware guide](../../docs/firmware-uploader.md) for boot mode, full ZIPs,
backup locations and the first-install steps.

1. Export in Max using [these settings](../../docs/native-export.md).
2. Choose **Open export folder** or **Open export ZIP**. Optionally add the
   matching `.rnbopat` using **Add patch drawing**; it affects the drawing only.
3. Choose arena reserve and startup volume, then **Compile export**. Studio
   prepares the C++, runs the native startup screen, builds a module and packages it.
4. Connect the board and load the package. Install the stable player separately
   if needed; ordinary package loads do not replace firmware.

You can also [build directly from an embedded RNBO patch in Max](../max/README.md).
The helper submits its live drawing and native C++ export together, then supplies
a Studio link for that exact job. Opening the link does not rebuild or upload.
Send `upload usb` or `upload wifi` to the Max helper to load its completed package,
or `build_upload usb` / `build_upload wifi` to build and then load on success.
Both accept an optional USB port or paired Wi-Fi board ID. Studio must remain
running; Wi-Fi setup/pairing and player installation stay in Studio.

Existing `.rnbopkg` files can still be opened, downloaded and loaded without a
compiler. USB/Wi-Fi pairing, network scanning, parameters, Pause/Resume, output
volume and render-time/CPU readings remain available. See [Wi-Fi](../../docs/player-wifi.md),
[physical pins](../../docs/physical-inputs.md), and [MIDI](../../docs/midi-inputs.md).

The baseline wrapper uses Float32 audio and Float64 scheduler time. Set voices,
Gen logic, delay sizes and parameter metadata in Max before export. The old
JSON editor, importer, automatic/trial rewriting and graph regeneration are
removed from Studio's supported workflow. Re-export after editing a patch.
A drawing attachment is not checked for semantic equality with generated code.

Exports are bounded to 1024 files / 32 MiB expanded, 16 MiB per file. ZIP paths,
links, duplicate names, external assets and multiple export roots reject.
Only trusted local native code should be compiled. Studio binds localhost and
retains session-token/origin checks. Saved pairing credentials remain private
under ignored `build/private/studio`; do not share that directory.
