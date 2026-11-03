# SPDX-License-Identifier: MIT
"""Independent mathematical truth for the closed original wave4 corpus.

Inputs are already binary32 wires in [-1,1]. Addition/subtraction of two
binary32 values is evaluated in binary64 then rounded once to binary32; this
retains enough precision for their final binary32 result. Min/max/comparisons
are mathematical value operations. Operation signed-zero bits are diagnostics,
not an undocumented tie/sign rule; the untouched right-plane observer in the
delta fixture must preserve all input bits. No generated DSP source is inspected.
"""
from __future__ import annotations
import math
import struct

KINDS = {"absolute", "minimum", "maximum", "subtract", "equal", "less",
         "sum-and-difference", "delta-left-observer-right"}


def f32(value):
    if type(value) not in (int, float):
        raise ValueError("Expected a finite numerical value")
    try:
        if not math.isfinite(value):
            raise ValueError("Expected a finite numerical value")
        result = struct.unpack("<f", struct.pack("<f", value))[0]
    except (OverflowError, struct.error) as exc:
        raise ValueError("Value is outside finite binary32") from exc
    if not math.isfinite(result):
        raise ValueError("Value is outside finite binary32")
    return result


def _wire(value):
    if type(value) is not float or not math.isfinite(value) or not -1.0 <= value <= 1.0 or f32(value) != value:
        raise ValueError("Input must be an actual finite binary32 wire in [-1,1]")
    return value


def expected_outputs(kind, left, right, *, previous=0.0):
    """Return mathematical binary32 outputs and final previous-input state.

    A caller can split the same input program into vectors and carry only the
    returned previous input. Reconstructing a fresh instance uses previous=0.
    Both independent planes are validated completely before any calculation.
    """
    if type(kind) is not str or kind not in KINDS:
        raise ValueError("Unknown wave4 mathematical model")
    if type(left) not in (list, tuple) or type(right) not in (list, tuple) or len(left) != len(right) or not 1 <= len(left) <= 1048576:
        raise ValueError("Expected two nonempty, equally sized bounded planes")
    a = tuple(_wire(x) for x in left)
    b = tuple(_wire(x) for x in right)
    previous = _wire(previous)
    if kind == "absolute":
        return (tuple(abs(x) for x in a), tuple(abs(x) for x in b)), previous
    if kind in {"minimum", "maximum", "subtract", "equal", "less"}:
        def op(x, y):
            if kind == "minimum": return min(x, y)
            if kind == "maximum": return max(x, y)
            if kind == "subtract": return f32(x - y)
            if kind == "equal": return float(x == y)
            return float(x < y)
        return (tuple(op(x, y) for x, y in zip(a, b)), tuple(op(y, x) for x, y in zip(a, b))), previous
    if kind == "sum-and-difference":
        return (tuple(f32(x + y) for x, y in zip(a, b)), tuple(f32(x - y) for x, y in zip(a, b))), previous
    output = []
    for x in a:
        output.append(f32(x - previous))
        previous = x
    return (tuple(output), b), previous


def analyse(kind, inputs, actual, *, previous=0.0):
    if type(inputs) not in (list, tuple) or len(inputs) != 2 or type(actual) not in (list, tuple) or len(actual) != 2:
        raise ValueError("Two input and output planes are required")
    expected, state = expected_outputs(kind, inputs[0], inputs[1], previous=previous)
    if any(type(p) not in (list, tuple) or len(p) != len(expected[0]) for p in actual):
        raise ValueError("Output frame counts differ")
    maximum = 0.0
    zero_sign = 0
    bits_changed = 0
    observer_bit_errors = 0
    observer_required = kind == "delta-left-observer-right"
    for channel, (want_plane, got_plane) in enumerate(zip(expected, actual)):
        for want, got in zip(want_plane, got_plane):
            if type(got) is not float or not math.isfinite(got) or f32(got) != got:
                raise ValueError("Output is not finite binary32")
            maximum = max(maximum, abs(want - got))
            changed = struct.pack("<f", want) != struct.pack("<f", got)
            bits_changed += changed
            zero_sign += changed and want == got == 0.0
            observer_bit_errors += changed and observer_required and channel == 1
    return {"accuracy_pass": maximum == 0.0 and observer_bit_errors == 0, "maximum_absolute_error": maximum,
            "maximum_absolute_error_limit": 0.0, "words": len(expected[0]) * 2,
            "model_output_bit_differences": bits_changed, "zero_sign_differences": zero_sign,
            "zero_sign_is_diagnostic_for_operation_outputs": True,
            "direct_observer_bit_exact_required": observer_required,
            "direct_observer_bit_errors": observer_bit_errors,
            "final_previous_input": state}
