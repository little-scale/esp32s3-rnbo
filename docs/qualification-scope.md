# Qualification scope

The active hardware goal covers RNBO objects, operations and structures on the
XIAO ESP32-S3, with recorded compatibility, numerical results, resource use and
performance. The user's explicit addition on 4 November 2026 also requires
**Gen / `gen~`, its DSP operators and its single-sample processing semantics**.
The goal is incomplete until both areas have explicit test outcomes.

The existing 1,455-row inventory describes RNBO spellings, RNBO codebox members
and related editor/serialization entries. It is not a Gen inventory. Gen DSP
operators and GenExpr/codebox constructs need separate exact identities and
their own source, export, native execution and XIAO evidence. An identically
named RNBO operator does not qualify a Gen operator.

The primary integration route is an original `gen~` patch embedded in RNBO and
exported through the pinned local RNBO toolchain. Cycling '74 documents this
route in its [RNBO overview](https://docs.cycling74.com/userguide/rnbo/).
Acceptance by the exporter is only the first gate; it does not establish
correctness, timing or precision on the ESP32-S3. Standalone Gen exports, if
used as a reference or a separate execution route, must remain distinguishable.

Single-sample qualification must include:

- One-sample `history` delay, specified initial values and reset/reconstruction.
- Causal recursive feedback against an independent recurrence, including an
  impulse crossing every host block boundary.
- Multiple histories whose old values are read before the current sample's
  state updates; chains, fanout and feedback graphs with observable order.
- Gen patcher and GenExpr/codebox forms, with separate source identities.
- Equivalent output for the same continuous input split into one-sample,
  short, odd and ordinary audio-block calls, where the route supports them.
- Sample-accurate control changes, parameter changes and scheduling boundaries.
- Stateful resources, delays, interpolation and memory limits, plus nonfinite,
  denormal and precision policies with their declared test domains.
- Processing cost, memory and allocation observations on XIAO, keeping kernel
  execution separate from host block, I²S and interface overhead.

The [Gen overview](https://docs.cycling74.com/userguide/gen/_gen_overview/) and
[`history` reference](https://docs.cycling74.com/reference/gen_dsp_history/)
describe per-sample operation and one-sample feedback. Running a patch inside
a 256-frame host callback is compatible with an inner per-sample loop, but is
not proof that the loop, feedback or sample-level ordering is correct. Likewise,
a host ABI that admits only 256-frame calls must not claim a one-frame call
test. Such a test needs an admitted kernel route or an extended, verified ABI.

Each inventoried name/form needs an actual outcome: verified in a declared
scope, failed with retained evidence, or explicitly unsupported by a tested
route. Untested cases remain untested. Export/compile failures are recorded
separately from numerical failures and missing host/resource adapters.
Gen's non-audio Jitter contexts are separate from the requested `gen~` DSP
scope. No arbitrary user program or unbounded feedback domain is established
by a finite fixture corpus.

The [XIAO results](xiao-qualification.md) retain the current RNBO measurements.
Gen inventory and execution qualification are pending; no RNBO result is
transferred to Gen by association.
