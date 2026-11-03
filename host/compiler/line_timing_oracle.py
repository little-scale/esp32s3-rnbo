# SPDX-License-Identifier: MIT
"""Independent piecewise-linear observations for the authored line/pack graph.

This is a native qualification tool, not a compiler adapter or an RNBO loop
implementation. Integer event positions and relative segment ages stay exact;
the model never stores absolute sample time in a Float32 value. The reviewed
discrete policy holds the previous value at a command's first sample and uses
ceil(duration) for expiry, with a one-sample endpoint allowance reported apart
from the amplitude error. These conventions are not a quotation of the docs.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
import json
import math
from pathlib import Path
import struct


def require(condition, message):
    if not condition:
        raise ValueError(message)


def float32(value):
    require(type(value) in (int, float), "Finite numeric value required")
    try:
        require(math.isfinite(value), "Finite numeric value required")
        result = struct.unpack("<f", struct.pack("<f", value))[0]
    except (OverflowError, struct.error) as exc:
        raise ValueError("Float32 overflow") from exc
    require(math.isfinite(result), "Finite Float32 value required")
    return result


def word(value):
    return struct.unpack("<I", struct.pack("<f", value))[0]


def round_positive_fraction(value):
    """Round a bounded nonnegative rational directly to binary32, ties to even.

    A binary64 approximation locates three neighbouring candidates only. Exact
    rational distances, including the even low bit, select the final result.
    This avoids using a possibly double-rounded approximation as the oracle.
    """
    require(isinstance(value, Fraction) and 0 <= value <= 4410, "Duration rational out of range")
    centre = word(float32(float(value)))
    candidates = range(max(0, centre - 1), min(0x7F7FFFFF, centre + 1) + 1)
    best = min(candidates, key=lambda bits: (
        abs(Fraction.from_float(struct.unpack("<f", struct.pack("<I", bits))[0]) - value),
        bits & 1, bits))
    return struct.unpack("<f", struct.pack("<I", best))[0]


def duration(milliseconds):
    value = float32(milliseconds)
    require(0 <= value <= 100, "Milliseconds outside the authored parameter range")
    exact = Fraction.from_float(value) * Fraction(441, 10)
    rounded = round_positive_fraction(exact)
    if rounded == 0:
        rounded = math.copysign(rounded, value)
    original = float32(value * 44100.0 * 0.001)
    return max(rounded, 1.0) if rounded <= 0 else rounded, {
        "milliseconds_bits": f"{word(value):08x}",
        "rational_duration_bits": f"{word(rounded):08x}",
        "original_double_duration_bits": f"{word(original):08x}",
        "conversion_agrees": word(rounded) == word(original),
        "zero_duration_becomes_one_sample": rounded <= 0,
    }


@dataclass(frozen=True)
class Segment:
    start: int
    initial: float
    target: float
    samples: float

    def at(self, frame):
        age = frame - self.start
        if age <= 0:
            return self.initial
        if age >= self.samples:
            return self.target
        return self.initial + (self.target - self.initial) * (age / self.samples)


def reference(case):
    require(type(case.get("blocks")) is int and 0 < case["blocks"] <= 4096, "Invalid captured block count")
    prefix = case.get("prefix_blocks", 0)
    warmup = case.get("warmup_blocks", 0)
    require(type(prefix) is int and 0 <= prefix < (1 << 56), "Invalid sequential prefix")
    require(type(warmup) is int and 0 <= warmup <= 64, "Invalid warmup")
    if "absolute_first_capture_sample" in case:
        require(case["absolute_first_capture_sample"] == (prefix + warmup) * 256, "Capture timestamp differs")
    frames = case["blocks"] * 256
    require(isinstance(case.get("events"), list), "Explicit ordered events required")
    active = Segment(0, 0.0, 0.0, 1.0)
    segments = [active]
    observer = [(0, 0.0)]
    milliseconds = 10.0
    previous_block = 0
    conversions = []
    for event_index, event in enumerate(case["events"]):
        block = event.get("block")
        require(type(block) is int and previous_block <= block < case["blocks"], "Events must be in authored block order")
        previous_block = block
        value = float32(event.get("value"))
        if "value_bits" in event:
            require(event["value_bits"] == f"{word(value):08x}", "Event value/word differs")
        if event.get("id") == "milliseconds":
            require(0 <= value <= 100, "Milliseconds outside the authored parameter range")
            milliseconds = value  # pack's cold inlet does not emit a ramp.
        elif event.get("id") == "target":
            require(-1 <= value <= 1, "Target outside the authored parameter range")
            start = block * 256
            samples, conversion = duration(milliseconds)
            conversions.append({"event_index": event_index, "block": block, **conversion})
            active = Segment(start, active.at(start), value, samples)
            if segments[-1].start == start:
                segments[-1] = active
            else:
                segments.append(active)
            if observer[-1][0] == start:
                observer[-1] = (start, value)
            else:
                observer.append((start, value))
        else:
            raise ValueError("Unknown parameter in the reviewed graph")
    return frames, segments, observer, conversions


def analyse(case, raw, *, maximum_absolute_error=2e-5, endpoint_allowance=1):
    """Observe each captured word against an independent ideal ramp and target.

    The fixed absolute limit is an additional accuracy observation; it does
    not replace or widen the five original catalogue gates. Baseline failures
    are returned as evidence, rather than being fitted with a new tolerance.
    """
    require(type(maximum_absolute_error) in (int, float) and math.isfinite(maximum_absolute_error)
            and 0 < maximum_absolute_error <= 2e-5, "Accuracy limit may not be widened")
    require(type(endpoint_allowance) is int and 0 <= endpoint_allowance <= 1, "Endpoint allowance may not be widened")
    frames, segments, observer, conversions = reference(case)
    cycles = case.get("lifecycles", 1)
    require(type(cycles) is int and cycles > 0, "Invalid lifecycle count")
    require(isinstance(raw, bytes) and len(raw) == frames * cycles * 8, "Incomplete Float32 capture")
    results = []
    for cycle in range(cycles):
        segment_index = observer_index = 0
        maximum = 0.0
        first_failure = None
        observer_errors = nonfinite = 0
        last_mismatch = {}
        data = raw[cycle * frames * 8:(cycle + 1) * frames * 8]
        for frame, (left, right) in enumerate(struct.iter_unpack("<ff", data)):
            while segment_index + 1 < len(segments) and segments[segment_index + 1].start <= frame:
                segment_index += 1
            while observer_index + 1 < len(observer) and observer[observer_index + 1][0] <= frame:
                observer_index += 1
            segment = segments[segment_index]
            expected = segment.at(frame)
            finite = math.isfinite(left) and math.isfinite(right)
            if not finite:
                nonfinite += 1
                if first_failure is None:
                    first_failure = {"frame": frame, "reason": "nonfinite_output"}
            else:
                error = abs(left - expected)
                maximum = max(maximum, error)
                if error > maximum_absolute_error and first_failure is None:
                    first_failure = {"frame": frame, "reason": "ideal_ramp_error", "error": error,
                                     "actual": left, "expected": expected}
            if word(right) != word(observer[observer_index][1]):
                observer_errors += 1
            if left != segment.target:
                last_mismatch[segment_index] = frame
        endpoints = []
        for index, segment in enumerate(segments):
            stop = segments[index + 1].start if index + 1 < len(segments) else frames
            expected = segment.start + math.ceil(segment.samples)
            if segment.initial == segment.target or stop <= expected + endpoint_allowance:
                continue  # No observable endpoint, or interrupted before settling.
            observed = max(segment.start, last_mismatch.get(index, segment.start - 1) + 1)
            critical = expected - endpoint_allowance - 1
            observable = critical >= segment.start and abs(segment.at(critical) - segment.target) > maximum_absolute_error
            reason = ("Observable outside the fixed amplitude budget" if observable else
                      "No disallowed early sample exists" if critical < segment.start else
                      "Early target equality is inside the fixed amplitude budget")
            late_hold = observed <= expected + endpoint_allowance
            endpoints.append({"start": segment.start, "expected_settled_frame": expected,
                              "observed_settled_frame": observed, "difference": observed - expected,
                              "early_timing_qualified": observable, "early_timing_reason": reason,
                              "late_target_hold_passed": late_hold,
                              "passed": late_hold and (not observable or observed >= expected - endpoint_allowance)})
        results.append({"cycle": cycle, "words": frames * 2, "maximum_absolute_ideal_error": maximum,
                        "first_failure": first_failure, "observer_word_errors": observer_errors,
                        "nonfinite_frames": nonfinite, "endpoints": endpoints,
                        "passed": first_failure is None and observer_errors == 0 and all(e["passed"] for e in endpoints)})
    return {"kind": "independent-line-piecewise-ramp-v2", "hardware_executed": False,
            "maximum_absolute_error_limit": maximum_absolute_error, "endpoint_allowance_samples": endpoint_allowance,
            "internal_completion_clock_qualified": False,
            "absolute_timestamps_rounded_to_float32": False, "conversions": conversions,
            "cycles": results, "passed": all(r["passed"] for r in results) and all(c["conversion_agrees"] for c in conversions)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--float-capture", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    require(plan.get("sample_rate") == 44100 and plan.get("block_frames") == 256, "Unreviewed timebase")
    matches = [case for case in plan["cases"] if case["id"] == args.case]
    require(len(matches) == 1, "Unknown or duplicate case")
    print(json.dumps(analyse(matches[0], args.float_capture.read_bytes()), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
