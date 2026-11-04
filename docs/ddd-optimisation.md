# DDD Float32 experiment

The recorded DDD patch exceeded the XIAO player's audio budget with its strict,
byte-identical DSP baseline. A short target screen measured **10,056 µs** against
a **5,805 µs** block period and rejected it. The opt-in `float32-audio-v3` profile
with Float32 delay storage subsequently ran this complete patch at observed
render times of **1,933–2,013 µs** (about **33–35%** of the block period), with a
**2,252 µs** observed peak. Several minutes of radio-off operation recorded no DSP
faults. These are whole-patch observations, without per-object cost attribution
or a hard worst-case timing guarantee.

The [sanitized experiment record](../evidence/ddd-optimisation.json) identifies the
source, packages, native comparison and target observations. This is separate
from the older [3sawsDrone3 static qualification](drone3-qualification.md).
The original editable source and Desktop file were unchanged. The user can load
another patch at any time; this document does not assert that DDD is currently
installed, or that Wi-Fi joining has passed.

## Changes and numerical scope

For this graph, the v3 pass reviews **15 method bodies** and makes **32 decimal
literal suffix changes**. This includes the two signal `mtof~` expressions taking
the Float32 `expf` path and Float32 coefficient arithmetic/`cosf` in `lores~`.
State declarations, method signatures, integer phase/truncation algorithms,
scheduler time and ring algorithms remain unchanged by the arithmetic pass.
It deliberately changes expression rounding and phase increments; it is not an
IEEE-bit-identity profile or a conversion of every operation to Float32.

The native default-settings comparison captured 2,048 blocks after four warmup
blocks: **11.89 seconds**, 44,100 Hz, 256 frames per block and seed `0x12345678`.
Both variants completed without invalid samples or late Platform allocations.
Over the full capture, v3 versus strict had:

| Observation | Difference |
| --- | ---: |
| Maximum absolute Float32 sample error | 0.0008099675 |
| Error RMS | 0.0001008578 |
| Maximum int16 PCM difference | 13 LSB |

The predeclared diagnostic limits of **2e-6 maximum sample error and 1 PCM LSB
failed** and remain recorded as failures. Even the first 64 blocks exceeded the
sample-error limit. The small RMS level-change check passed; it does not erase
the pointwise differences. PCM comparison used **100% conversion volume with
fixed 0.5 headroom**; both captures included clipping. This policy is distinct
from the package's 50% startup volume. There is no universal error or audibility
claim, and no qualification of every input or control mode.

## Automatic Studio default

`float32-auto-v1` applies the same v3 transformations independently to each
reviewed method. Unknown methods retain their original bytes and are listed in
the audit; a patch with no reviewed methods remains unchanged. Timing, setup and
scheduler code are outside this pass. Existing explicit profiles keep their
original admission behavior. For DDD, automatic output is byte-identical to v3.
Float32 delay storage remains a separate optional setting.

The user's AAA variant compiled with the automatic default: 13 reviewed methods
were transformed and two unreviewed scalar multipliers were retained. USB loading
then replaced DDD successfully; the observed render time was 2,315 µs with a
2,513 µs peak and zero reported DSP errors. Its earlier strict package had been
rejected at 9,965 µs. These are whole-patch observations, not per-object benchmarks
or a numerical-error bound for AAA. Studio distinguishes the running Main from
the compiled package and retains CPU-admission failures beside the Load button.

## Separate storage choice

Enabling Float32 delay storage saves **65,536 bytes** of observed native arena
use, from **458,920 to 393,384 bytes**. Its complete Float32 capture and WAV were
byte-identical to the v3 arithmetic variant retaining Float64 rings for this
same workload. The 1 MiB arena reservation is capacity; these figures describe
measured usage. This observed storage identity is separate from the failed
strict-versus-v3 numerical gates and does not establish identity for all workloads.

## Reproducing the recorded settings

In [RNBO Studio](../host/studio/README.md), select **Float32 audio · pitch and
filters (experimental)** and **Use Float32 delay storage** explicitly. Leave the
delay cap empty for this DDD workload; its authored delay is in samples. Keep a
sufficient arena reserve. Studio now defaults to **Automatic Float32**, while the
compiler CLI still defaults to strict arithmetic. A successful
short startup screen is an admission check, not a proof of all-mode accuracy or
real-time performance.

Local reports retained under ignored build storage are:

```text
build/private/ddd-optimisation-v1/native-review-v3/report.json
build/private/ddd-optimisation-v1/native-review-v3/review.json
build/private/ddd-optimisation-v1/native-review-v3/storage32/report.json
build/private/ddd-optimisation-v1/module-v3-delays/build-report.json
build/private/ddd-optimisation-v1/target-loaded.json
build/private/ddd-optimisation-v1/target-running.json
```

Native host timing is not used as a target speed result. The target measurements
include the running patch and owner work through PCM conversion, excluding I²S
wait; they are not total dual-core CPU usage. Networking was inactive for the
reported DDD observations. A player update preserves the latest selected package;
it does not imply that package is this recorded DDD version.
