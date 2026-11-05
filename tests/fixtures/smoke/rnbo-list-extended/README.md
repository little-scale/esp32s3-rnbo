# Extended numeric lists and storage

Original armed RNBO fixtures: 32 scenarios, 17 exact patcher spellings. Export
with the installed RNBO compiler, prepare as stereo FX, and run the strict
hardware-smoke harness. All 22 actions resolve parameter IDs rather than fixed
ABI indices. No startup drive reaches the object before arming.

`reference.py` models bounded integer lists and ordered storage independently.
It never evaluates generated DSP. List codes preserve all digits and length for
up to five values in 0..7. Emission-code sums are explicitly weaker: they check
content totals/suppression, not a lossless arbitrary sequence encoding. Integer
sums stay below 2^24; no tolerance is allowed. The raw right input is checked
separately across all 20 output blocks.

Partitions 1 and 2 contain 14 complete output checks each. Partitions 3..6 retain
one original growth scenario apiece: push three and pop one on each drive. These
are isolated because native preflight finds allocation faults at the eighth
drive. Four additional push-three/pop-three controls exercise bounded FIFO/LIFO
operation. They do not replace the growth sources or qualify larger storage.

`initial-28-v1` preserves the first catalog/reference/generator and two original
partitions before adding the four controls and isolating the growth probes.
Its 28 patch paths resolve in this parent folder; all original graph hashes,
expected output streams and zero limits are unchanged. The historical generator
is for inspection, not execution from its archive directory.

Primary installed XML/help receipts are in each catalog row. The `list.union`
policy intentionally retains a documented ambiguity: the help describes omitting
right items already in the left, while XML also describes broader duplicate
removal. The original reference preserves left duplicates. Its measured native
and target differences remain visible, without substituting captured output.

Generate/check current sources:

    python3 tests/fixtures/smoke/rnbo-list-extended/generate.py --check

Public results and limits: [report](../../../../docs/rnbo-list-extended.md).
