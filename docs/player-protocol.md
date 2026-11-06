# Stable RNBO player integration contract

> **Current intake:** create C++ with Max’s [Minimal Export](native-export.md), then compile/package it in Studio. `.rnbopat` is drawing data only. Hardware interfaces below are retained; earlier patch/compiler measurements apply only to their recorded builds.

A board-specific player application stays installed. Max exports RNBO C++; Studio
compiles a self-contained Xtensa ELF, and wraps it in a `.rnbopkg` package. Patch
loads do not write the application/bootloader/partition regions. Native patches
remain trusted code; checksums and descriptor checks are admission checks, not
memory isolation or authentication.

## Package v1

Little-endian 128-byte header: magic `RNBOS3P1` (8 bytes), then nine uint32 fields
`header_bytes=128, version=1, abi_major=1, role, sample_rate=44100,
block_frames=256, arena_bytes, metadata_bytes, elf_bytes`. These are followed by
32-byte SHA256 of the ELF, 32-byte SHA256 of the metadata, and 20 zero bytes.
Payload is UTF-8 JSON metadata followed by the ELF, with no trailing bytes.
Role is 1=Main (0 signal inputs, 2 outputs). Other roles reject. All effects live inside Main.
Arena is 4096..4194304 bytes, metadata at most 65536 bytes, ELF at most 524288 bytes.
Metadata requires `name` (1..63 UTF-8 bytes), `source_sha256` (64 lowercase hex),
`initial_volume` (integer 0..100), and may contain `visual` from host/visual/layout.py.
Unrecognized metadata fields can be ignored; invalid required fields reject.
Package SHA256 identifies the entire exact header+payload. Modules have zero
undefined imports, ABI1, fixed 44100/256 and the existing single-instance wrapper.
Each active image has its own state, arena, context and sample position.

MIDI-input packages add optional `midi_input_ports:1` metadata and module flag
`RNBO_S3_SHORT_MIDI_INPUT` (bit 16). The event layout and ABI remain 1.0. The
updated player declares `midi_input_version:1`; Studio checks it before upload.
Older loaders reject the new flag. Hardware input is routed only to modules
with that capability, so old packages need recompilation for hardware MIDI.
Non-MIDI prepared manifests/configs retain their previous shape.

### Envelope v2: physical inputs

Input-bound packages set header `version=2` with the same layout, magic and
module ABI. They require one `physical_inputs` object with schema version 1,
board `xiao`, and canonical bindings keyed by stable `parameter_id`. An old
player rejects version 2 instead of ignoring physical controls. The updated
player accepts v1 without bindings and v2 with bindings; a version/binding
mismatch rejects. Studio checks `physical_inputs_version:1` before transfer.
The player separately checks binding schema, GPIO reservations and module IDs
before activation. See [pin mappings and options](physical-inputs.md).

## USB v1

UTF-8/ASCII commands terminated by newline; exactly one JSON response per command.
Maximum command line 8192 bytes; binary chunks use hex to avoid console escaping.

- `player-info`: runtime=`rnbo-esp32s3-player`, api_version1, board, firmware ELF
  SHA, rate, block_frames, generation, paused/panic, volume, maintenance, telemetry,
  and the Main identity with parameter schemas/actual/normalized values.
  Parameters are per-role indexes; fields name/min/max/initial/index/actual/normalized.
- `player-begin ROLE TOTAL_BYTES SHA256`: allocate a bounded staging buffer;
  reply `upload:ready, offset:0, chunk_bytes:1024`. Old audio can continue receiving.
- `player-data OFFSET HEX`: exact contiguous offset and at most 1024 decoded bytes;
  reply `upload:chunk, offset:NEW_OFFSET`. A bad chunk rejects/aborts staging.
- `player-abort`: discard staging without changing active patch.
- `player-commit`: require exact size/hash/package validation, then pause DMA at an
  audio block boundary. Load/prepare and screen the candidate while the old image
  remains available, stage in inactive storage, commit boot selection, switch, unload old image,
  and resume DMA. Reply `upload:committed, generation, role, package_sha256` only
  on complete success. Before durable selection changes, failure retains the old
  patch and boot selection. An audio-driver resume failure after selection commits
  returns an error with `old_retained:false`; the new saved patch requires a restart.
- `player-pause`, `player-resume`: pause/resume DSP without destroying patch state.
- `player-volume PERCENT`:0..100; live value is RAM state; Main startup metadata
  supplies initial volume when installed/rebooted. Fresh empty player defaults 50%.
- `player-param ROLE GENERATION INDEX NORMALIZED`: exact active generation and
  per-role bounded index, normalized finite 0..1. Queue to audio owner; reply queued.
- `player-midi GENERATION STATUS D1 D2`: complete supported short MIDI message
  to the capable Main audio owner. Length follows status; unused data bytes are
  ignored. Queue admission requires the current generation and playing state.
