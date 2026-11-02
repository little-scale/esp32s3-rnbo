# Second-wave original object probes

These six MIT-licensed flat graphs add23 host workloads beyond the first15
Main/FX object fixtures. Generated RNBO source remains under ignored `build/`.
No device, firmware or production-preparer changes are part of this collection.

| Fixture | Independent checks |
| --- | --- |
| line-timing | Millisecond slope/endpoints, immediate target observer, zero-time transition, interruption and changed-duration restart at block boundaries |
| average-window | Mathematical rolling mean via a fresh `math.fsum` window; warmed versus reset history; fixed zero output lag; cancellation-heavy signals |
| biquad-response | Published difference equation, impulse response, identity coefficients, stable slow pole and DC gain |
| phase-pulse | Signed phasor rate, zero frequency, sample-based train period and duty extremes |
| noise-colour | Explicit white seed, variance/DC/correlation, independent windowed spectral colour probes, reconstruction/seed observations |
| nonlinear-domains | Hyperbolic tangent, wrap/clip boundaries and positive-domain fractional/integer powers |

```sh
python3 host/compiler/qualify_wave2.py \
  --out build/object-qualification/WAVE2-NEW
```

The runner requires a fresh directory and matching Release compiler/integration
identities. It seals its source, catalog, original patch, custom C ABI probe,
prepared provenance, library/executable identities and float/PCM outputs.
`probe.cpp` supports explicitly scheduled block-boundary parameter events and
bounded disjoint stereo input files. Reported process times are host observations.

The final initial run is `build/object-qualification/wave2-final/report.json`.
It intentionally returns nonzero and reports `passed:false`: the strict
averager exceeds the unchanged2e-6 mathematical-accuracy limit on long
cancellation signals, and native `pink~` ignores the create seed in favor of
`systemticks()`. Other listed semantic checks pass. These findings are retained,
not converted into green results by widening tolerances or changing the SDK.
All six optional audio-v2 routes are explicitly unadmitted by the existing
catalog; that is a precision-profile limitation, not a generic object ban.

Average history policy is grounded in the private generated
`average_tilde_{01,02}_{init,doReset,setwindowsize,perform,dspsetup}` methods.
Their hashes and exact source lines are in `source_audit`. Warmup supplies zeros
to the unchanged default16-sample window. A changed valid window resets its
available count; output then averages only available samples until filled.
The current input enters accumulation before output, so expected causal lag is
exactly zero. Tests reject wrong reset policy, window size and a one-sample shift.

Noise source hashes/lines show that explicit white seeding and pink clock
seeding are different routes. Native repeated-pink differences do not establish
the behavior of the module's private clock. Dynamic/target investigation is
separate. A changed context seed is confounded with changed native clock ticks
and must not be presented as causal control of the pink stream.
