# dbtoa Float32 comparison

This original signal patch has two independent `dbtoa~` instances, one per
channel. It compares the strict implementation with the explicit, changed
rounding `float32-dbtoa-v1` profile. The compiler admits only its reviewed graph,
runtime and source maps. Other spellings and codebox or Gen forms are separate.

The independent mathematical reference is `10^(dB/20)`. Inputs are finite
binary32 values from −24 to +6 dB; every output must be finite and within the
predeclared Float32(2e-6) absolute limit. The mathematical result is evaluated at
high precision and rounded directly to nearest/even binary32. Agreement at 80
and 120 decimal digits is a stability check, not an exhaustive transcendental
rounding proof. The vectors and expected caches were frozen before candidate
execution. They contain no generated DSP.

The four 256-frame stereo vectors cover the existing musical grid, endpoint and
subnormal neighbors around zero, all 481 sixteenth-dB points, and input neighbors
around 64 independently derived output-rounding boundaries. There are 705
distinct input words. The checked-in caches are little-endian interleaved
binary32; `reference.py` independently recomputes their expected values.

Each vector runs three rounds in A-B-B-A order: A is strict, B is the explicit
profile. All 48 rows bind the same original patch. Both variants use a matched
1 MiB arena ceiling, zero automatic SDK warm callbacks, four checked manual warm
callbacks and sixteen checked timed callbacks. Costs describe the complete
stereo callback, with no isolated per-object timing claim. Memory, lifecycle and
finalization gates remain required. Hardware execution belongs to the separate
root-run benchmark, not fixture creation.

Bit identity is not a gate: earlier host observations already showed one-ULP
changes at −24 and +6 dB. Max/RMS error, changed words and ULP distances should
remain visible in numerical reports. The output range is approximately
0.0631–1.9953, so fixed 0.5 PCM gain has headroom; this does not establish PCM
identity for arbitrary inputs. NaNs, infinities, floating exceptions, errno,
alternate rounding modes and dB values outside this domain are unqualified.