- `player-midi-config off|uart`: park DMA and save UART MIDI selection in NVS;
  reject D7/GPIO44 physical-binding conflicts. Reply `midi_configured:true`.
- `player-midi-stream GENERATION HEX`: diagnostic software byte stream, 1..128
  bytes, parsed with running status; reply `midi_stream_accepted:true` confirms
  parsing was attempted, not audio delivery. Counters/readback verify delivery.
- `player-midi-loopback GENERATION HEX`: same bounded diagnostic through UART1
  internal TX/RX loopback, requiring enabled UART. TX is not routed to a pad.
- `player-wifi-scan`: USB-only, after startup verification and outside a package
  transfer; park DMA and return `networks:[{ssid,rssi,channel,secure}]`. At most
  24 visible UTF-8 personal/open network names are returned, strongest first and
  deduplicated. Scanning does not save credentials.
- `player-wifi-setup SSIDHEX PASSWORDHEX KEY64HEX`: USB-only provisioning while
  parked. Studio supplies a random 32-byte key; the SSID is 1–32 UTF-8 bytes and
  password is 8–63 bytes, or `-` for an open network. Replies do not return secrets.
- `player-wifi-forget`: USB-only removal of Wi-Fi settings; saved Main packages
  remain. Scan/setup/forget reject before the Main startup guard has cleared.

`player-info` includes `wifi:{supported,configured,connected,ip,device_id,port,error?}`
without credentials or pairing keys. The separate TCP transport on port 8789
uses fresh server/client nonces, HMAC-SHA256 and contiguous request sequences.
Its JSON envelopes carry the same command/reply text; setup/scan/forget stay
USB-only. Authentication provides integrity, not confidentiality. See
[player-wifi.md](player-wifi.md) for exact MAC domains, setup and current validation
limits.

`player-info` adds `midi_input_version:1` and a `midi` object with UART mapping,
host-build/attachment state, queue use, accepted/delivered/dropped message counts,
transport errors and recovery counts. See [MIDI input](midi-inputs.md) for supported
messages, clock timing, note cleanup, exact pin mapping and host-build limits.

No filesystem writes, module loading, allocation or image destruction run in the
audio owner. Maintenance deliberately pauses audio; this first integration does
not promise a gapless swap. The DMA owner stops/starts DMA itself and acknowledges
parking before any flash maintenance. Control/USB is the only image/storage owner
while parked. Generation-stamped ordinary events cannot target a replaced image.

## Durable selection

Use the existing `storage` SPIFFS partition and NVS, with two checked files for Main and an atomic NVS selection. Write only an inactive file, sync and
validate it before committing a selector. Keep previous file for recovery. Boot
tries selected package, then previous valid package; invalid packages leave the
player responsive and quiet. Startup image preparation must succeed before DMA.
The stable firmware and partition layout are independent of patch compilation.

## Admission and recovery limits

The player accepts at most 32 input parameters and uses a separate bounded arena
for each candidate. During a swap, the candidate and previous image coexist until
selection commits. A short detached target screen checks 16 callbacks for finite
samples, allocation statistics and callback time (5,224 µs ceiling, reserving time
for the sink). It advances the new patch before activation. This is an admission
screen, not qualification of every parameter setting or a worst-case timing proof.

A persistent preparation guard records the candidate before native preparation.
If preparation traps or a reset interrupts its first blocks, the next boot blocks
that package identity and tries the previous valid package. Clearing the guard
requires at least two actual, healthy, unpaused blocks from the matching image.
Recovery is not native-code isolation: an unchecked allocation failure or faulty
native code can still reset the board. A failed DMA restart quarantines rendering
until restart. Live controls do not reconstruct the patch on Resume.

Existing storage is never erased to force a mount. Formatting is allowed only
when the complete storage partition has been checked as erased. Previous-package
promotion changes the checked selector without rewriting the surviving file.

## Validation

The [XIAO player evidence](../evidence/player-xiao.json) records the exact tested
firmware and package identities, replacement/reboot checks and measured audio
telemetry. The one-time player installation verified its complete application
readback. Subsequent sine/drone swaps transferred packages only; the running
firmware ELF identity stayed unchanged. The browser also reopened and loaded the
saved drone package without running the compiler. A 60-second sampled run passed
with all audio error counters zero, about 68.9% audio work per block and a
4,512 µs peak within the 5,805 µs block budget. Transfer-checksum errors, a malformed
package and stale-generation controls were rejected on the device while retaining
the drone. Pause froze the image position and Resume continued it. Reboot restored
the saved drone at its 50% startup volume.

Both board player applications compile. AMOLED runtime layout replacement and
controls also pass computer-side LVGL checks; this player has not yet been tested
on an AMOLED device. XIAO PCM telemetry confirms nonzero output after volume and
zero output when paused or at zero volume; these checks do not capture the DAC's
physical output. Fault-injection tests exercise the actual control, loader and
storage C with simulated hardware boundaries. They do not prove power-loss
behavior at every instant, real FreeRTOS scheduling, or all possible RNBO patches.
