# Initial RNBO runtime review

Reviewed against the installed RNBO 1.4.4 Minimal runtime and the generated
oscillator export. This records source and host checks; it does not qualify
hardware, dynamic loading or arbitrary patches.

## Static execution contract

The wrapper admits one generated image and one live context. The generated
class owns its existing `MinimalEngine`; the wrapper does not add another
engine. Creation and the one-shot preparation call happen while detached.
Every callback requires exclusive ownership. Destruction must follow audio
detachment, while the patch, runtime globals and arena still exist.

The initial contract is 44,100 Hz, exactly 256 frames, float32 planar stereo.
Main accepts no input channels; FX accepts two. Preparation validates the
actual generated channel counts, fixed profile and numeric parameter metadata.
Parameter IDs must be unique and fit the copied C ABI fields. The wrapper uses
RNBO's actual/normalized conversion functions; it does not infer a linear map.
Signal parameters, external messages and MIDI output are not admitted by this
static adapter. Input/output buffers must have disjoint 256-float storage.

Warm-up blocks advance the patch before shell sample position zero. The shell
tracks exact monotonic uint64 frame positions after preparation. Events are
declared to be delivered at block boundaries. RNBO scheduler time remains
double, but generated duration calculations may produce a float before double
conversion. Long-uptime sample-accurate timestamp delivery remains unqualified.

## Allocation and failure boundaries

`RNBO_USECUSTOMALLOCATOR` routes RNBO platform allocation into a bounded,
aligned arena. Reallocation by copy consumes more arena space; free is a
no-op until destruction. A late platform allocation faults the context and
the returned audio block is silenced. Arena exhaustion aborts because some
generated allocation callers dereference unchecked results.

The target wrapper does not override process-wide C++ new/delete. Generated
`new SampleBuffer`, RNBO String storage, logger templates and other raw C++
allocation routes therefore remain outside platform counters. Host contract
tests observe C++ new during tested owner callbacks; they do not cover all
libc allocation or target task behavior. Task-aware heap tracing and realistic
first-event/long-delay qualification remain necessary before a complete
no-late-allocation claim.

RNBO's logger and global random generator are translation-unit statics. The
wrapper preserves the previous logger and seeds the global generator with an
integer expansion of all 32 input seed bits. This does not provide multiple
independent instances. Per-object seed arguments can still control object
randomness according to the generated patch. Independent Main/FX images and
module-local symbol binding remain separate work.

Panic latches this context silent. The shell must also retain a prompt final
output mute path independent of normal event queue capacity. Resuming this
initial adapter requires detached destruction and reconstruction; old queued
events must not release the mute latch.

## Runtime fixes and evidence

The prepared runtime retains separately hashed, exact-pattern transformations
for inline/overflow list copying, list move ownership, cross-capacity list
assignment return types and nested clock dispatch. Original runtime headers
remain available in each prepared export's `originals` directory. An unknown
upstream source layout must fail preparation rather than receive a broad
replacement.

`tests/native/runtime_test.cpp` tests list capacities 0, 4, 16 and 32 at lengths
0, 15, 16, 17 and 32; copy and assignment independence; moved-from reuse;
variadic initialization around the inline boundary; and actual MinimalEngine
clock target dispatch, value delivery, target-specific cancellation and root
fallback. These are host primitive tests, not a broad RNBO compatibility sweep.

The C ABI is an in-memory development interface, not a serialized package or
proof of an ELF loader contract. An independently qualified Xtensa loader,
constructor/finalizer lifecycle, constrained import set and repeated two-image
load/unload tests are still required before uploadable modules are claimed.
