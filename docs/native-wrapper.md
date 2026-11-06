# Native-export wrapper and retained components

Max now owns graph interpretation, RNBO/Gen semantics, code generation and
polyphony. Our wrapper owns integration with the device. Changing the frontend
alone does not require replacing the player or its package format.

| Component | Decision | Remaining work |
| --- | --- | --- |
| RNBO/Gen `.rnbopat` importer and custom visual lowerer | Retired to `archive/importer` | Historical reproduction only |
| Native export intake | Folder/ZIP → validated Minimal C++ | Qualify more Max-export forms and runtime versions |
| Module ABI, zero-import ELF and package format | Retained | Keep source/runtime/wrapper identities with results |
| Player and saved Main patch | Retained | No firmware reflash required for intake migration |
| I²S, PCM conversion, finite checks, headroom and volume ramp | Retained | Continue separate end-to-end audio checks |
| AMOLED drawing, multisliders, meter and Pause/Resume | Retained | Optional matching drawing attachment; DSP comes from C++ |
| USB, Wi-Fi pairing/uploads and live controls | Retained | Existing identity and admission checks still apply |
| Parameter IDs/ranges/metadata and physical inputs | Native Max inline `@meta` → package checked | Physical wiring and scan behaviour remain pending |
| UART MIDI / experimental USB host | Native Max monitor passes software/UART internal loopback | External MIDI/controller and USB-host tests remain pending |
| Native/XIAO harnesses and independent oracles | Retained | Add native-export provenance; do not inherit importer coverage |
| Importer-era numerical optimisation profiles | Research-only | Requalify against Max exports before making supported profiles |

## Wrapper baseline

The production module wrapper (`module-sdk/dynamic/rnbo_s3_dynamic.cpp`) and
the static/native-test wrapper (`module-sdk/wrapper/rnbo_s3_static.cpp`) both
remain unchanged in this migration. Their baseline defines `RNBO_USE_FLOAT32`, `RNBO_NOSTL`, `RNBO_NOTHROW`,
`RNBO_NO_PATCHERFACTORY`, `RNBO_FIXEDLISTSIZE 16`, and custom allocation/print hooks.
Audio samples are binary32; scheduler time remains binary64. The player renders
44,100 Hz / 256-frame blocks, applying controls and MIDI through the existing
`TimeNow` interface. Single-sample Gen state executes inside those blocks;
this does not establish within-block sample-offset delivery of host controls.

Each module uses a bounded arena. Startup runs constructor/initialisation and
preparation before render-time allocation checks begin. Exhaustion can abort;
late allocations and runtime errors reject qualification. A startup screen
cannot exercise every later parameter list, clock sequence or delay resize.
The package loader also checks actual module descriptors and startup timing;
a passing computer build is not an ESP32 deadline guarantee.

The preparer retains existing narrowly recorded runtime compatibility fixes and
integer-wrap handling. Raw/prepared hashes and adaptations identify changes;
`float32-strict` does not mean byte-unmodified generated/runtime code.
No new numerical rewrite or scheduler change is made in this migration.

## Next wrapper qualification priorities

1. **Lists and allocation.** The compound `curve~` event-13 fault is a 32-byte
   overflow-list allocation from its active-ramp list after exceeding the wrapper's
   16 inline elements. A private 32-element experiment completes this exact test
   within its original tolerance, at increased context size. Establish bounds
   for bursts and longer lists before selecting production reservation policy.
2. **Clock and ramp semantics.** The callback-13 fault belongs to event-rate
   `line`, not signal-rate `line~`. Float32 rounding of its next clock time can
   place an endpoint before its exact end; it then repeatedly schedules that same
   instant until the queue overflows. A private binary64 clock-local experiment
   completes the run, while the independent timeline reference still disagrees.
   Preserve and qualify those timing differences before adopting a fix. Existing
   `edge~`/report timing differences also remain. See the
   [ramp diagnosis](native-ramp-diagnosis.md).
3. **Native end-to-end baselines.** Qualify representative Main instruments,
   MIDI, parameter ranges, long-running ramps, delay/resource use and actual
   sample-by-sample Gen feedback at the fixed audio profile.
4. **Optimisation after parity.** Profile real target callbacks first. Keep
   numerical differences, correctness results and CPU savings separate. Native
   export alone showed no speed improvement in the three matched CPU contexts.

The historical object inventory remains useful as a test plan and source of
oracles. It is not a claim that every Max export or entire object family works.
The wider testing goal remains paused while this migration is completed.
