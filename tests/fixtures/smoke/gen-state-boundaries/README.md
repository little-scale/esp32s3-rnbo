# Gen state and callback boundaries

Eight original GenExpr programs cover four previously unauthored state operators
and two explicit `Delay` declaration/method scenarios. Each is a separate flat
RNBO `gen~` FX graph with two declared signal inputs and outputs, no parameters
and no external resources requested by the source. Parser and preparation
failures are retained; a source is never replaced after its outcome.

The references start at fresh initialization, use no automatic preparation
warmup and check four manual warmups followed by sixteen timed callbacks. The
same 256-frame input vector repeats while state carries across all twenty
calls. This tests state inside the fixed-256 production ABI; it does not expose
a one-frame or variable-block host API.

| Program | Predeclared reference |
| --- | --- |
| Free phasors | Phase steps 3/1024 and 5/2048 at 44.1 kHz; capture initial phase 0 before advancing. Neither period divides 256. |
| Reset phasors | Initial/reset phases 0.125/0.375, reset-before-capture with late/early vector reset samples. |
| Odd-period trains | Periods 7/11 samples, width 0.5, onset 0; ordinal 0 is captured first. |
| Train widths and onset | Same periods, onset 0.25, signal widths from 0/0.25/0.5/0.75/1; circular phase window. |
| Rate | Sync off; increasing phase ramps of 64/32 samples, time multipliers 8 and 16; unwrap, divide by the multiplier and wrap. Both output periods are 512 samples, with exact dyadic phase and state carried across the 256-frame boundary. |
| Multiplicative accumulation | Initial/reset value 1; exact bounded dyadic factor cycles and reciprocal factors, post-accumulation reset then capture. |
| Integer delay | Two declared maximum-16-sample `Delay` instances, taps 1/3, no interpolation, read before write; fresh storage is zero. |
| Feedback delay | Tap 3 and feedback 0.5 with a copied right input; fresh independent input convolution with 64 terms. |

Initial capture/reset ordering is a declared comparison policy where primary
prose is less precise. A mismatch stays visible rather than moving the reference
to fit a generated implementation. The multiplier uses a nonzero initializer,
so it cannot pass trivially by multiplying an initial zero forever. Delay method
results do not qualify similarly named standalone `read` or `write` operators.

Gen's primary registry explicitly calls the train period input “period
(samples)”; RNBO patcher `train~` units are not inherited. Its rate description
says multipliers below one create several ramps per input phase cycle, so the
reference divides by the time multiplier. An initial multiply-based reference
was archived and corrected from that primary text before any DSP execution.
The rate-only source multipliers were then changed from 1/8 and 3/16 to 8 and
16, also before any DSP execution, to make the intended slower/cross-callback
phase test exactly dyadic. Prior source/reference checkpoints are preserved;
the other seven programs, all input vectors and numeric limits are unchanged.

All references use zero numeric tolerance except the feedback convolution's
predeclared 2e-6. Its omitted tail is at most 2^-65 for the selected bounded
inputs. Words are rounded once for output comparison; operation zero signs are
diagnostic. The right feedback pilot uses that same numeric comparison, with
no additional raw-bit observer claim. Internal storage, actual arena use and
callback cost require separate module/hardware observations. No universal
phase/reset policy, arbitrary resource size or optimisation gain is claimed.

`generate.py --check` checks authored sources/catalog against the installed
primary registry. Portable tests run with
`python3 -m unittest tools.test_smoke_gen_state_boundaries_reference`.
