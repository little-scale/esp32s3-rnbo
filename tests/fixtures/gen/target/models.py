# SPDX-License-Identifier: MIT
"""Closed-form independent history truth, not a generated recurrence.

Feedback uses the last64 source terms newest-to-oldest in ordinary binary64.
Periodic histories use integer phase. Epoch−1024 accounts for four detached
zero-input vectors. Runtime reset reanchors to its actual capture frame.
"""
import math
import struct
import sys

MAX_FRAMES = 16384
PATTERN = (0.25, -0.125, 0.5, 0.0, -0.25, 0.125, -0.5)
LIMIT = 2e-6
WITNESS_MINIMUM_SEPARATION = 4 * LIMIT
TAIL_BOUND = 2.0**-64
EVALUATION_BOUND = 128 * sys.float_info.epsilon


def bounds(model):
    if type(model) is not int or model not in (1, 2, 3):
        raise ValueError("Unknown closed Gen history model")
    return {"model_tail_bound": TAIL_BOUND if model == 1 else 0.0,
            "model_evaluation_bound": EVALUATION_BOUND if model == 1 else 0.0}


def _f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def truth_at(model, frame, epoch, left):
    bounds(model)
    if type(frame) is not int or type(epoch) is not int or not -1024 <= epoch <= frame < len(left):
        raise ValueError("Invalid history frame/epoch")
    if model == 1:
        start = max(0, epoch)
        history = 0.0
        for age in range(1, min(64, frame - start) + 1):
            term = math.ldexp(left[frame - age], -(age - 1))
            history = history + term
        return left[frame] + 0.5 * history, history
    phase = (frame - epoch) % model
    return float(1 + phase), float(1 + (phase + 1) % model)


def expected_outputs(model, planes, events=(), *, warmup_blocks=4):
    bound = bounds(model)
    if type(warmup_blocks) is not int or warmup_blocks != 4 or type(planes) not in (tuple, list) or len(planes) != 2:
        raise ValueError("Expected two planes and the declared four zero warmup vectors")
    left, right = tuple(planes[0]), tuple(planes[1])
    if len(left) != len(right) or not 1 <= len(left) <= MAX_FRAMES:
        raise ValueError("Invalid Gen input span")
    for n, pair in enumerate(zip(left, right)):
        if any(type(x) is not float or not math.isfinite(x) or abs(x) > 0.5 or _f32(x) != x or struct.pack('<f', x) != struct.pack('<f', PATTERN[(n + ch * 3) % 7]) for ch, x in enumerate(pair)):
            raise ValueError("Input differs from exact authored dyadic stimulus")
    if type(events) not in (list, tuple) or len(events) > 64:
        raise ValueError("Reset event list must be bounded")
    order = []
    for event in events:
        if type(event) is not dict or set(event) != {"block", "id", "form", "value"}:
            raise ValueError("Unknown reset event fields")
        block = event['block']
        if type(block) is not int or not 0 <= block * 256 < len(left) or event['id'] != 's3_reset' or event['form'] != 'actual' or type(event['value']) is not float or event['value'] != 1.0:
            raise ValueError("Only actual s3_reset=1 at an existing vector boundary is admitted")
        order.append(block * 256)
    if order != sorted(order):
        raise ValueError("Reset events must preserve monotonic source order")
    epoch = -1024
    at = 0
    truth = [[], []]
    cache = [[], []]
    rounding = 0.0
    witnesses = []
    for frame in range(len(left)):
        while at < len(order) and order[at] == frame:
            counterfactual = tuple(_f32(x) for x in truth_at(model, frame, epoch, left))
            reset = tuple(_f32(x) for x in truth_at(model, frame, frame, left))
            separation = max(abs(x - y) for x, y in zip(reset, counterfactual))
            witnesses.append({'event_index': at, 'block': frame // 256, 'frame': frame,
                              'epoch_before': epoch, 'reset_pair': reset,
                              'without_current_reset_pair': counterfactual,
                              'maximum_pair_separation': separation,
                              'observable_at_limit': separation > WITNESS_MINIMUM_SEPARATION})
            epoch = frame
            at += 1
        pair = truth_at(model, frame, epoch, left)
        for ch, value in enumerate(pair):
            wire = _f32(value)
            truth[ch].append(value); cache[ch].append(wire)
            rounding = max(rounding, abs(wire - value))
    mask = [0] * ((len(left) + 255) // 256)
    for witness in witnesses:
        if witness['observable_at_limit']: mask[witness['block']] = 1
    return {'truth': tuple(tuple(x) for x in truth), 'cache': tuple(tuple(x) for x in cache),
            'maximum_cache_rounding_error': rounding, **bound,
            'semantic_limit': LIMIT, 'scheduled_reset_count': len(order),
            'observable_reset_count': sum(w['observable_at_limit'] for w in witnesses),
            'reset_witness_mask': tuple(mask), 'witness_minimum_separation': WITNESS_MINIMUM_SEPARATION,
            'reset_witnesses': witnesses}


def cache_bytes(result):
    return b''.join(struct.pack('<ff', a, b) for a, b in zip(*result['cache']))


def reset_witness_bytes(result):
    return bytes(result['reset_witness_mask'])
