# SPDX-License-Identifier: MIT
"""Independent mathematical references for the third stateful-object wave.

No generated kernel is imported. Constant input/control spans use the closed
form of a single-pole exponential, retaining Float64 mathematical history.
Sample/hold selects source indices from the crossing predicate, rather than
replaying a generated held-value loop or caching an old threshold decision.
"""
from __future__ import annotations

import math
import struct

LIMITS = {'onepole-hz': 3e-6, 'slide': 3e-6, 'delta': 2e-6, 'sah': 0.0}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def wire32(value):
    require(type(value) in (int, float), 'Numeric wire value required')
    try:
        require(math.isfinite(value), 'Finite wire value required')
        result = struct.unpack('<f', struct.pack('<f', value))[0]
    except (OverflowError, struct.error) as exc:
        raise ValueError('Float32 wire overflow') from exc
    require(math.isfinite(result), 'Finite Float32 wire required')
    return result


def bits(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def coefficient_hz(frequency, sample_rate=44100):
    require(type(sample_rate) is int and sample_rate == 44100, 'Unreviewed sample rate')
    require(type(frequency) in (int, float) and math.isfinite(frequency), 'Finite frequency required')
    if frequency <= 0:
        return 1e-5
    # expm1 gives an independent stable evaluation of 1-exp(-omega), including
    # near the lower clamp; it does not reproduce Float32 cancellation.
    return max(1e-5, min(.99999, -math.expm1(-math.tau * frequency / sample_rate)))


def _vectors(*vectors):
    require(vectors and len(vectors[0]) > 0, 'Nonempty vectors required')
    count = len(vectors[0])
    require(all(len(v) == count for v in vectors), 'Vector lengths differ')
    require(all(type(x) in (int, float) and math.isfinite(x) for v in vectors for x in v), 'Finite samples required')
    return count


def _span(initial, target, coefficient, count):
    if coefficient == 1:
        return [target] * count
    exponent = math.log1p(-coefficient)
    return [math.fsum((initial * math.exp((i + 1) * exponent),
                       target * -math.expm1((i + 1) * exponent))) for i in range(count)]


def onepole_reference(source, cutoff, *, initial=0.0):
    count = _vectors(source, cutoff)
    require(math.isfinite(initial), 'Finite initial history required')
    result = []
    start = 0
    state = float(initial)
    while start < count:
        stop = start + 1
        while stop < count and source[stop] == source[start] and cutoff[stop] == cutoff[start]:
            stop += 1
        values = _span(state, source[start], coefficient_hz(cutoff[start]), stop - start)
        result.extend(values)
        state = values[-1]
        start = stop
    return result


def slide_reference(source, up, down, *, initial=0.0):
    count = _vectors(source, up, down)
    require(math.isfinite(initial), 'Finite initial history required')
    result = []
    state = float(initial)
    start = 0
    while start < count:
        stop = start + 1
        while stop < count and source[stop] == source[start] and up[stop] == up[start] and down[stop] == down[start]:
            stop += 1
        rate = up[start] if source[start] > state else down[start]
        coefficient = 1 / max(1, abs(rate))
        # A constant target is approached monotonically, so its direction
        # branch cannot change within this exact mathematical span.
        values = _span(state, source[start], coefficient, stop - start)
        result.extend(values)
        state = values[-1]
        start = stop
    return result


def delta_reference(source, *, previous_input=0.0):
    _vectors(source)
    require(math.isfinite(previous_input), 'Finite previous input required')
    prior = [previous_input, *source[:-1]]
    return [current - previous for current, previous in zip(source, prior)]


def sah_reference(source, trigger, threshold, *, held_initial=0.0, previous_trigger=0.0):
    _vectors(source, trigger, threshold)
    require(math.isfinite(held_initial) and math.isfinite(previous_trigger), 'Finite initial state required')
    previous = [previous_trigger, *trigger[:-1]]
    crossings = [i for i, (old, now, limit) in enumerate(zip(previous, trigger, threshold)) if old <= limit < now]
    result = [held_initial] * len(source)
    for index, start in enumerate(crossings):
        stop = crossings[index + 1] if index + 1 < len(crossings) else len(source)
        result[start:stop] = [source[start]] * (stop - start)
    return result, crossings


def parameter_planes(fixture, case, frames):
    require(type(frames) is int and frames > 0 and frames % 256 == 0, 'Whole captured blocks required')
    definitions = {p['id']: p for p in fixture.get('parameters', [])}
    require(len(definitions) == len(fixture.get('parameters', [])), 'Duplicate parameter definition')
    values = {name: wire32(p['initial']) for name, p in definitions.items()}
    planes = {name: [value] * frames for name, value in values.items()}
    previous_block = 0
    for event in case.get('events', []):
        block, name = event.get('block'), event.get('id')
        require(type(block) is int and previous_block <= block < frames // 256, 'Events out of authored order/range')
        require(name in definitions and event.get('form', 'actual') == 'actual', 'Unreviewed parameter event')
        value = wire32(event.get('value'))
        require(definitions[name]['minimum'] <= value <= definitions[name]['maximum'], 'Parameter outside authored bounds')
        planes[name][block * 256:] = [value] * (frames - block * 256)
        values[name] = value
        previous_block = block
    return planes


def expected_outputs(fixture, case, inputs):
    frames = _vectors(*inputs)
    require(len(inputs) == 2, 'Stereo FX inputs required')
    if 'blocks' in case:
        require(type(case['blocks']) is int and case['blocks'] * 256 == frames, 'Incomplete planned input capture')
    planes = parameter_planes(fixture, case, frames)
    semantic = fixture['semantic']
    family = semantic['kind']
    require(family in LIMITS, 'Unknown mathematical family')
    def control(spec):
        if spec['kind'] == 'literal':
            return [wire32(spec['value'])] * frames
        if spec['kind'] == 'parameter':
            require(spec['id'] in planes, 'Unknown control parameter')
            return planes[spec['id']]
        require(spec['kind'] == 'input' and spec['channel'] in (0, 1), 'Unknown signal control')
        return inputs[spec['channel']]
    outputs = [None, None]
    crossings = {}
    copies = set()
    for model in semantic['output_models']:
        channel = model['channel']
        require(channel in (0, 1) and outputs[channel] is None, 'Unknown/duplicate output channel')
        if 'copy_input' in model:
            outputs[channel] = list(inputs[model['copy_input']])
            copies.add(channel)
            continue
        source = inputs[model['data_channel']]
        if family == 'onepole-hz':
            outputs[channel] = onepole_reference(source, control(model['cutoff']), initial=semantic['initial'])
        elif family == 'slide':
            outputs[channel] = slide_reference(source, control(model['up']), control(model['down']), initial=semantic['initial'])
        elif family == 'delta':
            outputs[channel] = delta_reference(source, previous_input=semantic['previous_input_initial'])
        else:
            outputs[channel], crossings[channel] = sah_reference(source, inputs[model['trigger_channel']], control(model['threshold']),
                held_initial=semantic['held_initial'], previous_trigger=semantic['previous_trigger_initial'])
    require(all(output is not None for output in outputs), 'Incomplete output model')
    return outputs, {'family': family, 'exact_copy_channels': sorted(copies), 'crossing_indices': crossings}


def analyse(fixture, case, inputs, actual):
    _vectors(*inputs, *actual)
    require(len(actual) == 2, 'Stereo output required')
    expected, basis = expected_outputs(fixture, case, inputs)
    family = basis['family']
    limit = LIMITS[family]
    channels = []
    for channel, (truth, output) in enumerate(zip(expected, actual)):
        exact = family == 'sah' or channel in basis['exact_copy_channels']
        maximum = 0.0
        first = None
        word_errors = 0
        for frame, (ideal, observed) in enumerate(zip(truth, output)):
            error = abs(observed - ideal)
            maximum = max(maximum, error)
            mismatch = bits(observed) != bits(ideal) if exact else error > limit
            if exact and mismatch:
                word_errors += 1
            if mismatch and first is None:
                first = {'frame': frame, 'observed': observed, 'expected': ideal, 'absolute_error': error}
        channels.append({'channel': channel, 'maximum_absolute_error': maximum, 'exact_wire_copy': exact,
                         'word_errors': word_errors, 'first_failure': first, 'passed': first is None})
    return {'kind': 'wave3-independent-mathematical-oracle-v1', **basis, 'limit': limit,
            'frames': len(inputs[0]), 'channels': channels, 'passed': all(c['passed'] for c in channels),
            'hardware_executed': False, 'target_performance_measured': False}
