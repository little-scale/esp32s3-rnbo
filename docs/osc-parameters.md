# OSC and the lightweight board parameter page

17 November 2026. Implemented and computer-tested on the shared RNBO player.
**Hardware CPU/RAM, timing and multi-node qualification are pending.** This change
has not been installed on a board. See the [readiness record](../evidence/osc-web-readiness.json).

## Connect

Install a matching updated player, then use the existing Studio USB Wi-Fi setup
if the board is not already provisioned. Once its saved station connection is
online, the player exposes:

| Service | Destination | Purpose |
| --- | --- | --- |
| OSC | board IP, UDP **1234** | Parameter input |
| Parameter page | `http://<board-ip>/`, TCP **80** | Sliders, number inputs and enum choices |
| Studio transport | board IP, TCP **8789** | Existing authenticated package loading and controls |

Updated Studio shows **Open board parameter page** and the OSC destination when
it sees a capable player with a connected Wi-Fi address. Restart an older Studio
process and reload its page to use the new tools/UI. These services are independent;
a Studio TCP session can stay connected while OSC and the parameter page are used.

This is trusted-local-network HTTP/OSC control. OSC has no pairing-key field;
parameter access on 1234/80 is not authenticated with Studio's pairing key. Wi-Fi
credentials and pairing keys are never served. The existing authenticated upload
protocol is unchanged. Browser writes additionally require the page's per-start
control token, an IP-based Host header and the current patch generation; CORS is
not enabled. This is not a public-Internet or TLS service.

The listeners are started when provisioned Wi-Fi first starts, after the existing
boot health/maintenance gate. Scanning without configuring Wi-Fi does not start
them. Forgetting/disconnecting Wi-Fi prevents access and invalidates queued input;
the allocated service resources remain until reboot. No separate access point,
DNS service, mDNS hostname or OSCQuery discovery service is added. Use the board's
actual IP or a DHCP reservation, not an assumed `.local` name.

On a paired SynthDef/RNBO device, use the companion **paired updater** to update
RNBO and the existing paired tools to select it. These endpoints operate only
while RNBO is running; they do not switch runtimes, change native rate or alter
XMOS. Avoid factory/erase installation on a commissioned pair.

## Pi-compatible parameter addresses

An ordinary exported `param` needs no OSC object inside the patch. The namespace
uses its stable RNBO **parameter ID**, not its display name or numeric index.

| Address | Type | Meaning |
| --- | --- | --- |
| `/rnbo/inst/0/params/cutoff` | `f` | Actual value, e.g. hertz |
| `/rnbo/inst/0/params/cutoff/normalized` | `f` | Normalized position, 0–1 |
| `/rnbo/inst/0/params/mode` | `s` for an enum | Exact exported enum label |
| `/rnbo/inst/0/params/mode/normalized` | `f` | Normalized enum selection |

The numeric actual-value path also accepts `i` and `T`/`F`. Normalized paths
require `f`. Nonfinite values, unsupported tags/argument counts and unknown
parameters reject. Actual values clamp to their native range and normalized
values to 0–1. RNBO's own setters/conversion retain authored constraints,
exponents and steps; the network task does not reproduce that arithmetic.

Example destinations below are illustrative IPs:

```sh
oscsend osc.udp://192.168.0.101:1234 /rnbo/inst/0/params/cutoff f 1200.0
oscsend osc.udp://192.168.0.102:1234 /rnbo/inst/0/params/cutoff/normalized f 0.25
```

Every board has one Main patch at **local instance 0**. Target separate boards
with separate IP destinations; do not put a MAC/board ID into the canonical path.
The same address can therefore control different values on different nodes.

### Enum labels, visibility and aliases

New builds preserve optional enum/visibility/OSC metadata from the genuine export
description in a checked `remote_parameters` package field. It does not change
DSP code or the audio envelope version. Public scalar parameters with ordinary
IDs work in existing packages without recompilation. Older packages lack enum
labels/visibility overrides/aliases, so their fallback is numeric-only exposure;
rebuild them to retain those semantics. Hidden/debug parameters in the retained
schema are absent from the public interface and have null state placeholders.

Optional standard runner metadata supplies an input alias:

```text
@meta "{'osc':'/instrument/cutoff'}"
@meta "{'osc':{'addr':'/instrument/cutoff','norm':true}}"
```

The first accepts actual values; the second normalized values. This can coexist
with existing `esp32` physical-control metadata. The runner's direction rule is
retained: specifying `out:true` requires `in:true` to also receive. This receiver
does not implement outgoing OSC, even if outgoing metadata exists.

Bounds: 128 scalar parameters, IDs up to 191 UTF-8 bytes, one literal alias per
parameter up to 255 bytes, and at most 32 unique enum labels of 63 bytes each.
Enums require range 0..count-1 and matching steps. Aliases under `/rnbo` are
reserved. Address patterns/wildcards, spaces, trailing/double slashes and IDs
ending `/normalized` are unsupported. An ambiguous legacy ID schema disables
remote exposure while retaining ordinary patch playback; malformed explicit
remote metadata rejects a new package before activation.
Valid native enums exceeding the network label bounds are hidden from this
interface rather than preventing otherwise supported DSP from compiling.

## Parameter page and sender pacing

The self-contained HTML/CSS/JavaScript is gzip-compressed in flash and streamed
without loading the whole file into RAM. It draws each public parameter with a
normalized slider and an actual-value number field; enums also have a choice
menu. Number changes submit on commit, rather than on every keystroke. The page
shows each canonical OSC address as selectable text.
Its Pi-style light theme uses a white background, blue filled slider tracks and
ring handles, black labels and muted grey min/max values. A two-column layout
collapses to one column on narrow screens; styling and layout run in the browser.
The header shows only “RNBO parameter controls” and the IP/OSC port. Routine
live counters and explanatory footer text are omitted; connection, pause and
maintenance messages appear when needed.

