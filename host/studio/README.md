# RNBO Studio

A local browser workspace for compiling one self-contained Main `.rnbopat` into
a `.rnbopkg` and loading it into a stable ESP32-S3 player. Include effects inside
the Main patch. The same package works on XIAO ESP32-S3 and Waveshare AMOLED V2.

```sh
./host/studio.sh
```

Open **http://127.0.0.1:8788**:

1. Select the USB device. Under **Install/update player**, select its board and
   install the player once. Use this action again only when updating the player.
2. Open a `.rnbopat` or load the example, choose compile settings, and click
   **Compile patch**.
3. Click **Load compiled package**. Normal loads transfer checksummed chunks over
   USB and do not flash application firmware.

Audio pauses briefly during replacement; this is not a gapless swap. The selected
package is saved and starts again at power-on. A completed package can also be
downloaded as `.rnbopkg`.

To reuse a downloaded package after restarting Studio, choose **Open .rnbopkg**,
then **Load compiled package**. Studio validates its envelope, checksums and
zero-import ELF and keeps a private copy. It does not rebuild the patch or rerun
the native startup screen. The editable `.rnbopat` is not included in the package;
keep that source separately when you want to make changes.

Compilation exports RNBO C++, applies the selected compiler profile, runs a short
native startup screen, builds a zero-import Xtensa module, and wraps it with its
name, source identity, arena limit, startup volume and optional visual layout.
The startup screen checks default settings for four warmup and four render blocks.
Its native host wrapper and allocation coverage differ from the dynamic Xtensa
wrapper, so it does not prove target arena sufficiency, all control settings, or
real-time performance. Native modules are trusted executable code; checksums are
integrity checks, not isolation. An unchecked native allocation failure can still
trap; retain a sufficient arena reserve.

The graph is a preview of the input patch. Editing JSON or compile settings
invalidates the previous package. Board selection affects only player installation.
Live volume and parameter changes are RAM state; package metadata supplies startup
volume. Parameter controls include the
active generation, so queued controls cannot target a replacement patch. A queue
acknowledgement and later readback do not prove an exact application sample.

Player installation retains the existing application-only write at `0x10000`,
matching-board flash/partition checks, a private 3 MiB recovery backup, and complete
application readback. An incompatible partition layout rejects before writing.
Installation is the separate firmware-changing action. Failed writes are not
silently retried or automatically rolled back. Private builds, logs and receipts
remain under ignored `build/`; generated RNBO code is not published by Studio.

## Requirements and scope

- Node.js and the user's authorised RNBO **1.4.4** package (`RNBO_DIR` if needed).
- ESP-IDF **5.5.0**, its Xtensa toolchain, CMake and a native C++ compiler.
- `pyserial` and `esptool` in the selected IDF Python environment. The launcher uses
  an installed IDF environment; `RNBO_STUDIO_PYTHON` can override it.
- For AMOLED player installation, the pinned dependency collection via
  `--components-from PATH`, or the verified `build/vendor-amoled` cache.

One Main patch has 0 signal inputs, 2 outputs, up to 32 parameters, 44.1 kHz and
256 frames per callback. Existing exporter/polyphony restrictions still apply.
There is no separate FX slot. The arithmetic selector defaults to
`float32-strict`; `float32-audio-v1` remains an explicit reviewed option with its
own rounding scope. Filter-delay caps and Float32 delay storage remain opt-in;
unset options preserve normal defaults. Arena reserve is capacity, not consumption.

Pause/Resume preserves patch state. Telemetry describes audio work through PCM
conversion, excluding I²S wait; it is not total dual-core CPU usage. An empty player
can report panic while continuing to output silent frames.

The server binds only to loopback, uses a session token for mutations, and stops
its compiler process group on exit. It waits for a firmware write to finish before
releasing the device. GitHub Pages cannot run this local compiler or access USB.

```sh
python3 -m unittest discover -s host/compiler -p test_package.py
python3 -m unittest discover -s host/studio -p 'test_*.py'
node --test host/studio/test_web.mjs
```

HTTP tests use a temporary loopback port; all device tests use fakes. Actual player
installation and package loading are qualified separately by the hardware owner.
