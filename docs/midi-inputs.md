# MIDI input on the XIAO player

## Return-to-test checklist

**Deferred at the user's request, 5 November 2026.** Return when an external
MIDI source and receiver/host hardware are available. Complete UART testing
first, then USB host. Internal loopback results below remain separate from
physical-interface validation.

- [ ] **UART:** connect a suitable receiver to D7/GPIO44; verify notes, velocity,
  channels, CC, pitch bend, running status, clock and Start/Continue/Stop through
  the corresponding RNBO objects.
- [ ] Verify held-note release on pause/resume, Active Sensing timeout where
  supported, UART enable/disable and reboot persistence. Check D7 binding conflicts.
- [ ] Record CPU percentage, peak callback time, queue drops/overflows and audio
  faults during sustained MIDI traffic; flag unexpected costs for optimisation.
- [ ] **USB host:** prepare adapter, suitable VBUS power and paired Wi-Fi; install
  the experimental host variant and verify enumeration, MIDI delivery, clock,
  unplug/reconnect and held-note recovery with a real controller.
- [ ] Save hardware evidence and update validation claims only for checks that
  actually pass. Restore the user's selected patch/settings and agreed player
  variant afterward.

The Main patch receives MIDI through its ordinary RNBO objects: `midiin`,
`notein`, `ctlin`, `bendin`, and other MIDI parsers included in that patch.
There is no parameter-name or `@meta` convention for MIDI. Physical parameter
bindings remain available alongside it.

## UART first

Install the updated standard XIAO player through Studio, then compile and load
your MIDI patch again. Under **MIDI input**, choose **UART · D7 / GPIO44** and
save. The setting survives reboot. MIDI starts **off** on a fresh configuration;
it does not change patch startup volume or pause settings.

| Item | Exact mapping |
| --- | --- |
| Receiver | UART1 RX, **D7 = GPIO44**, the pad also labelled RX |
| Format | MIDI 1.0 serial, **31,250 baud, 8 data bits, no parity, 1 stop bit** |
| Signal | 3.3 V logic output from a suitable MIDI receiver into D7 |
| Transmitter | None; no GPIO is assigned to UART TX |
| RNBO destination | Main patch, MIDI input port 0, preserving channels 1–16 |
| Audio pins | Unchanged: BCLK GPIO7, WS GPIO8, data GPIO9 |

A DIN/TRS MIDI connector needs a proper MIDI receiver interface. Do not wire
its current-loop signal or a 5 V logic output directly into GPIO44. For a
3.3 V logic-level UART sender, connect its TX to D7 and its ground to XIAO GND.
The UART RX input uses a pull-up when enabled.

D7 remains available to a digital `@meta` binding while UART MIDI is off.
Enabling UART while a loaded patch binds GPIO44 is rejected. Loading a patch
that binds GPIO44 while UART is enabled is also rejected. Disable UART before
changing between those uses. UART MIDI v1 is XIAO-only; the AMOLED player still
builds from the same codebase, with this UART profile unavailable.

## Messages and MIDI clock

Channel voice messages, running status and velocity-zero NoteOn are handled.
Realtime bytes can interrupt another message without corrupting it. Supported
short system messages include clock **F8**, Start **FA**, Continue **FB**, Stop
**FC**, Active Sensing **FE**, Reset **FF**, quarter-frame **F1**, song position
**F2**, song select **F3**, and tune request **F6**. SysEx is skipped; its
interleaved realtime messages still pass. Reserved statuses are discarded.

For a simple clock counter, use:

```text
midiin -> select 248 -> counter
```

See the silent [MIDI monitor example](../examples/midi-monitor.rnbopat), which
publishes note, velocity, raw byte and clock count as parameters. Clock is
delivered to the patch as MIDI messages; the player does not automatically
derive BPM or set a transport. Events apply at **256-frame audio boundaries**
(about 5.805 ms at 44.1 kHz), without sample-offset timestamps. This is suitable
for initial clock support; it does not claim sample-accurate external sync.

The fixed input queue holds 128 complete messages; at most 64 are delivered per
audio block. The audio task performs no UART/USB reads or transport allocation.
Pause, overflow, UART errors, disconnect and Active Sensing timeout request
recovery: sustain-off on all channels, followed by explicit releases for tracked
notes before accepting new notes. This reaches plain `notein` patches as well
as voice allocators. A patch's own release envelopes can still take time.

