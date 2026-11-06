# Native loader qualification fixture

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

The standalone `loader-spike/` project builds a small Xtensa C++ module and a
separate ESP32-S3 test firmware. It does not replace the RNBO audio firmware,
initialize a display/network, write module storage or produce audio. The
primary board profile is Waveshare ESP32-S3 Touch AMOLED 1.8 V2 with 16 MiB
flash and 8 MiB octal PSRAM. The optional XIAO profile selects 8 MiB flash.

## Reproduce the build

Use ESP-IDF 5.5 and its selected Xtensa GCC 14.2.0 toolchain. Obtain the loader
component from `esp-iot-solution` commit
`d2d935d0ee3e78deffa3981cc8c39ac8f534932b` and cmake_utilities 0.5.3. The helper
checks every dependency file against `loader-spike/dependencies.json`, then
copies verified sources into ignored `build/vendor-loader-spike`. It does not
modify the supplied source directories. Component Manager remains disabled;
there is no network dependency resolution during compilation.

```sh
python3 tools/build_loader_spike.py \
  --loader-dir /path/to/esp-iot-solution/components/elf_loader \
  --cmake-utilities-dir /path/to/espressif__cmake_utilities \
  --board amoled --host-tests
```

The optional upstream host suite also needs the same repository's
`examples/elf_loader/elf_loader_example/main/test_{xtensa,riscv}.elf` and
`examples/elf_loader/elf_console_example/main/fs_image` fixtures. A component-only
download can build the spike without `--host-tests`. Host test output remains
in `build/loader-spike-module/*host-tests.log`.

Outputs are the positive and unknown-import modules under
`build/loader-spike-module{,-bad-import}/rnbo_loader_fixture.app.elf`, their
unstripped `.debug` companions, and the test firmware under
`build/loader-spike-amoled`. `build-report.json` records source/dependency,
compiler, profile and artifact identities. The helper never flashes a board.

## What the fixture checks

The module uses upstream `project_elf()` flags and the loader's actual entry
request mechanism. Its own versioned C handshake copies a function table into
shell-owned storage. It imports only `rnbo_spike_host_marker`; integer and float
host callbacks and a PSRAM state array arrive through the handshake. Private
module-local C++ finalizer bookkeeping derives from the pinned upstream
Apache-2.0 lifecycle fixture. C++ exception/RTTI support is disabled.

The firmware is written to verify all of these on a board:

- Early constructor ordering, global construction exactly once across repeated
  entry requests, and C++ finalization during unload.
- Initialized data, BSS state, constants, internal virtual dispatch and returned
  function pointers after relocation.
- Two simultaneously loaded copies of identical bytes with identical internal
  symbol names and independent globals, callbacks and state.
- Shell-owned float input/output buffers and explicitly allocated PSRAM state.
- Continued processing of the second copy after the first is detached/unloaded.
- Thirty-two repeated two-image load/process/detach/unload cycles, heap integrity,
  unchanged free PSRAM and no loss of free internal RAM after one warm-up cycle.
- Truncated container rejection and rejection of the separate image requiring
  `rnbo_spike_unapproved_import`; absent `printf` and `esp_restart` exports.

Success prints a single `rnbo_loader_spike: PASS cycles=32 ...` line. A failed
assertion reports its source line and aborts. The test does not call pointers
after their image is unloaded. The initialized global, constant-array address
and non-inlined virtual call are deliberately retained in the compiled image,
so the compiler cannot replace those tests with scalar constants.

## Locked source and integration details

| Dependency | Version | Files | SHA-256 of ordered path/content inventory |
| --- | --- | ---: | --- |
| Espressif ELF loader | 2.0.0, pinned commit above | 81 | `62d0bc75890842f243f7835a49279cb951daaca61768116d370b5040226f5910` |
| Espressif cmake_utilities | 0.5.3 | 36 | `4debf79f417db7c25083c3a4d565183b7b4b5e98ca207e958ed7da76551d6ee6` |

The loader source remains unmodified. The isolated firmware's CMake explicitly
adds its private lwIP dependency because the pinned `esp_elf_symbol.c` includes
`sys/socket.h` even when default symbol exports are disabled. This satisfies
IDF's component include rules; the firmware does not initialize networking.

Resolved configuration must enable PSRAM loading and ESP32-S3 cache-offset
mapping, and disable libc, ESP-IDF, customer and shared-object export paths.
One explicitly registered symbol table contains one named import. A narrow
import set is a compatibility contract, not isolation from native memory bugs.

The pinned `esp_elf_request()` ignores its entry function's integer return value
and returns success after dispatch. Consequently, `request == 0` is insufficient
for module admission. The fixture checks the copied handshake fields after
each request; a production RNBO loader needs an explicit handshake result and
must validate every returned descriptor/callback before activation.

## Evidence boundaries

The pinned upstream host suite passed all 34 tests with the installed Xtensa
tools, including real multi-import relocation handling. Four additional host
tests compile the actual loader validator and apply it to this spike's emitted
ELF: valid admission, structurally valid unresolved imports, truncated input,
wrong architecture and misaligned input. These do not execute Xtensa code.

Artifact inspection checks the emitted Xtensa architecture, entry-bearing
ET_DYN form, exact imports, supported relocation kinds, allocated state/constant
sections and relocated constructor/finalizer arrays. It remains distinct from
on-device relocation, cache coherency, execution and timing evidence.

## Recorded AMOLED V2 execution

On 2 November 2026, the fixture passed on the connected Waveshare AMOLED 1.8 V2
(ESP32-S3 revision 0.2, 16 MiB flash, 8 MiB PSRAM). The complete log records:

```text
PASS cycles=32 modules_per_cycle=2 ctor_once=1 finalizers=1 callbacks=integer,float globals_isolated=1 psram_before=8386192 psram_after=8386192 internal_before=329547 internal_after=329547
```

Malformed ELF and unapproved-import rejection messages were observed before the
positive runs. A two-second startup delay was added to let USB reconnect before
test evidence is printed; the loader/module algorithms were unchanged. The test
firmware was replaced with the identified instrument application afterward.
Logs and artifact identities are in `build/hardware/amoled-first/`.

This closes the physical gate for this small fixture. Dynamic RNBO modules,
real audio deadlines during ELF execution, independent Main/FX image lifecycles
and live flash maintenance remain unqualified.

For a later run, preserve known-good firmware/settings, confirm its exact model
and flash size, build the corresponding profile and capture the complete boot
log. Existing app/data partition offsets are retained, but flashing and any
partition changes need a deliberate recovery procedure. Only a recorded PASS
with firmware/module hashes can close this fixture's physical gate. RNBO
loading, audio deadlines, Main/FX replacement and live flash maintenance remain
later, independent qualification steps.
