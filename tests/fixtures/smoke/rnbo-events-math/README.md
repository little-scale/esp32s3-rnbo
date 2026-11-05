# RNBO event maths: finite-domain functional screens

This original 44-source catalog tests exact event-rate spellings, including
trigonometric/hyperbolic functions, logs, exponentials, powers, windows, unit
conversions and four conversion-constant spellings. Each source has one real
`param drive`, fixed cold arguments where needed, a held left `sig~` output and
an independent raw right audio lane. The unused first audio input preserves
the admitted stereo FX interface. No audio-profile adaptation is requested:
these use the existing strict Float32 samples and Double scheduling profile.

The independent `reference.py` defines each mathematical operation, input
domain and absolute limit before execution. Inputs are rounded to binary32;
Python double maths is rounded once to binary32 at the expected output.
Ordinary limits are 2e-6; degrees uses 2e-5 and power/radians-to-degrees constants
8e-6. Named approximations use a separately declared **1e-3 absolute screen**,
which is a test policy, not a promised RNBO accuracy specification. Differences
are retained without changing limits to fit observed results.

Each fresh image uses zero automatic warmup, four manual warm callbacks and
sixteen timed callbacks. There are 21 ordered actual-value parameter events,
including repeated values, holds and multiple updates before one callback.
All calls have 256 frames at 44.1 kHz. `atan2`/`hypot` have fixed second operand
2; `pow`/`fastpow` have fixed exponent 2.5. Positive-domain inputs are in [1,5],
inverse-trig/atanh/log1p/tangent inputs in [-0.5,0.5], and window phases in [0,1].
`cosT8` reaches ±3; `cosT8safe` also tests ±8 and ±3. Other inputs are in [-2,2].
The source catalog records each exact domain. Constants output the conversion
constant, rather than multiplying the drive; all have a nonzero first event.
No invalid-domain, arbitrary cold-inlet, reset, list, within-block timestamp or
full-object qualification is implied.

The catalog, both 22-source partitions and reference are hash-pinned. Every
source graph has a bound fingerprint. The collector independently reconstructs
all 20 expected blocks and the ordered controls; altered references, limits,
source spellings, domains or incomplete ledgers reject. The right observer has
an additional **20,480-byte SHA256 capture**, covering all 5,120 raw right-lane
words in each scenario. Its hash must match independently reconstructed words,
including zeros, subnormals and finite extremes. The mathematical tolerance
cannot hide a changed right word. Capture/hash work is outside process timing.

All 44 programs compile and run on XIAO. **41 pass**, while `fastexp`, `fastpow`
and `fasttan` retain outside-screen differences. Both native and target runs
show these three differences; neither an ESP-specific defect nor a universal
claim that these intentional approximations are broken follows. All target
images finalise and the allocation/memory gates pass after observer setup.
An initial setup filename collision and an initial failed memory gate are
retained separately in the [attempt ledger](../../../../evidence/rnbo-events-math-attempts.json).
The first large observer hash consumes 288 internal bytes before the measured
baseline; later logging/hashing costs no additional internal bytes in either
completed partition. No memory gate was relaxed. This identifies the observer
cost for this harness; it does not resolve another experiment's heap changes.

Run `generate.py --check` to reproduce sources using the local licensed primary
reference metadata. Tests verify mathematical landmarks, domains, case-fold-safe
IDs, frozen admission, stream/control mutations and bit-level right-pilot faults.
Generated RNBO implementation sources and private builds remain under `build/`.
The [qualification report](../../../../docs/rnbo-event-math.md) links all evidence.
