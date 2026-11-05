# Delay resources and explicit members

Thirty-three original RNBO codebox programs cover thirteen exact member IDs:
seven delay members and next/clear/reset on comb and allpass. Twenty-two execute
on XIAO; eleven original string-enum read-call programs reject in C++.
The numeric-enum programs are separate authored sources. No constructor, alias,
other syntax or Gen status is inherited.

The official [delay](https://rnbo.cycling74.com/codebox/ref/delay),
[comb](https://rnbo.cycling74.com/codebox/ref/comb) and
[allpass](https://rnbo.cycling74.com/codebox/ref/allpass) references describe
their methods. Installed RNBO 1.4.4 `BufferInterp` metadata enumerates Linear,
Cubic, Spline, Cosine, Step, None, Fastcubic and Spline6 as integer values 0–7.
The metadata source hash is saved in the native evidence. String arguments
reach generated C++ unchanged and are rejected at the integer interpolation
parameter. Rejections inside the write/step scenarios occur at their
accompanying read call, not at the write/step primitive.

## Predeclared source and reference policy

All programs use one resource on the left and a bounded right-input pilot.
Delay explicitly requests maxdelay 16 samples; comb/allpass keep their default
storage. The test reserves a 2 MiB arena ceiling to admit default buffers;
that reservation is not a claim that every program consumes that much state.

Programs observe integer next/read, overwrite-before-step, double physical
steps, size, scheduled clear/reset and all eight interpolation enums. Linear
and cosine read at 2.5 samples; four/six-point modes read at 4.25 samples with
asymmetric signal history. Step/none declare floor selection. A separate next
case supplies a fractional size. Manual order is read-before-write-before-step;
the overwrite case writes twice to the same cell and observes the final write.
Double step advances two cells for each input sample.

References use direct delayed sample age and mathematical comb/allpass
recurrences. Fractional models use Lagrange, full-neighbor-slope Hermite,
half-slope Catmull-Rom and centered quintic B-spline definitions. Their knots
are centered around the physical read coordinate. Where method prose is terse,
this physical alignment, floor selection and size 16 are declared screening
policies. They are not fitted to exported algorithms or target observations.

Clear/reset occurs at index modulo 257 equal to 37 or 38, plus absolute indices
255/256. Default history is declared zero after clearing. Twenty continuous
256-frame callbacks at 44.1 kHz include four checked manual warmups and sixteen
timed calls, with zero automatic warmups. The unchanged strict module profile
uses zero tolerance for integer operations and the original predeclared 2e-6
bound for fractional kernels/feedback recurrences. Numerical mismatches,
within-tolerance differences and signed-zero differences stay separate.

The native harness is derived from the existing stream observer. Only its
creation arena changes from 4096 to 2097152 bytes; a source-body equivalence test
protects the process loop and output comparison. No native timing is used as
target performance.

## XIAO results, 5 November 2026

**22 programs execute: 17 pass and five retain output mismatches**, across
**225,280 output checks**. The eleven string-enum sources remain C++ rejections
with source/log hashes and no device timings. Native/target input/reference
hashes, aggregate difference counts and maximum errors agree; this does not
prove bit-for-bit equality of the full native/target output streams.

There are 25,591 numerical mismatches, 4,858 within-tolerance word differences
and zero signed-zero differences. All 17 passing programs have zero numerical
mismatches. No input, reference or tolerance changes after output observation.

Passing cases cover integer next/read, write overwrite, double step, size 16,
clear/reset, comb/allpass recurrences, and fractional linear/cosine plus
step/none reads. The five retained mismatches are:

- Fractional `delay.next`: generated next accepts an integer size, so 2.5 is
  converted before read. Explicit linear/cosine read accepts a number size and
  passes the half-sample reference. The public next table describes size as
  number, so the distinction remains documented rather than silently rounded
  in the reference.
- Cubic, fastcubic, spline and spline6 reads: generated sample windows start
  at the floor of the read coordinate, while the reference centers its knots
  around that coordinate. Delay/window alignment remains follow-up. These
  failures do not establish failure of the separately checked scalar kernels.

Observed arena high-water is 192 bytes for the bounded delay and 1,048,704 bytes
for default comb/allpass. All 22 images finalise, free internal/PSRAM totals
return unchanged and no late-allocation/process fault occurs. The quiet test
application remains installed.

## CPU follow-up

Nine scenarios trigger the median-cost rule, bringing the queue from 101 to 110
contexts. No separate peak-spike flag triggers. Complete callback medians range
47–44,189 µs, with maximum observed peak 44,194 µs. Default comb/allpass clear/reset
scenarios take roughly 44 ms per callback, about 7.6 times the 5.805 ms audio period.
Their repeated sample schedules typically clear the roughly 1 MiB buffer state
twice per block. These offline checks have no I²S deadline claim.

Review default buffer capacities and clear/reset scheduling before attributing
this cost to next alone. These timings use unchanged strict storage, without
an Auto Float32 profile or matched optimisation comparison. Baseline comb/allpass next, cosine, cubic and spline
read also enter the queue. Reset/clear scenario times include the loop schedule
and buffer work; no isolated method cost or optimisation gain is claimed.

The thirteen member entries bring the RNBO dashboard to 778 scoped mappings,
including partial outcomes and rejected forms. Other capacities/taps, arbitrary
parameter domains, resource sharing, helper return values, host reconstruction,
other rates/vector sizes and full mode/alignment semantics remain pending.

Evidence: [hardware results](../../../../evidence/xiao-smoke-rnbo-codebox-delay-members.json)
and [native diagnostics plus rejection/metadata details](../../../../evidence/rnbo-codebox-delay-members-native.json).

```sh
python3 tests/fixtures/smoke/rnbo-codebox-delay-members/generate.py --check
python3 -m unittest discover -s tools -p test_smoke_rnbo_codebox_delay_members_reference.py
```