Studio shows delivered messages and queue overflows. `player-info` also exposes
UART bytes/errors, ignored USB packets, dropped messages and recovery counts.
Receiving Active Sensing enables a 350 ms silence timeout for the UART source.

New MIDI packages declare `midi_input_ports: 1` and module capability bit 16.
Older packages continue to load, but need recompiling to receive hardware MIDI.
Updated Studio rejects a new MIDI package on an older player before transfer.
The in-memory event layout and ABI version remain unchanged; an older loader
rejects the new capability flag rather than silently admitting it.

## Experimental USB host build

A separate XIAO player variant implements class-compliant **USB MIDI 1.0 input**:
one device, the first supported alternate-zero MIDIStreaming bulk IN endpoint,
and cable 0 routed to Main input port 0. MIDI 2.0, SysEx, MIDI output and merging
multiple USB devices/cables are outside this version.

```sh
python3 tools/build_firmware.py xiao --player --usb-midi-host --variant midi-host-v1
```

The build requires an explicit variant and is not Studio's normal install.
ESP32-S3's native USB host uses the same internal USB PHY as USB Serial/JTAG;
this variant disables the USB console. Pair Wi-Fi with the standard player
first, so Studio can upload packages and control the host player over Wi-Fi.
The XIAO then needs a suitable host adapter and external 5 V VBUS supply for the
MIDI device; the firmware does not configure a GPIO as a VBUS power source.
Use a power arrangement appropriate to the boards and avoid feeding two power
sources into one another. Bootloader recovery is needed to return to the
standard USB player if Wi-Fi is unavailable.

USB configuration parsing and event-packet decoding are tested on the computer;
the host firmware compiles. **Physical enumeration, controller compatibility,
disconnect recovery and CPU cost with a USB device attached remain untested.**
The host variant has not been installed on the user's board.

## Checks without a MIDI controller

The [5 November XIAO run](../evidence/player-midi-xiao.json) passed: 206 messages
were accepted and delivered, with 96 software clocks and 96 UART-loopback clocks
counted exactly. Eleven loopback transfers received 117 UART bytes without UART
errors. Note/velocity, running status, realtime interleaving, transport/system
common, pause/resume release and Active Sensing recovery passed. Audio faults,
missed deadlines and audio-owner/late allocations remained zero. The silent
monitor's final callback measured 287 µs (4.94% of the audio period), with an
observed 831 µs peak (14.32%); these include the monitor patch and PCM output,
and are not an isolated MIDI-overhead benchmark. Main `a` was restored at 50%
with its parameter value restored and UART off.

The native monitor test exercises the actual generated RNBO code and C event
wrapper, including exact counting of 96 clocks. The C parser test covers running
status, realtime interleaving, SysEx filtering, malformed streams, USB descriptor
bounds and note recovery under undefined-behavior checking.

`tools/check_player_midi.py` can temporarily load the silent monitor, inject
software messages, and use **UART1 internal TX-to-RX loopback**. The diagnostic
does not route TX onto a pad. It tests the UART peripheral, RX driver, parser,
queue and RNBO delivery without external hardware, then restores the identified
Main package, volume, parameters and UART setting in `finally`. Close Studio's
USB connection before using this command; supply the exact currently loaded
package as `--restore-package`.

Internal loopback does **not** verify the D7 pad, receiver circuit, DIN/TRS
electrical interface or actual controller timing. Those are the next hardware
checks, followed by USB-host attachment tests.

Reproduce the computer-side checks after exporting/preparing the monitor:

```sh
python3 tools/test_midi_core.py
cmake -S . -B build/midi-monitor-native \
  -DRNBO_S3_EXPORT_DIR="$PWD/build/research/midi-v1/monitor-prepared" \
  -DRNBO_S3_MIDI_MONITOR_TEST=ON
cmake --build build/midi-monitor-native
ctest --test-dir build/midi-monitor-native --output-on-failure
```

References: [ESP-IDF 5.5 UART](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32s3/api-reference/peripherals/uart.html),
[USB Host Library](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32s3/api-reference/peripherals/usb_host.html),
[ESP-USB hardware constraints](https://docs.espressif.com/projects/esp-usb/en/latest/esp32s3/usb_host.html),
[MIDI electrical specification update](https://midi.org/wp-content/uploads/wpforo/default_attachments/1709416667-ca33-MIDI-10-Electrical-Specification-Update.pdf).
