# XIAO ESP32-S3 headless RNBO

The XIAO runs the same RNBO wrapper, audio owner, parameter handling, volume
ramp, Pause/Resume lifecycle and USB capture tools as the AMOLED build. Its
board profile supplies stereo I²S and excludes the display, touch and codec
components. The initial hardware check uses the same prepared `3sawsDrone3`
patch as the AMOLED instrument.

## Startup and build

XIAO builds default to **50% volume and automatic, unpaused playback**. No USB
start command, touch input or button is needed. `--initial-volume` overrides
the startup level; changing the live volume over USB does not change this
build-time reboot default. The AMOLED build's existing default is unchanged.

With ESP-IDF 5.5.0 and a validated prepared Main export:

```sh
python3 tools/build_firmware.py xiao \
  --export-dir build/object-optimisation/integrated-v1/prepared/drone \
  --variant drone3-headless50 --arena-bytes 131072
```

That export path identifies the local reviewed drone build; it is not supplied
in a fresh clone. Prepare your own export as described in the
[host guide](../host/README.md), and supply its path. The 128 KiB arena belongs
to this particular capped/Float32/table-omitted drone; other patches may need
a different budget.

The firmware statically embeds one patch. Live package replacement, Wi-Fi
deployment and physical parameter controls are separate remaining work.
Use the XIAO's own 8 MiB configuration and partition table. Back up existing
firmware/settings before installation; identify the device again after resets.
An AMOLED binary is not a XIAO firmware image.

## I²S wiring

These assignments match the existing SuperCollider XIAO setup:

| Signal | XIAO label | GPIO |
| --- | --- | ---: |
| BCLK | D8 | 7 |
| LRCLK / WS | D9 | 8 |
| Data out | D10 | 9 |
| Ground | GND | — |

Output is stereo, 44,100 Hz, signed 16-bit Philips I²S, without MCLK. DAC power
and analogue connections remain those required by the connected DAC.

## USB controls

The shared newline-delimited console uses 115200 baud. Commands include
`status`, `parameter-values`, `param INDEX VALUE`, `normalized INDEX VALUE`,
`volume 0..100`, `panic` and `resume`. The protocol still calls the Pause
operation `panic`; it mutes and reconstructs the patch before Resume.
`parameters` emits readable text, while `parameter-values` emits JSON.

The [capture client](../host/clients/README.md) downloads actual post-volume
stereo PCM from the successfully submitted I²S buffers. It shares the same
recording identity and chunk validation as the AMOLED client.

## Initial hardware validation

On the connected 8 MiB flash / 8 MiB PSRAM XIAO, the drone started at 50% before
any audio-control command. Both captured channels contained sound. A parameter
change/readback/restoration passed; Pause produced zero PCM; Resume restored
nonzero PCM. A watchdog reboot then restored automatic 50% playback and all
eight compiled parameter defaults, without a volume or Resume command.

Reported nonfinite, clipping, I²S write/DMA, queue and module errors remained
zero, with no late audio-owner allocations. The selected 128 KiB RNBO arena
used 99,088 bytes. This is initial whole-patch evidence, not qualification of
every individual object or a hard deadline guarantee.

See the [hardware evidence](../evidence/xiao-headless-drone3.json) for exact
firmware, patch and capture identities. The drone supplies identical left/right
signals in this test, so this does not establish independent-channel separation.
The user separately confirmed hearing the drone through the existing I²S DAC.
Electrical clock/data measurements and a cold power-cycle remain separate from
the USB-buffer checks and software reboot.
