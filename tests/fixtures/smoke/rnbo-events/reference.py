# SPDX-License-Identifier: MIT
"""Independent boundary-event math with a held left signal and raw right pilot.

Fresh drive defaults0; the first authored event sets1 before call0. Exactly20
fixed256-frame callbacks follow zero automatic preparation warm blocks: manual4
plus timed16. Events are actual parameter values before callbacks, in authored
order; the last value at a duplicate callback wins. No within-block timestamp,
reset, arbitrary cold-inlet, or one-frame ABI behavior is claimed.

Left is op(drive,2), except OR's explicitly authored cold0. Unary operations
use drive alone. Round uses nearest multiple2, with declared ties-away policy;
fract/mod use signed remainder and a truncating quotient. Definitions are
mathematical/primary-document conventions, not evaluated generated algorithms.
Right is input2 copied word-for-word, independent of parameter events. All
models use exact numeric left comparison and exact raw right comparison;
left zero signs may be reported separately by the smoke harness.
"""
from fractions import Fraction
import math
import struct

BLOCK_FRAMES = 256
PREPARE_ZERO_WARM_BLOCKS = 0
MANUAL_WARM_CALLS = 4
TIMED_CALLS = 16
REFERENCE_CALL_COUNT = MANUAL_WARM_CALLS + TIMED_CALLS
PARAMETER_ID = 'drive'
PARAMETER_DEFAULT = 0.
PARAMETER_RANGE = (-8., 8.)
PILOT_RIGHT_BIT_EXACT = True
MODEL_NAMES = {
    148: 'abs', 149: 'neg', 150: 'floor', 151: 'ceil', 152: 'trunc',
    153: 'round-multiple2', 154: 'signed-fract', 155: 'sign',
    156: 'boolnum', 157: 'not', 158: 'add2', 159: 'subtract2',
    160: 'multiply2', 161: 'divide-by2', 162: 'signed-modulo2',
    163: 'minimum2', 164: 'maximum2', 165: 'equal2', 166: 'greater2',
    167: 'less2', 168: 'and2', 169: 'or0', 170: 'xor2',
}
MODELS = frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES = {model: 0 for model in MODELS}
REFERENCE_POLICIES = {
    153: 'declared-nearest-multiple2-ties-away-from-zero',
    154: 'signed-fraction-convention',
    162: 'signed-remainder-truncating-quotient',
    169: 'event-hot-input-with-cold-zero',
}


def word(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def value(word):
    return struct.unpack('<f', struct.pack('<I', word))[0]


LEFT_WORDS = tuple(word(x) for x in (-1., -.75, -.5, -.25, -.125, -0., 0., .125,
                                    .25, .5, .75, 1., .375, -.375, .625, -.625))
PILOT_WORDS = (0, 0x80000000, 1, 0x80000001, 0x007fffff, 0x807fffff,
               0x00800000, 0x80800000, 0x3e800000, 0xbe800000, 0x3f000000,
               0xbf000000, 0x3f800000, 0xbf800000, 0x7f7fffff, 0xff7fffff)
# Gaps13/14 deliberately hold. Calls7/11 resend unchanged values. Calls10/16
# deliberately have multiple updates; preserving their order is observable.
_SCHEDULE = (
    (0, 1.), (1, -2.), (2, 0.), (3, .5), (4, -.5), (5, -1.5),
    (6, 2.), (7, 2.), (8, -8.), (9, 8.),
    (10, 3.), (10, 2.), (10, 1.), (11, 1.), (12, 1.5),
    (15, -0.), (16, 0.), (16, 1.), (17, -1.), (18, .75), (19, -.75),
)


def _model(model):
    if type(model) is not int or model not in MODELS:
        raise ValueError('Unknown RNBO boundary-event model')


def input_words(frames=256):
    if type(frames) is not int or frames != BLOCK_FRAMES:
        raise ValueError('This boundary-event smoke reference requires256 frames')
    return tuple(w for n in range(frames)
                 for w in (LEFT_WORDS[(n // 16) % 16], PILOT_WORDS[n % 16]))


def case_input_words(model, frames=256):
    _model(model)
    return input_words(frames)


def parameter_events(model):
    _model(model)
    values = iter((.25, -.5, .75) if model in (154, 162)
                  else ((3., 1., 2.) if model == 165 else (3., 2., 1.)))
    return [{'before_call': call, 'id': PARAMETER_ID, 'value': next(values) if call == 10 else x}
            for call, x in _SCHEDULE]


def _remainder(x, base):
    quotient = math.trunc(Fraction(x) / base)
    remainder = Fraction(x) - quotient * base
    return math.copysign(0., x) if not remainder else float(remainder)


def _operation(model, x):
    if model == 148: result = abs(x)
    elif model == 149: result = -x
    elif model == 150: result = math.floor(x)
    elif model == 151: result = math.ceil(x)
    elif model == 152: result = math.trunc(x)
    elif model == 153:
        quotient = abs(Fraction(x) / 2)
        integer = (2 * quotient.numerator + quotient.denominator) // (2 * quotient.denominator)
        result = math.copysign(float(2 * integer), x)
    elif model == 154: result = _remainder(x, 1)
    elif model == 155: result = x if x == 0 else (1. if x > 0 else -1.)
    elif model == 156: result = x != 0
    elif model == 157: result = x == 0
    elif model == 158: result = x + 2
    elif model == 159: result = x - 2
    elif model == 160: result = x * 2
    elif model == 161: result = x / 2
    elif model == 162: result = _remainder(x, 2)
    elif model == 163: result = min(x, 2.)
    elif model == 164: result = max(x, 2.)
    elif model == 165: result = x == 2
    elif model == 166: result = x > 2
    elif model == 167: result = x < 2
    elif model == 168: result = (x != 0) and (2 != 0)
    elif model == 169: result = (x != 0) or (0 != 0)
    else: result = (x != 0) != (2 != 0)
    return word(result)


def reference_blocks(model, inputs, call_count=20):
    _model(model)
    if type(call_count) is not int or not 1 <= call_count <= REFERENCE_CALL_COUNT:
        raise ValueError('Invalid boundary-event callback count')
    inputs = tuple(inputs)
    if len(inputs) != 2 * BLOCK_FRAMES:
        raise ValueError('Expected one interleaved256-frame input vector')
    if any(type(w) is not int or not 0 <= w <= 0xffffffff or (w & 0x7f800000) == 0x7f800000 for w in inputs):
        raise ValueError('Expected finite raw binary32 input words')
    events = parameter_events(model)
    previous_call = -1
    for event in events:
        if (set(event) != {'before_call', 'id', 'value'} or type(event['before_call']) is not int
                or not previous_call <= event['before_call'] < REFERENCE_CALL_COUNT
                or event['id'] != PARAMETER_ID or type(event['value']) is not float
                or not math.isfinite(event['value']) or not -8 <= event['value'] <= 8):
            raise ValueError('Invalid ordered actual-parameter schedule')
        previous_call = event['before_call']
    if not events or events[0] != {'before_call': 0, 'id': 'drive', 'value': 1.}:
        raise ValueError('First event must change the defaultdrive before call0')
    pilot = inputs[1::2]
    blocks = []
    current = PARAMETER_DEFAULT
    index = 0
    for call in range(call_count):
        while index < len(events) and events[index]['before_call'] == call:
            current = value(word(events[index]['value']))  # actual parameter representation
            index += 1
        expected = _operation(model, current)
        blocks.append(tuple(w for right in pilot for w in (expected, right)))
    return tuple(blocks)


def reference_words(model, inputs):
    return reference_blocks(model, inputs, 1)[0]
