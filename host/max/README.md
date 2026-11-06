# Build an embedded RNBO patch from Max

The helper builds the **live `rnbo~` object**, including edits that have not been
saved. The RNBO patch stays embedded in its parent `.maxpat`. A separate
`.rnbopat` file is not required.

Open [embedded-sine.maxpat](embedded-sine.maxpat) for a working example. Start
`./host/studio.sh`, then click **build** in the helper panel. Click **open** to
view that build in Studio and inspect its drawing. Send `upload usb` or
`upload wifi` to load the completed package directly from Max. Plain `build`
compiles only; the helper never installs player firmware.

## Install as a Max package

[Download the Max helper ZIP](https://little-scale.github.io/esp32s3-rnbo/downloads/esp32s3-rnbo-max.zip).
Unzip it and put its `esp32s3-rnbo` folder in `~/Documents/Max 9/Packages` on macOS,
then restart Max. The package includes the abstraction, scripts, an embedded
sine example and an Alt/Option-click help patch. Studio and its compiler
dependencies remain a separate installation; start `./host/studio.sh` as usual.
This follows the [Max package layout](https://docs.cycling74.com/userguide/packages/).

To build the ZIP from this checkout, run `python3 host/max/build_package.py`.
The result is `build/dist/esp32s3-rnbo-max.zip`; its manifest records each bundled
file's hash. The bundle contains only the listed helper/example/license files.
You can instead use the manual file-copy setup below.

`rnbo.instrument` is an equivalent alias for `rnbo.studio`; both have matching
help patches. The package builder derives them from the same implementation.
For a manual Library installation, keep both abstractions, both scripts and
their help files together in a subfolder of `~/Documents/Max 9/Library`.

## Add it to an existing Max patch

Copy these three files beside your `.maxpat` (or put this folder on Max's search path):

- `rnbo.studio.maxpat`
- `rnbo-studio.js`
- `rnbo-studio-client.js`

Give the intended `rnbo~` object the **scripting name** `instrument` in its
Inspector, and enable `@dumpoutlet 1`. Add `rnbo.studio instrument` as an
abstraction, or use a `bpatcher` named `rnbo.studio.maxpat` with `instrument` as
its argument, as in the example. Open the abstraction's window to see its
presentation controls, or display it in a bpatcher.

A `bang` or `build` message to the helper starts the build. You can also connect
RNBO's dump outlet to the helper inlet for export-status messages. The helper
additionally queries RNBO's read-only export status while waiting. With no
argument, it uses the single `rnbo~` in a containing Max patch; multiple RNBO
objects require an explicit scripting name so the intended instrument is selected.

## Build and upload messages

Send these messages to the helper's inlet:

| Message | Action |
| --- | --- |
| `build` or `bang` | Export and compile the live patch; leave the board alone. |
| `upload usb` | Load the last successful build through the single listed USB board. |
| `upload usb /dev/cu.usbmodem101` | Load through that specific USB port (use your current port). |
| `upload wifi` | Load through the single board already paired with Studio. |
| `upload wifi 001122aabbcc` | Load through that specific paired board ID. |
| `build_upload usb` | Export and compile, then load by USB if the build succeeds. |
| `build_upload wifi` | Export and compile, then load by paired Wi-Fi if the build succeeds. |

`build_upload` also accepts the same optional port/device-ID argument. The
example includes clickable message boxes, and the helper panel has USB/Wi-Fi
upload buttons. The messages belong in the surrounding Max patch.

With multiple USB boards or saved Wi-Fi pairings, supply the explicit target;
the helper will not guess. Find USB ports and paired Wi-Fi IDs in Studio's
connection selectors. Quote a numeric-only Wi-Fi ID in a Max message to preserve
any leading zeros. Wi-Fi setup/pairing is done in Studio first; passwords and
pairing keys never pass through the Max patch. There is no USB fallback after
a Wi-Fi failure.

Upload means loading/saving the **Main package** into an already installed RNBO
player. It briefly pauses audio and replaces the saved patch. It does not flash
the player firmware. A completion message is emitted only after Studio reports
the package active; CPU/admission failures report `upload_failed` instead.
The status outlet emits `upload_target`, `uploading`, then `uploaded` or
`upload_failed`. A missing board or failed transfer is not automatically retried.

Only this helper's last successfully compiled and hash-checked package is eligible.
Starting a new build invalidates the previous one for Max uploads, so a failed
new build cannot silently upload an older patch. Editing after a completed build
does not update that package: use `build_upload` to include the current edits.
After a Studio/helper restart or a Studio port change, build again first.

The helper belongs in the surrounding **Max patch**, alongside `rnbo~`.
`v8` and `node.script` are Max objects and do not belong inside the RNBO DSP graph.
For an RNBO patch embedded in a nested Max subpatcher, place the helper alongside
its `rnbo~`, or supply a name found in a containing parent patch.

## What happens

1. Max scripting reads live object labels, positions and connection endpoints
   for the drawing. This is display data, not a replacement patch compiler.
2. A fresh temporary directory and Minimal Export configuration are created.
   RNBO itself generates C++ directly from its live embedded patch.
3. The helper waits for RNBO export completion, then sends the generated files
   and drawing together to Studio's existing build API.
4. Studio runs its normal checks and compilation. The helper reports progress,
   saves the checked `.rnbopkg` in its temporary build directory and provides
   a link to that exact job in Studio.

The original Max/RNBO source files are not saved, renamed or externalised by the
helper. Do not edit while export is underway: a detected top-level drawing change
requires a fresh build. This check is not a full semantic lock on nested code or
external dependencies. Make another build after making further edits.

Live capture preserves box positions and cord endpoints; manually routed cord
bend points are not exposed by the API used here. If a drawing cannot be captured
or exceeds the display limits, compilation can still proceed with parameter
controls. Current display limits remain 96 objects / 384 segments; the DSP export
is subject to the separate player limits.

## Defaults and scope

Tested with **Max 9.1.4 / RNBO 1.4.4**, using `v8` and the bundled Node for Max.
The helper needs no npm installation and uses no RNBO internal generator APIs.
It targets Minimal C++, Copy Library, fixed 44100 Hz / 256 frames and the existing
Float32 wrapper. Polyphony is **linked to the `rnbo~` object's `@polyphony`**;
per-voice parameter exposure follows its corresponding attribute. Existing
player restrictions, including MIDI output and external resources, still apply.

Optional messages to the helper: `startup_volume 50`, `arena 1` (1/2/4 MiB),
and `studio_port 8788` for another localhost port. The default startup volume is
50%; these settings affect the new package, not the currently running board.

Studio remains a separate local process. If it is unavailable or busy, the helper
reports the error; it does not reuse an older export or automatically retry an
upload. Temporary export/package files may be removed by the OS;
use Studio's download button to keep a package permanently. Build links refer to
jobs in the running Studio session and expire when that server restarts.

The [integration receipt](../../evidence/max-embedded-build.json) records a real
Max build with a gain object added only in memory, the resulting drawing and
native-output comparison. This is a host integration check, not a new hardware
or listening qualification.

The upload extension is covered by Max-message lifecycle tests, USB/Wi-Fi target
and failure tests, and the actual Studio HTTP handler with simulated transports.
An actual `build_upload usb` from Max also loaded the native example on XIAO:
parameter readback, Pause/Resume, runtime counters and reboot persistence passed.
The prior package and controls were restored. A corrupt package rejected before
transfer. See the [USB check receipt](../../evidence/max-usb-upload-player.json).
The check ran at zero output volume without DAC capture/listening. Wireless
uploads from Max remain pending because the saved network was unavailable.