The browser fetches metadata once per patch generation, polls small cached state
responses at **5 Hz**, and sends at most eight updates per **20 ms** request.
Continuous slider values coalesce **in the browser**; ordered number/choice edits
are kept in a bounded sender queue. Repeated accepted device events are not
coalesced. Only one write request is in flight. Polling and sends stop when the
tab is hidden. A generation change discards unsent old-patch values and reloads
controls. The UI is intended for one operator; the HTTP server allows at most
two simultaneous connections, not an arbitrary number of browser clients.

The implementation uses small HTTP GET/POST exchanges, not WebSockets or a full
OSCQuery frontend. The browser displays applied cached readbacks, including
changes from OSC, Studio, MIDI and physical inputs. Internally changed parameters
are refreshed on demand, up to eight readbacks per audio block while a browser
polls; a sweep of all 128 can take up to 256 ms at 16 kHz. This sweep ends when
complete and is not a continuous background timer.

For external OSC senders, start around **50 Hz per moving continuous control**
and **500 updates/second per node in total**. These are suggested sender settings,
not measured hardware limits. Faster/event-sensitive streams should be tested
with the actual patch. Sending a new filter coefficient can cost much more than
parsing the OSC packet itself.

## Bounded delivery and resources

- OSC datagrams: at most **1024 bytes**, one numeric/string argument per message.
- Browser writes: at most **2048 UTF-8 bytes** and eight updates per request.
  The sender splits larger batches; the receiver rejects JSON deeper than eight
  nested containers before parsing it.
- Immediate bundles only (timetag **1**), up to eight leaf messages and bounded
  nesting. The entire datagram is validated before one batch is queued. Scheduled
  timetags, empty/oversized bundles and unsupported types reject without applying
  an earlier valid element.
- Shared remote queue: **eight packets**, up to eight updates per packet. At most
  **eight updates total per audio block**; a bundle is not split across blocks.
  Queue overload drops/counts the incoming batch without invoking the general
  command queue's overflow-induced Pause. The UDP worker yields after eight
  datagrams during a flood. No per-parameter rate timers, smoothing or receiver
  coalescing are added.
- Accepted events retain order. Pause, maintenance, link loss and patch changes
  invalidate pending controls. Updates while paused/installing are refused; they
  never Resume or change master volume. The browser's queue ACK is not proof of
  applied state: state polling supplies the readback.
- Only the audio owner calls module setters/readbacks. Network workers access
  immutable metadata under a short mutex and the existing scalar value cache.
  No socket/JSON/heap operation is added to audio processing. The OSC decoder uses
  fixed buffers and makes no per-message heap allocation. HTTP JSON parsing and
  metadata responses have bounded temporary allocations outside the audio task.

The new tasks reserve **4 KiB OSC + 12 KiB HTTP stack**, plus an approximately
864-byte event queue, small bookkeeping and network/session buffers. These are
source-configured sizes, **not a measured total heap cost**. Metadata pointers
are reused rather than duplicating the complete parameter schema. Existing Wi-Fi
costs are shared. HTTP/control components optimize for code size; RNBO DSP/audio
performance settings are unchanged. Actual internal-RAM/PSRAM peaks, stack margin
and CPU still require device measurements, including initial page load/reconnect.

Current AMOLED application images are especially close to the experimental
paired app1 capacity; pairing tools must check the exact current image size.
Normal single-runtime installation has different capacity. No slot enlargement,
repartitioning or erosion of the paired installer's admission is performed here.

`player-info.remote_control` reports version, online/start flags, ports, packet,
accepted/delivered/discarded/rejected/dropped counters and the last socket/start
error. The page uses `/api/schema`, `/api/values` and `/api/parameter`; its schema
exposes IDs without expanding ordinary Studio status responses with all ID strings.

## Scope and remaining hardware checks

This is parameter reception and a small web controller, not the full Pi runner.
It adds no OSCQuery HTTP namespace, `rnbo.remote` discovery, feedback subscriptions,
MIDI/inport OSC routing, presets, JACK configuration, remote compilation or timed
cross-node synchronization. Updates use the existing 256-frame audio boundary:
about 5.80 ms at 44.1 kHz, 5.33 ms at 48 kHz, or 16 ms at 16 kHz, plus network/task
latency. Delayed UDP packets arriving after a patch change cannot carry a Pi-style
generation stamp; they resolve against the then-current patch. Already queued
old-generation events are discarded.

Computer checks exercise the actual C decoder/route validation and HTTP handlers,
queue/epoch admission, malformed packet corpus, genuine native RNBO stepped
parameter setters, page logic and Studio integration. Visual browser checking uses
simulated parameter data, not a live ESP32. Hardware qualification must measure
idle/enabled overhead, page-load RAM peaks, internal heap/stack margins, paced and
burst traffic, all supported rates, replacement/reconnect under traffic and two
independent nodes. Retain and restore the user's current paired runtime/program.

Upstream references: [runner guide](https://rnbo.cycling74.com/learn/rnbo-raspberry-pi-oscquery-runner),
[OSC specification](https://opensoundcontrol.stanford.edu/spec-1_0.html), and
[Instance.cpp at reviewed commit 1c3bb53449cccdc062b2f3ab581411f8c4e0ac43](https://github.com/Cycling74/rnbo.oscquery.runner/blob/1c3bb53449cccdc062b2f3ab581411f8c4e0ac43/src/Instance.cpp#L351)
(Git blob `340673252ebab9f0979f57827e12d6a6de9ac906`). The server uses ESP-IDF 5.5's
[HTTP component](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32s3/api-reference/protocols/esp_http_server.html).
