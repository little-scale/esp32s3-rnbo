# AMOLED patch-area touch → RNBO parameters

Put inline `@meta` on ordinary RNBO `param` objects, then export using Max's
[C++ Minimal Export](native-export.md) or [rnbo.studio](../host/max/README.md).
Install the current AMOLED player once using Studio's firmware dropdown.
Changing these bindings afterwards requires only a new patch package.

```text
param touch_x 0.5 @min 0 @max 1 @meta "{'esp32':{'type':'touchscreen','axis':'x'}}"
param touch_y 0.5 @min 0 @max 1 @meta "{'esp32':{'type':'touchscreen','axis':'y'}}"
param touched 0 @min 0 @max 1 @meta "{'esp32':{'type':'touchscreen','axis':'pressed'}}"
```

The outer double quotes and inner single quotes are intentional RNBO JSON5
metadata syntax. These are project-specific bindings, separate from GPIO
capacitive `type:'touch'`. `displayname` remains a human-readable label.

## Exactly which area responds

Only the **patch drawing rectangle** on the AMOLED Main/Patch page responds:
**336 × 232 pixels**, at screen **x = 16…351, y = 64…295**. The header, CPU line,
output meter, volume slider, Pause/Resume and Params buttons do not supply touch
coordinates or gates. The Params page's multisliders retain their existing use.
The fallback parameter-list drawing occupies the same patch rectangle.

A gesture must begin inside this rectangle. Dragging into it from a button or
slider does not start a gesture. Leaving the rectangle releases the gate and
holds the last X/Y values; moving back in while still held does not restart it.
Lift and press again. Release, lost contact or switching to Params releases the
gate. The contact remains captured until lift, so dragging out of the drawing
will not start operating another control.

When any touchscreen binding is present, touching patch objects controls this
surface instead of jumping to their parameter sliders. Use **Params** for those
sliders. Patches without touchscreen metadata keep the previous tap-to-select
behaviour. This version exposes one contact's X/Y and pressed state; it does not
provide pressure, gestures or separate multi-finger coordinates.

## Values, options and timing

| Binding | Normalized input |
| --- | --- |
| `axis:'x'` | Left = 0; right = 1 |
| `axis:'y'` | Top = 0; bottom = 1 |
| `axis:'pressed'` | Released = 0; touched = 1 |

RNBO's normalized parameter conversion applies `@min`, `@max`, `@exponent` and
steps. For example, X can directly control a frequency range:

```text
param frequency 440 @min 80 @max 1200 @meta "{'esp32':{'type':'touchscreen','axis':'x'}}"
```

Optional `invert:true` reverses an axis or the gate. To make Y increase upward:

```text
param level 0.1 @min 0 @max 0.2 @meta "{'esp32':{'type':'touchscreen','axis':'y','invert':true}}"
```

Optional `deadband` defaults to `0.002`, accepts 0…0.1, and suppresses small X/Y
changes. Exact endpoints still publish. Set `deadband:0` to report every changed
pixel. A stationary finger does not continually reassert values. Each new press
publishes coordinates before the pressed gate; release leaves X/Y untouched.
Several parameters may use the same axis, with at most 16 bindings per package.
Unknown options, invalid axes and duplicate destination IDs fail validation.

Updates follow the display's input events and enter the bounded,
generation-checked parameter queue; RNBO receives them at an audio-block boundary.
The audio callback performs no touch-driver access or allocation. Coordinate
math and filtering use Float32. This is control-rate input, not a sample-accurate
or Gen single-sample timing source. Use smoothing in RNBO when appropriate.

Pause and maintenance invalidate held gestures, including transitions occurring
between GUI updates. The neutral gate is sent again when parameter delivery
resumes; use a fresh press to play. Failed parameter publications are not marked
as delivered. Queue overload retains the player's existing pause/fault behaviour.

## Board and package compatibility

Bindings produce `touchscreen_inputs` v1 metadata, restricted to board `amoled`
and area `patch`, and require **package envelope v3**. Ordinary packages keep v1;
XIAO GPIO-bound packages keep v2. Older players reject v3 rather than silently
ignoring its bindings. Studio checks `touchscreen_inputs_version:1` and the
AMOLED board before transferring over either USB or Wi-Fi.

XIAO rejects touchscreen packages. A package cannot mix XIAO physical-pin
bindings and AMOLED screen bindings. Optional `.rnbopat` drawing data cannot
assign these bindings; they come from the native export's parameter metadata.

## Example and checks

Open [amoled-touchscreen.maxpat](../host/max/amoled-touchscreen.maxpat): X controls
sine frequency, upward Y controls level, and pressed gates the output. The
example is also included in the downloadable Max helper package. Build/upload
from the surrounding Max patch with `rnbo.studio` as usual.

Tests exercise real C metadata/gesture code with cJSON and undefined-behaviour
sanitizers, package downgrade/mixing rejection, old-player upload prevention and
native Max export/build. Both player firmware profiles compile. Physical finger
interaction, screen coordinate orientation and DAC/listening
confirmation on the AMOLED remain pending; computer tests do not establish those.
