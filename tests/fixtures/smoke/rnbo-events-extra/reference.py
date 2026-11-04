# SPDX-License-Identifier: MIT
"""Independent boundary-event math with a held left signal and raw right pilot.

Fresh drive defaults0; the first authored event sets1 before call0. Exactly20
fixed256-frame callbacks follow zero automatic preparation warm blocks: manual4
plus timed16. Events are actual parameter values before callbacks, in authored
order; the last value at a duplicate callback wins. No within-block timestamp,
reset, arbitrary cold-inlet, or one-frame ABI behavior is claimed.

Left is op(drive,2), except OR's cold0. Unary operations use drive alone.
Integer and floating stores take hot numeric input, with literal2 only their
initial stored value. Reverse arithmetic has nonzero hot divisors; denormal
models include actual signed subnormals. NaN operations have finite-only scope. Definitions are
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
    171:'fabs',172:'pass',173:'bool',174:'subtract2',175:'multiply2',
    176:'equal2',177:'not-equal2',178:'greater2',179:'greater-equal2',
    180:'less2',181:'less-equal2',182:'and2',183:'or0',184:'xor2',
    185:'reverse-subtract2',186:'absolute-difference2',187:'isnan-finite',
    188:'fixnan-finite',189:'isdenorm',190:'fixdenorm',191:'integer-store',
    192:'floating-store',193:'reverse-divide2',194:'reverse-remainder2',195:'step2',
}
MODELS = frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES = {model: 0 for model in MODELS}
REFERENCE_POLICIES = {
    187:'finite-only-no-NaN-handling-claim',188:'finite-only-no-NaN-handling-claim',
    189:'binary32-subnormal-bit-definition',190:'subnormal-flush-to-numeric-zero',
    191:'hot-integer-store-truncates-toward-zero',192:'hot-floating-store',
    193:'nonzero-hot-divisor',194:'signed-remainder-nonzero-hot-divisor',
    195:'not-first-less-than-second',
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
        raise ValueError('Unknown RNBO extra boundary-event model')


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
    replacements = iter((1.,3.,2.) if model in (179,195) else
                        (4.,2.,1.) if model == 186 else
                        (3.,1.,2.) if model in (176,177,181) else (3.,2.,1.))
    events=[]
    for call, x in _SCHEDULE:
        if call == 10:
            x=next(replacements)
        if model in (193,194) and x == 0:
            x=2.  # original zero events are outside the reverse-divisor domain
        if model in (189,190):
            if call == 3: x=value(1)
            elif call == 4: x=value(0x80000001)
            elif call == 5: x=value(0x007fffff)
            elif call == 8: x=value(0x00800000)
        events.append({'before_call':call,'id':PARAMETER_ID,'value':float(x)})
    return events


def _remainder(x, base):
    quotient = math.trunc(Fraction(x) / base)
    remainder = Fraction(x) - quotient * base
    return math.copysign(0., x) if not remainder else float(remainder)


def _operation(model, x):
    if model == 171: result=abs(x)
    elif model in (172,188,192): result=x
    elif model == 173: result=x != 0
    elif model == 174: result=x-2
    elif model == 175: result=x*2
    elif model == 176: result=x == 2
    elif model == 177: result=x != 2
    elif model == 178: result=x > 2
    elif model in (179,195): result=x >= 2
    elif model == 180: result=x < 2
    elif model == 181: result=x <= 2
    elif model == 182: result=(x != 0) and True
    elif model == 183: result=(x != 0) or False
    elif model == 184: result=(x != 0) != True
    elif model == 185: result=2-x
    elif model == 186: result=abs(x-2)
    elif model == 187: result=0.
    elif model == 189: result=(word(x)&0x7f800000)==0 and (word(x)&0x007fffff)!=0
    elif model == 190: result=0. if (word(x)&0x7f800000)==0 and (word(x)&0x007fffff)!=0 else x
    elif model == 191: result=math.trunc(x)
    elif model == 193: result=2/Fraction(x)
    elif model == 194: result=_remainder(2.,Fraction(x))
    else: raise ValueError('Unknown event operation')
    return word(float(result))


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
