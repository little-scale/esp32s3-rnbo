# RNBO Studio

A local browser workspace for compiling one self-contained Main `.rnbopat` into
a `.rnbopkg` and loading it into a stable ESP32-S3 player. Include effects inside
the Main patch. Ordinary packages work on XIAO ESP32-S3 and Waveshare AMOLED V2;
packages with physical input bindings currently require the XIAO profile.

**Float32 trial — unverified kernels** is an explicit arithmetic option under
Advanced build settings. It runs a default-output comparison with Auto and offers
a downloadable review report; saved packages retain their experimental label.
See [scope, logs and promotion to the reviewed list](../../docs/float32-trial.md).

```sh
./host/studio.sh
```

Open **http://127.0.0.1:8788**:

1. Select the USB device. Under **Install/update player**, select its board and
   install the player once. Use this action again only when updating the player.
2. Open a `.rnbopat` or load the example, choose compile settings, and click
   **Compile patch**.
3. Click **Load compiled package**. Normal loads transfer checksummed chunks over
   USB, or paired Wi-Fi after setup below, without flashing application firmware.

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
The XIAO player's **MIDI input** section saves optional UART input on
**D7/GPIO44**, 31,250 baud. Compile a patch containing MIDI objects again after
installing the updated player. Clock and other short system messages reach
`midiin`; physical receiver wiring and USB-host attachment require later checks.
See [MIDI mapping, clock and host-build instructions](../../docs/midi-inputs.md).

Live volume and parameter changes are RAM state; package metadata supplies startup
volume. Parameter controls include the active generation and connection identity,
so queued controls cannot target a replacement patch or another selected player. A queue
acknowledgement and later readback do not prove an exact application sample.

Player installation retains the existing application-only write at `0x10000`,
matching-board flash/partition checks, a private 3 MiB recovery backup, and complete
application readback. An incompatible partition layout rejects before writing.
Installation is the separate firmware-changing action. Failed writes are not
silently retried or automatically rolled back. Private builds, logs and receipts
remain under ignored `build/`; generated RNBO code is not published by Studio.

## Wi-Fi setup and use

Update the player over USB once to install its Wi-Fi support. With **Connection**
set to **USB**, select the board and click **Connect USB**. Open **Wi-Fi setup · via
USB**, click **Scan nearby networks**, and select a network. Audio pauses briefly
while the board scans; scanning does not change or save network settings. You can
also enter a hidden network name manually. Enter the password, then click
**Save Wi-Fi & pair**. The
password is cleared from the page when sent. Studio saves a private pairing key
and address under ignored `build/private/studio/`; it does not save the network
name or password on the computer. The board keeps its network settings.

Wait for the Wi-Fi status to show a connection and address. Choose **Wi-Fi** under
**Connection**, select the saved player, and click **Connect Wi-Fi**. You can then
load a compiled or saved package and use the same live controls with USB unplugged.
Keep the board powered by a battery or another power source. The computer must
remain on a network that can reach the board, with Studio running locally.

This route uses saved, numeric private IPv4 addresses; it does not scan or discover
players. If DHCP changes the address, enter its current address in **IP address
override**, or reconnect over USB to refresh it. **Forget Wi-Fi** requires USB and
removes the board's settings and that player's saved pairing on this computer.
Player firmware installation and updates still require USB.

Commands and replies use HMAC-SHA256 authentication with fresh connection nonces
and sequence numbers. This detects modification and replay; it does **not encrypt**
the package, metadata or controls. Use a trusted LAN, not an Internet-facing or
untrusted shared network. Native packages remain trusted executable code. Wi-Fi
transport does not add memory isolation. A failed or timed-out mutating command
is not automatically repeated; reconnect and inspect the player before retrying.

## Requirements and scope

- Node.js and the user's authorised RNBO **1.4.4** package (`RNBO_DIR` if needed).
- ESP-IDF **5.5.0**, its Xtensa toolchain, CMake and a native C++ compiler.
- `pyserial` and `esptool` in the selected IDF Python environment. The launcher uses
  an installed IDF environment; `RNBO_STUDIO_PYTHON` can override it.
- For AMOLED player installation, the pinned dependency collection via
  `--components-from PATH`, or the verified `build/vendor-amoled` cache.

One Main patch has 0 signal inputs, 2 outputs, up to 32 parameters, 44.1 kHz and
256 frames per callback. Existing exporter/polyphony restrictions still apply.
There is no separate FX slot. Studio defaults to **Automatic Float32 audio**
(`float32-auto-v1`): it applies the reviewed audio-kernel transformations where
their exact guards match, and leaves unknown forms unchanged. This changes rounding
and does not promise that every operation becomes Float32 or that every patch fits
the audio budget. Standard arithmetic (`float32-strict`) and the explicitly named
profiles remain available; the command-line preparer's default remains strict.
Filter-delay caps and Float32 delay storage remain separate opt-in settings.
Arena reserve is capacity, not consumption.

Beside **Load compiled package**, Studio shows the **Currently running** Main and
the **Package to load** separately. A CPU-screen rejection means the transfer
completed but the candidate was not activated; the player keeps its previous
state. The persistent result shows the measured callback time, the roughly 5.8 ms
block budget, and the original error. The player also reserves part of that budget
for audio output. If editable source is open, **Recompile with Float32 optimisation**
selects the automatic audio profile and compiles again without changing delay
storage or loading the result automatically. Compiler and other load errors remain
visible; the original source stays open.

Pause/Resume preserves patch state. Render and peak show microseconds alongside
**Audio CPU** percentages: `time_us × sample_rate / (block_frames × 1,000,000) × 100`.
They describe callback work through PCM conversion, excluding I²S wait, relative
to one audio block's time budget. They are not total dual-core CPU usage; a value
above 100% exceeds that block budget. An empty player can report panic while
continuing to output silent frames.

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
# Physical parameter inputs

Use inline `@meta` on RNBO `param` objects to bind XIAO analog, digital or touch
inputs. See the [exact pin map, syntax and options](../../docs/physical-inputs.md).
An updated player is required once over USB; mappings then travel in each package.
Studio shows package bindings and live raw readings. Physical hardware testing is
pending; AMOLED external-input mappings are not enabled by this XIAO profile.
