# SPDX-License-Identifier: MIT
"""Independent sample-state mathematics for a fixed256-frame Gen smoke batch.

Epoch: fresh constructor/initialization, SDKprepare zero warm blocks, then four
compared manual warm calls and sixteen compared timed calls. The same256-frame
input vector repeats; all state persists across the twenty calls. This model
makes no assertion about a variable-block or single-frame production ABI.

Definitions come from primary Gen documentation, not generated algorithms.
Delta/change compare against initial input0. Latch/sah initially hold0; sah
compares the previous raw control to the CURRENT threshold. Slide starts0 and
uses the ideal difference-update equation with the authored sample constants.
DCblock uses the documented ideal coefficient9997/10000 with Float64 state.
Accumulator adds then outputs, reset held0. Counter's explicitly declared policy
is initial0, increment BEFORE output, wrapping at7/5; the prose reference is
less explicit about its first-frame ordering, so retain any discrepancy.
"""
import math
import struct

BLOCK_FRAMES = 256
PREPARE_ZERO_WARM_BLOCKS = 0
MANUAL_WARM_CALLS = 4
TIMED_CALLS = 16
REFERENCE_CALL_COUNT = MANUAL_WARM_CALLS + TIMED_CALLS
MODEL_NAMES = {
    104: 'delta', 105: 'change', 106: 'latch', 107: 'dcblock',
    108: 'sah-default', 109: 'sah-half-threshold', 110: 'sah-signal-threshold',
    111: 'slide-up2-down4', 112: 'slide-up4-down2',
    113: 'accum-reset0', 114: 'counter-increment-before-output-max7-max5',
}
MODELS = frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES = {model: 2e-6 if model in (107, 111, 112) else 0 for model in MODELS}
REFERENCE_POLICIES = {
    104: 'gen-previous-input0', 105: 'gen-sign-of-input-difference',
    106: 'gen-nonzero-track-zero-hold-initial0',
    107: 'gen-ideal-dcblock-coefficient-9997-over10000',
    108: 'gen-raw-control-rising-threshold0-initial0',
    109: 'gen-raw-control-rising-threshold-half-initial0',
    110: 'gen-raw-previous-control-versus-current-signal-threshold',
    111: 'gen-ideal-slide-initial0-up2-down4',
    112: 'gen-ideal-slide-initial0-up4-down2',
    113: 'gen-add-before-output-initial0-reset0',
    114: 'declared-gen-counter-increment-before-output-initial0',
}


def word(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def value(word):
    return struct.unpack('<f', struct.pack('<I', word))[0]


# Late control rises and held values deliberately differ from the next block's
# first data0. This makes a constructor/reset at256 boundaries observable.
LEFT = (0., .25, .25, -.5, -.5, -0., 1., 1., -1., -1., .5, .5, 0., .125, .125, .75)
RIGHT = (0., 1., 1., -0., -1., -1., .5, .5, 0., .25, -.25, -.25, -1., 1., 1., 1.)


def _model(model):
    if type(model) is not int or model not in MODELS:
        raise ValueError('Unknown Gen stateful smoke model')


def input_words(frames=256):
    if type(frames) is not int or frames != BLOCK_FRAMES:
        raise ValueError('This stateful smoke reference requires256 frames')
    return tuple(word(x) for n in range(frames) for x in (LEFT[n % 16], RIGHT[n % 16]))


def case_input_words(model, frames=256):
    _model(model)
    inputs = input_words(frames)
    if model == 113:
        return tuple(word(value(w) / 1024.) for w in inputs)
    return inputs


def reference_blocks(model, inputs, call_count=20):
    _model(model)
    if type(call_count) is not int or not 1 <= call_count <= REFERENCE_CALL_COUNT:
        raise ValueError('Invalid stateful smoke call count')
    inputs = tuple(inputs)
    if len(inputs) != 2 * BLOCK_FRAMES:
        raise ValueError('Expected one interleaved256-frame input vector')
    bound = 1. / 1024 if model == 113 else 1.
    for w in inputs:
        if (type(w) is not int or not 0 <= w <= 0xffffffff
                or (w & 0x7f800000) == 0x7f800000 or not -bound <= value(w) <= bound):
            raise ValueError('Input outside the authored finite stateful smoke domain')
    vector = tuple(value(w) for w in inputs)
    previous_input = [0., 0.]
    previous_control = [0., 0.]
    state = [0., 0.]
    blocks = []
    for call in range(call_count):
        output = []
        for frame in range(BLOCK_FRAMES):
            absolute_sample = call * BLOCK_FRAMES + frame
            for channel in range(2):
                x = vector[2 * frame + channel]
                control = vector[2 * frame + 1 - channel]
                if model == 104:
                    result = x - previous_input[channel]
                    previous_input[channel] = x
                elif model == 105:
                    previous = previous_input[channel]
                    result = 1. if x > previous else (-1. if x < previous else 0.)
                    previous_input[channel] = x
                elif model == 106:
                    if control != 0:
                        state[channel] = x
                    result = state[channel]
                elif model == 107:
                    result = x - previous_input[channel] + .9997 * state[channel]
                    previous_input[channel] = x
                    state[channel] = result  # Float64ideal state, not a Float32DSP recurrence
                elif model in (108, 109, 110):
                    threshold = 0. if model == 108 else (.5 if model == 109 else x)
                    if previous_control[channel] <= threshold < control:
                        state[channel] = x
                    previous_control[channel] = control
                    result = state[channel]
                elif model in (111, 112):
                    up, down = (2., 4.) if model == 111 else (4., 2.)
                    samples = up if x > state[channel] else down
                    state[channel] += (x - state[channel]) / samples
                    result = state[channel]  # ideal state; emitted words round only once
                elif model == 113:
                    state[channel] += x  # all authored increments and sums are exact dyadics
                    result = state[channel]
                else:
                    result = (absolute_sample + 1) % (7 if channel == 0 else 5)
                output.append(word(result))
        blocks.append(tuple(output))
    return tuple(blocks)


def reference_words(model, inputs):
    return reference_blocks(model, inputs, 1)[0]
