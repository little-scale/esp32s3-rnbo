# RNBO for ESP32-S3

Run patches exported by **Cycling ’74 RNBO in Max** on a stable ESP32-S3 player.
The supported route is **C++ Minimal Export → native Xtensa module → `.rnbopkg` → player**.
Our former `.rnbopat` importer and visual Gen translator are retired.

Use [RNBO Studio](http://127.0.0.1:8788) for compilation, USB/Wi-Fi package uploads,
live parameters, volume, pause and device measurements:

```sh
./host/studio.sh
```

In Max, choose the C++ source target, **Minimal Export**, **Copy Library**, fixed
**44,100 Hz / 256 frames**, and stereo outputs with no audio inputs for a Main
package. Currently the adapter qualifies **RNBO 1.4.4**. Open the complete export
folder or ZIP in Studio. An optional matching `.rnbopat` supplies the drawing;
it is never translated into audio code. The [Max build helper](host/max/README.md)
can export a live embedded `rnbo~` and attach its drawing automatically, including
unsaved edits. Send it `upload usb` / `upload wifi` to load its completed package,
or `build_upload usb` / `build_upload wifi` to compile and load in one action.
An installable [Max helper ZIP](https://little-scale.github.io/esp32s3-rnbo/downloads/esp32s3-rnbo-max.zip)
includes the abstraction, scripts, example and help patch. See the [export guide](docs/native-export.md).

Both boards share the same module ABI and player code: **Seeed XIAO ESP32-S3**
with stereo I²S, and **Waveshare ESP32-S3 Touch AMOLED 1.8 V2** with its display,
touch controls and ES8311 mono output. Install the player once; replacing a
package saves the new Main patch for reboot without reflashing the application.
All effects belong inside Main.

We retain the package loader, bounded allocation arena, USB and Wi-Fi transports,
parameter metadata and controls, AMOLED patch drawing/multislider/meter,
[physical-input `@meta` bindings](docs/physical-inputs.md), and
[UART/experimental USB-host MIDI](docs/midi-inputs.md).
Audio uses the **baseline Float32 wrapper**; scheduler time remains Float64.
Importer-era source optimisation profiles are not offered in Studio.

The [wrapper review](docs/native-wrapper.md) describes what stays and what still
needs qualification, including event timing and bounded lists. The
[native export comparison](docs/native-export-comparison.md) records real Max
exports and XIAO measurements: no measured CPU change in three matched contexts,
and a visual Gen modulo export that now compiles. Native export does not remove
all runtime or allocation limits.

See [current status](docs/STATUS.md) and the [public dashboard](https://little-scale.github.io/esp32s3-rnbo/).
Previous object checks and optimisation gains remain **historical importer-route
evidence**, not blanket qualification of the new route. The broad testing goal
remains paused. The [archive](archive/README.md) preserves reproducibility.

For command-line builds and prerequisites, see [host tools](host/README.md).
Max/RNBO is required to create exports; compiling a complete export needs Python,
CMake, a C++17 compiler and ESP-IDF 5.5 with the pinned Xtensa dependencies.
Node and the internal RNBO generator are not part of the supported compiler path.

Generated code retains Cycling ’74’s licence notices. See
[third-party notices](THIRD_PARTY.md) and the licences included in each export.
