# Build an embedded RNBO patch from Max

The helper builds the **live `rnbo~` object**, including edits that have not been
saved. The RNBO patch stays embedded in its parent `.maxpat`. A separate
`.rnbopat` file is not required.

Open [embedded-sine.maxpat](embedded-sine.maxpat) for a working example. Start
`./host/studio.sh`, then click **build** in the helper panel. Click **open** to
view that build in Studio, inspect its drawing and load the completed package.
No package upload or firmware installation is automatic.

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
reports the error; it does not reuse an older export or automatically upload a
previous package. Temporary export/package files may be removed by the OS;
use Studio's download button to keep a package permanently. Build links refer to
jobs in the running Studio session and expire when that server restarts.

The [integration receipt](../../evidence/max-embedded-build.json) records a real
Max build with a gain object added only in memory, the resulting drawing and
native-output comparison. This is a host integration check, not a new hardware
or listening qualification.
