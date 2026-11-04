# Additional RNBO event smoke fixtures

These 40 original MIT-authored flat patches exercise exact event-object spellings individually. They extend `rnbo-events`; signal variants, codebox forms and aliases do not inherit results.

Every patch has one actual-value parameter `drive` (default 0, range −8…8), connected to the object's hot inlet 0. Outlet 0 feeds `sig~` and the left audio output. Input 2 feeds the right output directly; input 1 is declared unused. Binary operands are 2, except logical OR's operand 0. For `intnum`/`int`/`i` and `f`/`float`/`constant`, literal 2 initializes a numeric store; hot numeric events overwrite it. No bang, cold-inlet update or autonomous-constant behavior is inferred.

`reference.py` defines independent mathematical expectations for 20 callbacks: four manual warm callbacks and sixteen timed callbacks, with zero automatic preparation warm blocks. Its 21 ordered actual-value events include repeated values, held callbacks and multiple commands before a callback. Each result is held for all 256 frames. The right pilot is compared word-for-word, including signed zeros and subnormals. Left operation zero signs are diagnostic; the numerical error limit is exactly zero.

Reverse division and modulo use nonzero event values. Denormal checks include signed minimum subnormals, the largest positive subnormal and the minimum positive normal. NaN-related objects receive only finite values, so this batch makes no NaN-handling claim. Integer stores truncate toward zero. `step` is independently defined as not(first < second), following its RNBO reference. No expectation is fitted to exported DSP.

`catalog.json` records exact spellings, literal operands, primary-reference fingerprints and model IDs 171–195. `test_reference.py` tests the reference contract; the tools-suite discovery wrapper is `tools/test_smoke_rnbo_events_extra_reference.py`.

The producer and fast-module results are under ignored `build/research/rnbo-events-extra-smoke-v1` and `build/hardware/rnbo-events-extra-smoke-modules-v1`. All 40 exports, preparations and Xtensa module links succeeded with zero imports. The 4 KiB arena setting is a structural ceiling, not measured use. Build time is not DSP performance. Hardware execution and compatibility/performance publication are separate steps. Generated RNBO C++ is not included in these sources.

The [XIAO run](../../../../evidence/xiao-smoke-rnbo-events-extra.json) completed all 40 cases: 35 pass and five retain output mismatches (`isdenorm`, `fixdenorm`, `rmod`, `!%`, `step`). All 840 actual-value updates/readbacks pass. No CPU-review flag or allocation failure occurs; the zero-error limit remains unchanged. See the [hardware record](../../../../docs/hardware-smoke.md) for measured timings and mismatch scope.
