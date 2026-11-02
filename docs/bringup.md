# AMOLED V2 hardware bring-up

Primary board: Waveshare ESP32-S3 Touch AMOLED 1.8 V2, 16 MiB flash and 8 MiB
octal PSRAM. The checked firmware builds do not establish physical results.
Recorded physical results are now available in
[the implementation status](STATUS.md) and
[hardware evidence](../evidence/amoled-v2-hardware.json).

## Prepared candidates

The default static RNBO build is the autonomous stereo oscillator at 44,100 Hz
and 256 frames, downmixed by averaging channels and applying fixed 0.5 sink
headroom. It needs no first touch or MIDI event. The headed shell includes an
FM1-style patch view, battery readout, volume, Panic and Resume. Graph extraction,
touch parameter controls and dense-layout fallback are described in
[patch-view.md](patch-view.md).

Build candidates remain under ignored `build/` directories. Read each
`build-report.json` to identify the exact source, ELF/binary digest, board,
resolved configuration and compiler before selecting one. Sine and four-voice
MIDI builds have separate variants. Build helpers never flash a device.

The native loader spike is a **separate test application**. It neither drives
the display nor produces audio. Its build and physical exit gate are documented
in [loader-spike.md](loader-spike.md).

## First connected session

1. Confirm the board is the V2 and identify its current USB Serial/JTAG port.
   Close any existing Studio/serial reader before opening another connection.
2. Preserve any existing firmware/settings needed for recovery. The reviewed
   factory partition layout is retained; this implementation has no firmware
   OTA A/B slots or persistent RNBO package store.
3. Use the AMOLED V2 build's own generated flashing arguments. A successful
   build is not a reason to select an XIAO binary. Re-enumerate the port after
   reset. Physical USB reconnect and BOOT recovery remain available if reset
   control lines do not restart the board.
4. Record the complete boot log and `status`, including firmware/module digests,
   PSRAM, rate/vector, heap guard, driver errors and audio task stack headroom.
5. Confirm the display/touch and speaker path. Buffer capture is a separate
   check from electrical output and listening.

The configured application flash mode is QIO. IDF deliberately writes the
bootloader with a DIO image header before it enables quad operation; this is
documented in the pinned ESP-IDF esptool Kconfig and is not a profile mismatch.

## Bring-up serial commands

The first shell uses newline-delimited commands at 115200 baud. It is a local
diagnostic interface; it is not the final authenticated deployment protocol.

| Command | Effect |
| --- | --- |
| `status` | Copied audio telemetry, allocation counters, identity and lifecycle state |
| `volume 25` | Master volume target, available even while muted; 20 ms gain ramp |
| `parameters` | Shell-owned copied parameter schema; indices belong to this static build |
| `param 0 440` | Queue an actual parameter value at the next block boundary |
| `normalized 0 0.5` | Queue a normalized value using RNBO's own conversion |
| `midi 0x90 69 100` | Complete channel note-on; MIDI fixture required to produce sound |
| `midi 0x80 69 64` | Complete channel note-off |
| `panic` | Immediate final mute; cancel queued events and request detached reconstruction |
| `resume` | Resume a successfully prepared matching Panic generation |
| `capture 44100` | Start a one-second recording of successfully submitted post-volume PCM |
| `capinfo` | Recording ID, completion, format and negotiated read limit |
| `capread ID OFFSET COUNT` | Read up to 1024 bytes from the completed matching recording |
| `heap_probe` | Explicit negative allocation-guard test; expected fault requires reboot |

Program-change and channel-pressure MIDI commands carry two bytes, for example
`midi 0xc0 1`. Other supported channel messages carry three. SysEx, realtime MIDI
bytes and sample-offset scheduling are not implemented in this first interface.
MIDI is never coalesced; queue overflow latches Panic. Parameter/MIDI events are
rejected while muted or rebuilding. A queued acknowledgement means queued,
not yet applied.

Panic parks the audio owner after its current callback, while the sink continues
writing zeros. Core 0 snapshots parameters, destroys/reconstructs the patch,
warms it and restores parameter values. The audio owner attaches only after
preparation and a matching explicit Resume. A stale Resume cannot clear a newer
Panic. Notes, oscillator phase, random evolution and delay tails are reconstructed,
not restored. The volume target survives this cycle.

If a restored parameter allocates after the wrapper's preparation freeze,
reconstruction fails conservatively and remains silent. A successful late heap
allocation on the running audio task latches a persistent fault requiring reboot.
Allocation counters are requested-byte totals, not a measured live-state peak.

## Capture and qualification

Use the [capture client](../host/clients/README.md) from a Python environment
with `pyserial` already installed. The ESP-IDF Python environment is one such
option. It validates the exact board/profile, recording ID, chunk boundaries,
lengths and advertised identity before saving WAV and proof metadata. AMOLED
captures mono; XIAO captures stereo. Both cap recordings at one second, and the
final partial 256-frame vector is clipped to the requested frame count.

Start with unity volume, then verify 50%, zero and Panic silence. Record driver
errors, nonfinite/clipped samples, allocation counters and worst observed busy
time. Compare host and target only with the same source, parameters, seed and
warm-up: current firmware uses **four** warm-up blocks and seed `0x12345678`.
The host renderer defaults to one warm-up block and a different seed; use
`--warmup 4 --seed 0x12345678` before making an exact waveform comparison.

The render counter includes event handling, DSP and final PCM work, excluding
blocking I²S pacing and post-write capture copying. The diagnostics builds record
driver elapsed time and post-write capture separately. DMA buffering means Panic
cannot retract samples already submitted to the driver. Recorded measurements
cover the tested fixtures with the display and capture active, Wi-Fi inactive;
they are observed timing results rather than hard worst-case guarantees.
