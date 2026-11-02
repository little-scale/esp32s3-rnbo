# Serial PCM capture

`capture.py` records the current post-volume PCM buffer from the bring-up shell.
The primary AMOLED board produces mono signed 16-bit PCM; XIAO produces stereo.
Both use 44,100 Hz, with up to 44,100 frames per recording.

Close other applications using the same serial port. The client opens the exact
port exclusively. On the tested primary AMOLED V2/macOS USB connection, setting
DTR true/RTS false before opening and then DTR false after opening preserved the
running device's frame clock and volume. The earlier false/false opening sequence
reset that board. The current sequence is not a universal guarantee for other
boards, operating systems, or USB adapters. It sends no flash, upload, Panic,
volume, or parameter commands. `pyserial` must already be
available in the Python environment used for the command; it is an optional
dependency and is not installed by this tool.

```sh
python3 host/clients/capture.py --port /dev/cu.YOUR_DEVICE \
  --board amoled --output build/captures/amoled-first.wav
```

Select `--board xiao` for the stereo board. The client checks the runtime family,
exact board model, sample rate, vector size, and channel count before starting.
It requires the new `capinfo.max_chunk_bytes` capability and never requests more
than 1,024 bytes per chunk. The recording ID must match throughout polling,
download, and final verification. Offsets, lengths, hexadecimal data, completed
frames, and final device identity are checked before any output is saved.

The WAV is accompanied by `FILE.wav.json`, containing raw status snapshots,
recording identity, PCM/WAV hashes, and advertised `firmware_elf_sha256` and
`module_source_sha256` identities when available. The firmware ELF digest and
prepared module source-tree digest describe different artifacts; neither is
treated as a digest of the other. Missing identities are explicitly recorded as
unknown. Existing WAVs or
sidecars are never replaced. Buffer capture does not establish external speaker,
codec, or DAC output quality.

Tests use fake transports only and do not claim physical board results:

```sh
python3 -m unittest discover -s host/clients -p 'test_*.py' -v
```

## Known-fixture audio qualification

`qualify_audio.py` changes live controls and runs Panic/Resume on an identified
static sine or four-voice MIDI fixture. It never uploads or flashes. Use one
exclusive serial owner throughout; the `Qualification` class also accepts an
already owned `Transport` connection.

For a known fresh sine instance whose original actual values are frequency 440
and level 0.2:

```sh
python3 host/clients/qualify_audio.py --port /dev/cu.YOUR_DEVICE \
  --firmware-report build/firmware-amoled-rnbo/build-report.json \
  --prepared build/prepared/sine-v2 --fixture sine \
  --restore frequency=440 --restore level=0.2 \
  --out build/hardware/sine-qualification-NEW
```

The tool checks the device's ELF and module source identities against the build
report, resolves compact indices from its matching prepared parameter schema,
and waits for settled audio-owner telemetry before recording original volume and
Panic state. Its first control change is volume 25%. It captures 25/100/50/0%
output, actual and normalized frequency changes, Panic silence, and recovery.
The output directory contains each WAV and sidecar plus `qualification.json`.

The shell cannot read back live parameter values. Supply their exact known
original actual values with `--restore`; the tool restores them through
acknowledged setters and reports that verification limit. It also restores
original volume and Panic state. Oscillator phase and previous held MIDI notes
cannot be recovered. MIDI4 therefore requires `--idle-midi-baseline`, with known
original `level` and `poly/level` values, and adds note release and sustain tests.

The report checks PCM pitch, amplitude ratios, silence, and advertised fault
counters. It records current/lifetime peak render time as a percentage of the
256-frame period and raw stack telemetry. Those measurements do not establish
absence of every deadline miss, external listening quality, or display/touch
behavior.
