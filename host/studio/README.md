# RNBO ESP32 Studio

Select **XIAO ESP32-S3 · 16 kHz / 256** for native-16k XIAO patch builds.
The equivalent Max-helper message is `profile xiao-16000-256-v1`.
Both select XIAO explicitly and require a genuine 16000 Hz export and matching
player firmware; the choice also works outside dual boot.

For an existing 44.1k or native-16k XIAO SC/RNBO pair, choose **XIAO + SC dual boot** in
Audio profile and **SC / RNBO** in the Instrument column. That section inspects,
switches, updates the RNBO slot and loads a matching Main through the companion's
guarded pairing tools. See [XIAO dual boot](../../docs/xiao-dual-boot-studio.md).
Initial commissioning/rate migration stays in the companion tools; do not use
the factory installer on a pair.

Voice PE patch builds now select native **48 kHz / 256** or **16 kHz / 256**.
Use a genuine matching Max export and restart Studio after updating its source.
Voice PE firmware installation currently uses the separate protected CLI, not
the generic firmware dropdown/erase workflow. The [Voice PE guide](../../docs/voice-pe.md)
explains XMOS matching, muted startup and the hardware-test kits.

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

If the player commits the package and audio advances, render deadline misses
observed after loading are reported as a warning in Studio and Max. Player-side
admission and checks for other runtime faults still apply.

Existing `.rnbopkg` files can still be opened, downloaded and loaded without a
compiler. USB/Wi-Fi pairing, network scanning, parameters, Pause/Resume, output
volume and render-time/CPU readings remain available. See [Wi-Fi](../../docs/player-wifi.md),
[physical pins](../../docs/physical-inputs.md), and [MIDI](../../docs/midi-inputs.md).

The baseline wrapper uses Float32 audio and Float64 scheduler time. New builds
automatically use Float32 storage for reviewed internal ordinary `delay~` rings;
unsupported forms, comb/allpass, Gen and other buffers retain their native
storage. Results show memory saved; the manifest/provenance records each fallback.
See the [policy and pending hardware checks](../../docs/native-delay-storage.md).
Set voices,
Gen logic, delay sizes and parameter metadata in Max before export. The old
JSON editor, importer, automatic/trial rewriting and graph regeneration are
removed from Studio's supported workflow. Re-export after editing a patch.
A drawing attachment is not checked for semantic equality with generated code.

Exports are bounded to 1024 files / 32 MiB expanded, 16 MiB per file. ZIP paths,
links, duplicate names, external assets and multiple export roots reject.
Only trusted local native code should be compiled. Studio binds localhost and
retains session-token/origin checks. Saved pairing credentials remain private
under ignored `build/private/studio`; do not share that directory.

Voice PE `outport led_rgb` packages use envelope v5 and require
`led_output_version:1`. Studio rejects an older player before staging them.
The [LED example and guide](../../docs/voice-pe-leds.md) cover all three formats.

The updated player's `remote_control` capability exposes a separate lightweight
parameter page at its Wi-Fi IP (HTTP 80), plus Pi-style OSC input on UDP 1234.
Studio shows **Open board parameter page** and the OSC destination. This works
alongside Studio's existing authenticated TCP session; the page is not hosted by
the computer. Controls are trusted-LAN parameter access, not authenticated package
uploads. See [OSC/web controls and hardware follow-up](../../docs/osc-parameters.md).

For a single-runtime XIAO, install the matching player using **Update player → Current player firmware → XIAO ESP32-S3 · 16 kHz / 256**. The patch profile alone does not change firmware. See [firmware selection](../../docs/firmware-uploader.md). Existing SC/RNBO pairs must use the paired updater.
