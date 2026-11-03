# Authored GenExpr history fixtures

These original programs use RNBO 1.4.4's `gen~` GenExpr frontend. They are
separate from RNBO `codebox~` and from visual `.gendsp` import.

`history-feedback` implements `y[n] = x[n] + 0.5*y[n-1]`, initially zero. Its
second output observes the previous history value. `two-history-swap` uses
explicit old-state temporaries to exchange histories initially 1 and 2. This
avoids relying on the order of two imperative assignments. Both graphs expose
one `reset` parameter connected through `set reset` to the actual Gen reset
action. Repeated equal parameter values deliberately retrigger reset.

Run the licensed local frontend tests with:

```sh
node --test host/export/test_genexpr.mjs
```

The public export/prepare tests retain the module's fixed 256-frame profile.
The additional native test makes a separate, explicitly tagged producer export
with variable blocks. Its original C++ probe checks 1, 2, 7, 255, 256 and mixed
partitions, repeated prepare, reset at sample boundaries and fresh construction
against a closed-form convolution or exact alternating-state model. O3 and
UBSan captures must match bit for bit. That direct-producer test does not change
the module ABI, test a device, measure CPU cost, qualify all Gen operators or
prove external resource support. Generated code remains in temporary/ignored
output directories.

The additional `three-history-rotation` program rotates explicit old-state
temporaries initially 1, 2 and 3. Unlike the period-two swap, its phase can
change observably on a 256-frame reset boundary. The closed
[`target/catalog.json`](target/catalog.json) runs all three fixed-256 programs
against a dyadic stereo input and continuous/boundary/every-block reset cases.
Python and portable C independently produce the expected caches; the collector
also recomputes them using a fresh high-accuracy convolution or integer phase.
The first XIAO batch passes; see [the scoped results](../../../docs/gen-qualification.md).
Zero reset witnesses for the period-two swap do not qualify its reset action.

The [arithmetic corpus](arithmetic/catalog.json) adds fifteen separately authored
function/infix programs and a reproducible generator. Its exact source spellings
are individually exported, compiled, run natively and run on XIAO; equal lowered
code does not transfer qualification between source identities. See the
[scoped arithmetic results](../../../docs/gen-arithmetic-qualification.md).

Admission currently requires explicit GenExpr code. File/title forms, converted
`gencode`, embedded visual patchers, `exposeparams` and unknown Gen box options
are rejected. Zero saved signal inputs are allowed for autonomous code: Gen
still retains a base control inlet in its object metadata. Zero outputs are
not admitted by this observable-DSP route. Other declared ports must match
first-party metadata. Gen resource
declarations remain visible to normal prepared-module resource admission;
external `Buffer` resources are rejected there rather than silently discarded.
