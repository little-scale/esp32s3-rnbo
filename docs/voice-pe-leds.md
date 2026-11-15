# Patch-controlled Voice PE LED ring

Use **`outport led_rgb` inside RNBO**, then export a genuine C++ Minimal Export
at the matching native Voice PE rate. The connected test unit uses 16 kHz.
The player needs `led_output_version:1`; LED packages use envelope v5 and a
sized ABI 1.1 extension. Ordinary packages keep their original ABI 1.0 prefix.

## Message formats

| List | Operation | Example |
| --- | --- | --- |
| `r g b` | Set all twelve LEDs | `1. 0. 0.` makes the ring red |
| `index r g b` | Set one LED, retaining all others | `3 0. 1. 0.` makes LED 3 green |
| 36 numbers | Replace the frame, twelve RGB triplets | Triplet 0 is LED 0, triplet 11 is LED 11 |

Connect an RNBO message box containing the list to `[outport led_rgb]`. Send a
bang to the box from `loadbang` for an initial colour, or drive the list from
authored control events. The list contains numbers only; do not put the symbol
`led_rgb` inside it. `@meta` is not required on this port. The existing `@meta`
bindings for dial/button/microphone-mute remain inputs.

RGB uses Float32 values in 0–1. Finite values outside that range clamp. An index
must be integer-valued in 0–11. Invalid indices, fractional indices, nonfinite
components, bangs, numbers and lists of other lengths reject the entire message
without changing previous colours. Messages apply in arrival order. An indexed
update starts from the last latched frame, initially black.

Indices are logical: the retained mapping uses physical LED `(index+7)%12` and
converts RGB to the wire's GRB order. The existing 20% brightness cap applies.

## Example

Open [voice-pe-led.maxpat](../host/max/voice-pe-led.maxpat), choose the explicit
native 16 kHz profile, build and upload. Its audio output is silent. Studio's `test`
parameter selects:

| Value | Message/result |
| --- | --- |
| 0 | Shared red |
| 1 | LED 3 green; others retained |
| 2 | LED 11 blue; others retained |
| 3 | Full 36-value blue frame at 0.5 |
| 4 | Invalid index 12; rejected |
| 5 | Fractional index 3.5; rejected |
| 6 | Two values; rejected |
| 7 | `-1 0.5 2`; clamps to `0 0.5 1` |
| 8 | Shared black |
| 9 | Shared blue |

In Max, `profile voice-pe-16000-256-v1` sets the actual export rate. The usual
`build`, `upload usb` and `upload wifi <board_id>` messages remain valid. Restart
an already running Studio after updating these tools so it can parse v5.

## Ownership, timing and diagnostics

The audio owner collects the module-owned frame into a bounded mailbox. The
control owner refreshes RMT. No GPIO/RMT wait, JSON or filesystem operation runs
in the output callback, and the adapter makes no per-message allocations.
RNBO's fixed inline list capacity is 36 only for LED exports; its reviewed
variadic-constructor bounds fix is recorded in build provenance.

At most 32 matching messages apply per audio block. Excess messages count as
dropped. Publication is limited to one frame per 20 ms and hardware refresh to
at most 40 Hz; intermediate frames coalesce. A 25–50 ms animation interval is
suitable. These are control-rate messages, not sample-accurate lighting events.

An LED patch owns the ring during playback. Pause clears its visible LEDs;
Resume restores its latched frame. Audio failure overrides with red. Replacement
discards the old generation's frame. Ordinary packages retain the board's
dial/status ring. Healthy audio blocks renew a heartbeat even when colour is
static; a frame older than 200 ms goes dark.

`player-info` includes `led_output_version` and `led_output`: driver health,
ownership, generation, freshness, sequence, accepted/rejected/dropped counts and
the effective 36 normalized RGB values. These are software readbacks, not optical
measurements. See the [LED hardware receipt](../evidence/voice-pe-led-output.json).
Native 48 kHz electrical tests, power interruption and long-duration stress remain
separate qualification items.

## Repeated package replacement

Replacement testing exposed intermittent SPIFFS staging failures with the default
garbage-collection limit. The player now reserves space before writing the inactive
package and allows up to 256 collection passes. Collection reclaims obsolete pages;
it does not erase the filesystem or delete live files from other firmware. If space
cannot be reserved, loading fails while retaining the active patch and saved selector.
