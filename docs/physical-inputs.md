# Physical inputs → RNBO parameters

Physical inputs v1 let a **XIAO ESP32-S3 player package** carry its own knob,
button and capacitive-touch mappings. Put `@meta` directly in the `param` object
text. No extra RNBO objects or firmware rebuild are needed when changing a
mapping after the updated player has been installed.

**Status: implemented; computer tests and firmware builds are recorded below.
Physical wiring, ADC response, touch electrodes and on-device CPU costs still
need hardware qualification.** The separate object-qualification goal remains
paused. This feature does not claim hardware validation from simulated readings.

## Copyable object text

Paste these as ordinary RNBO `param` objects:

```text
param note 39 @min 0 @max 60 @displayname Note @meta "{'esp32':{'type':'analog','pin':'A0'}}"

param gate 0 @min 0 @max 1 @displayname Gate @meta "{'esp32':{'type':'digital','pin':'D6'}}"

param accent 0.25 @min 0.25 @max 1 @displayname Accent @meta "{'esp32':{'type':'touch','pin':'D3'}}"
```

The outer double quotes and inner single quotes are intentional. This JSON5
form is accepted by the pinned RNBO 1.4.4 generator and keeps the mapping visible
inside the object. The importer preserves the editable patch file. An inspector
metadata object works too, but is not required. `displayname` remains the label
shown to the user; it does not assign a pin.

The `esp32` metadata key is this project's convention. Other metadata is left
alone. Misspelled options under `esp32`, invalid pin names and conflicting
bindings fail compilation rather than silently disappearing.

## Exactly how XIAO pin names map

