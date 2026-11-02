# Actual RNBO native-loader qualification

This separate ESP-IDF application qualifies real RNBO ELF modules without
modifying the working instrument firmware. It initializes neither I²S nor the
display/network, writes no module storage, and emits a single final
`RNBO_DYNAMIC_LOADER_TEST PASS ` line only after all assertions complete.
It waits two seconds for USB attachment before starting a test task on core 1.

Use the pinned ESP-IDF 5.5.0 / Xtensa GCC 14.2.0 installation and the locked
loader dependencies already staged by `tools/build_loader_spike.py`. Build the
known fixtures first:

```sh
python3 host/compiler/build_module.py --export build/prepared/sine-v2 --build-dir build/modules/sine
python3 host/compiler/build_module.py --export build/prepared/fx-pass-through-v2 --build-dir build/modules/fx
python3 host/compiler/build_module.py --export build/prepared/midi4 --build-dir build/modules/midi4
python3 tools/build_rnbo_loader_test.py --board amoled
```

The build helper performs no device access. The default artifacts are under
`build/rnbo-loader-test-amoled/`; its `build-report.json` uses the same
repository-relative `artifacts` mapping as the instrument builds. It records
the modules' build reports, prepared identities, compiler/dependencies,
resolved configuration, source hashes, and expected PASS prefix. A separate
XIAO build can be selected with `--board xiao`; that is not hardware evidence.
The ELF-loader source is unmodified and checked against
`loader-spike/dependencies.json`. Registry/libc/IDF/customer symbol tables and
shared-object lookup remain disabled. All three emitted modules must have
zero undefined imports; their required math/compiler support is linked
privately into each image.

The helper verifies the supplied module bytes against their adjacent compiler
reports, independently repeats ELF admission, and requires the static sine
reference to use the exact same prepared export as the dynamic sine. It checks
the source/module snapshots again after compilation. Do not substitute a
different prepared profile while keeping an older ELF or report.

## Tests performed on the target

- Hash all embedded ELFs and compare their recorded SHA-256 identities.
- Reject a truncated ELF; ensure common firmware/libc/C++ symbols are absent
  from the loader's lookup registry.
- Validate relocated constructor/finalizer arrays before requesting entry.
  Every function target must lie in that image's executable `.text` alias;
  array spans must fit their corresponding loaded sections.
- Require explicit handshake success because the pinned loader discards the
  entry function's C return value. Test wrong magic/version, short output
  structures, misaligned/undersized/oversized/wrapped state ranges, and a live
  rebind. Constructors must run exactly once across repeated entry requests.
- Admit the actual descriptor only after its complete declared span fits one
  loaded data section. Check ABI, role, channel/rate/vector contract, bounded
  state layout, supported flags, and every base/extension callback address.
- Bind shell-owned PSRAM state, create and prepare with four warm-up blocks
  and seed `0x12345678`. These fixture modules use a sufficient 1 MiB arena;
  a structural minimum is not a measured patch memory budget.
- Compare the dynamic sine against a statically linked copy using the same
  preparation and parameter events. Float absolute tolerance is zero; PCM
  tolerance is zero LSB after the stated 0.5 scale and symmetric int16
  conversion. This is a comparison of these fixtures, not a general math or
  object compatibility guarantee.
- Load two copies of the identical sine ELF simultaneously. Verify separate
  contexts, descriptors, function addresses, parameter/state progression and
  a fresh reference waveform. Reconstruct one already-bound image; unload it
  and keep processing the other. Retain copied parameter metadata safely.
- Feed distinct planar left/right buffers into a dynamic pass-through FX and
  check exact stereo routing. Check its bounded Panic output latch.
- Exercise the four-voice MIDI fixture on channel four, reject a wrong-channel
  release musically by checking sustained energy, then release all notes and
  require silence. The first run also projects the held chord against all four
  note frequencies and requires each amplitude to exceed 0.015.
- Observe module-local C++/RNBO/total arena allocation counters and use IDF heap
  hooks around event/process calls to detect an unexpected firmware-heap
  dependency. Late allocation, invalid samples and wrapper errors must remain
  zero. Module memory is reclaimed only after patch destruction, ELF
  finalization/unmapping, and then freeing its caller-owned state.
- After one complete warm-up round, repeat 32 full load/prepare/process/
  reconstruct/destroy/unload rounds. Require heap integrity, equal free PSRAM,
  and no loss of free internal RAM after every round.

## Evidence limits

A successful build is not execution evidence. A complete hardware PASS must
be tied to its firmware ELF and all module hashes. Retain the full boot log,
including the four MIDI spectrum measurements and final memory figures.
Test timing counters describe offline callback execution under this test's
workload; no I²S/display/network is active and no permanent-player deadline is
qualified by them. Buffer/arena allocation placement and actual initialization
usage are observed separately from the declared ceilings.

These checks improve admission and lifecycle correctness for trusted native
code. Section-range checks cannot prove that an arbitrary byte within `.text`
is a valid function entry, and an ELF is not memory isolated from its host.
The test deliberately uses known fixtures. A larger patch needs an explicitly
measured sufficient state budget; do not initialize an unknown delay-heavy
patch with this fixture's 1 MiB arena.

Root-owned hardware qualification must preserve the current instrument image,
confirm the board/partition identity, flash only the matching application
region, capture the complete test output and restore the exact instrument
image even when the test fails. The build helper never flashes or controls a
serial connection.