**A0 and D0 are two names for the same pad: GPIO1. Neither means GPIO0.**
Numbering refers to the standard XIAO ESP32-S3 shown in the
[Seeed pin reference](https://wiki.seeedstudio.com/xiao_esp32s3_pin_multiplexing/).

| XIAO pad label | Analog label | ESP32-S3 GPIO | Touch channel | Use in this input profile |
|---|---|---:|---:|---|
| D0 | A0 | 1 | 1 | Analog, digital or touch |
| D1 | A1 | 2 | 2 | Analog, digital or touch |
| D2 | A2 | 3 | 3 | **Reserved:** GPIO3 boot strapping; rejected by this profile |
| D3 | A3 | 4 | 4 | Analog, digital or touch |
| D4 | A4 | 5 | 5 | Analog, digital or touch; also the board's SDA alias |
| D5 | A5 | 6 | 6 | Analog, digital or touch; also the board's SCL alias |
| D6 / TX | — | 43 | — | Digital; available while the player uses native USB |
| D7 / RX | — | 44 | — | Digital; available while the player uses native USB |
| D8 / SCK | A8 | 7 | 7 | **Reserved:** current I²S DAC bit clock (BCLK) |
| D9 / MISO | A9 | 8 | 8 | **Reserved:** current I²S DAC word select (WS/LRCLK) |
| D10 / MOSI | A10 | 9 | 9 | **Reserved:** current I²S DAC data output (DOUT) |

Use `A0`, `D0` or `GPIO1` to identify the first pad. These resolve to the same
GPIO, and may not be assigned to separate parameters at once. Use `D3` or
`GPIO4` for touch on the D3 pad; **do not use `TOUCH3` to mean D3**. Touch channel
3 belongs to GPIO3/D2, which this profile reserves.

There is no `A6`/`A7` input alias in this profile: D6 and D7 are not ADC pins.
Only the exposed pads in the table are accepted. USB GPIO19/20, flash/PSRAM,
the activity LED, BOOT GPIO0 and arbitrary internal GPIOs cannot be claimed.
GPIO7–9 remain reserved by the v1 profile even in a custom audio-pin build;
the firmware also checks any additionally configured I²S pins.

Each pad has **one input mode and one destination parameter** in v1. For example,
binding A0 as analog and D0 as digital is a conflict. D4/D5 must not also be wired
to an external I²C bus while used as these inputs.

### AMOLED board

The existing AMOLED player still supports ordinary packages. It explicitly
rejects packages containing these **XIAO-specific** bindings. The AMOLED's
display, audio, SD and touch wiring consumes different GPIOs; a separate,
verified external-input pin profile is needed before enabling inputs there.
The AMOLED touchscreen is not the capacitive GPIO `touch` mode described here.

## Analog: raw ADC → normalized value → parameter range

The player reads 12-bit ADC1 values with 12 dB attenuation. The default mapping is:

```text
normalized = clamp((raw - raw_min) / (raw_max - raw_min), 0, 1)
```

For the Note example, after any smoothing settles:

| ADC reading | Normalized value | Note parameter |
|---:|---:|---:|
| 0 | 0 | 0 |
| approximately 2048 | approximately 0.5 | approximately 30 |
| 4095 | 1 | 60 |

The player sends normalized events through RNBO's conversion path, so `@min`,
`@max`, `@exponent` and parameter steps retain their RNBO meaning. This is a
linear note range in the example; it is fractional unless quantized in RNBO.

**ADC counts are not a guarantee of a linear 0–3.3 V measurement.** ESP32-S3 ADC
accuracy and saturation depend on attenuation and the particular chip. For a
true external 0–3.3 V sweep, use a suitable divider to keep the ADC voltage within
its useful range, then measure the endpoints and set `raw_min`/`raw_max`.
Software endpoint calibration cannot recover a saturated signal. See
[Espressif's ADC range guidance](https://docs.espressif.com/projects/esp-faq/en/latest/software-framework/peripherals/adc.html).
Do not connect 5 V or negative voltages directly to these pads; external input
circuits must share the board's ground.

All analog options are optional:

| Option | Default | Meaning |
|---|---:|---|
| `raw_min` | `0` | Raw count mapped to normalized 0; integer 0–4094 |
| `raw_max` | `4095` | Raw count mapped to normalized 1; integer 1–4095, above `raw_min` |
| `smooth_ms` | `10` | Float32 one-pole control smoothing time constant; 0 disables, maximum 1000 |
| `deadband` | `0.002` | Minimum change from last sent normalized value; 0–0.1 |
| `invert` | `false` | Reverse the normalized direction |

Example with measured endpoints:

```text
param note 39 @min 0 @max 60 @meta "{'esp32':{'type':'analog','pin':'A0','raw_min':80,'raw_max':3900,'smooth_ms':10}}"
```

Those endpoints are illustrative, not calibration data for your board. Exact
0/1 endpoints are sent after the smoothing settles even when the deadband would
otherwise hide the last small change. Unconnected analog inputs float: leave
them unbound until wired, or expect their readings to move unpredictably.

## Digital buttons and switches

The default is **internal pull-up, active low**. A normally open button between
the selected pad and GND gives released → normalized 0 and pressed → normalized 1.
The destination parameter therefore receives its minimum and maximum. A high
level with `active_low:false` gives normalized 1 instead.

| Option | Default | Meaning |
|---|---|---|
| `pull` | `'up'` | Internal `'up'`, `'down'` or `'none'` |
| `active_low` | `true` | Low voltage means active; set false for active high |
| `debounce_ms` | `8` | Candidate level must stay unchanged for this long; integer 0–1000 |
| `invert` | `false` | Reverse the resulting normalized value |

These are level/gate inputs. Toggle, edge-trigger and encoder modes are not
implemented. Use RNBO logic to derive those behaviours if needed. A `pull:'none'`
input needs an external circuit that defines both logic levels.

## Capacitive touch

Touch uses an electrode connected to a permitted touch pad. It is a capacitive
sensor, not an analog voltage input. After a package loads, keep the electrode
untouched while the first **64 nonzero scans** establish its baseline, roughly
256 ms at the nominal scan rate. It publishes no touch value until calibration
and debounce finish. Invalid/zero readings do not count toward calibration.

| Option | Default | Meaning |
|---|---:|---|
| `threshold` | `0.08` | Touch begins above an 8% increase over the baseline; allowed 0.001–1 |
| `hysteresis` | `0.02` | Release threshold is `threshold - hysteresis`; must be smaller than threshold |
| `debounce_ms` | `12` | Stable touch/release time; integer 0–1000 |
| `invert` | `false` | Reverse touch/release normalized values |

With defaults, activation is above baseline ×1.08 and release at or below ×1.06.
The baseline tracks slowly while untouched and is held during a detected touch.
Electrode size, wiring and environment will need hardware tuning later. This
version produces a 0/1 gate, not a pressure or continuous-capacitance parameter.
Reload the package to recalibrate if its startup baseline was taken while held.

## Player behaviour and Studio

- The updated player must be installed **once over USB**. Studio refuses to send
  an input-bound package to an older player that cannot interpret the bindings.
  Input-bound packages use **package envelope v2** (same binary layout and module
  ABI, required input support); old players reject the envelope even outside
  Studio. Ordinary packages retain envelope v1. The input metadata schema itself
  is version 1.
- Compilation carries stable parameter IDs and the checked bindings in the
  `.rnbopkg`. Changing parameter order does not retarget a pin to the wrong param.
- Studio's package result lists the mappings. Live controls additionally show
  each pin/GPIO, raw reading, normalized value, readiness and read-error count.
- Input drivers are configured only for bound pads. A package without bindings
  releases previous inputs. Package replacement resets pending input values,
  filtering, debounce and touch calibration.
- Scans run on the control owner, nominally every **4 ms / 250 Hz**, outside the
  audio callback. USB/Wi-Fi work can delay scans; this is not a hard timing or
  audio-rate CV guarantee. Latest values are coalesced per parameter, then consumed
  at a 256-frame audio boundary (about 5.8 ms at 44.1 kHz). They never fill the
  command event queue. Driver/JSON allocation stays outside the audio owner.
- The authored parameter default lasts until the first valid conditioned input
  value. While paused, the latest physical value is retained and applied on
  resume. A stationary control does not continuously override Studio; it takes
  control again when its conditioned value changes. There is no soft pickup.
- A failed read holds the last parameter value and increments its read-error
  count. Driver startup failure disables the input reader and appears in Studio;
  the audio patch can still run. Repeated errors need investigation on hardware.
- Status contains `physical_inputs_version:1` and `main.physical_inputs`, including
  scan time and peak scan time for later CPU measurements. Runtime conditioning
  uses Float32; JSON validation uses cJSON's normal number representation.

The mappings apply to package-based players. Static embedded-patch shells do
not implement this input frontend.

## Verification and the later hardware session

Computer checks cover the real RNBO inline metadata export, host binding/package
admission, stable-ID lookup, alias conflicts, runtime pin reservations, analog
endpoints/inversion/smoothing/deadband, button bounce and held-touch state.
Native C conditioning tests use the same source compiled into the firmware, with
undefined-behaviour checks. The XIAO and AMOLED player firmware builds pass.
Recorded checks: 514 compiler tests, 91 Studio tests, 23 frontend tests, 14 RNBO
export/GenExpr tests, one native conditioning test and six native package/store
tests. Six focused package tests also pass after adding the v2 envelope guard.
The example exports and compiles into a zero-import Xtensa module and an
uninstalled, initially silent package. Build identities and scope are recorded
in [the evidence manifest](../evidence/physical-inputs-v1.json).

Later hardware checks still need to establish:

1. Knob endpoint readings and useful voltage range on A0; sweep, noise and latency.
2. Button release/press/bounce on D6 with the default pull-up and polarity.
3. Touch baseline, threshold, hysteresis and long holds on D3 with a real electrode.
4. Pause/resume, package replacement and input-resource recovery on the board.
5. Scan costs and audio CPU/deadline counters with USB and Wi-Fi active.

No hardware compatibility or performance percentage is inferred from computer
tests. The standalone example is [physical-inputs.rnbopat](../examples/physical-inputs.rnbopat).
