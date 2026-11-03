# SPDX-License-Identifier: MIT
"""Independent short RNBO math/logic vectors, with no generated DSP dependency.

Each stereo frame becomes (op(left, right), op(right, left)); unary models act
on their respective lane. Inputs are all 256 ordered pairs of sixteen exact
binary fractions/integers. Float64 exactly represents these sums/products before
one binary32 rounding. Numeric zero is the functional gate; zero signs remain
visible in returned words for separate diagnostics. Pass and negation retain
an explicit raw-word definition.
"""
import struct

MODEL_NAMES = {
    35: 'add', 36: 'mul', 37: 'rsub', 38: 'absdiff', 39: 'neg',
    40: 'fabs', 41: 'pass', 42: 'neq', 43: 'gt', 44: 'gte', 45: 'lte',
    46: 'and', 47: 'or', 48: 'xor', 49: 'not', 50: 'boolnum',
}
MODELS = frozenset(MODEL_NAMES)


def word(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def value(word):
    return struct.unpack('<f', struct.pack('<I', word))[0]


# Both zero encodings are intentional, even though their numeric values agree.
WORDS = tuple(word(x) for x in (
    -4., -2., -1.5, -1., -.75, -.5, -.25, -0.,
    0., .25, .5, .75, 1., 1.5, 2., 4.,
))


def input_words(frames=256):
    if type(frames) is not int or not 1 <= frames <= 16384:
        raise ValueError('Invalid functional vector length')
    return tuple(w for frame in range(frames)
                 for w in (WORDS[(frame // 16) % 16], WORDS[frame % 16]))


def reference_words(model, inputs):
    if type(model) is not int or model not in MODELS:
        raise ValueError('Unknown stateless functional model')
    inputs = tuple(inputs)
    if not inputs or len(inputs) % 2 or len(inputs) > 32768:
        raise ValueError('Expected bounded stereo input words')
    for w in inputs:
        if (type(w) is not int or not 0 <= w <= 0xffffffff
                or (w & 0x7f800000) == 0x7f800000 or not -4 <= value(w) <= 4):
            raise ValueError('Expected finite binary32 inputs within [-4,4]')

    def operation(a, b):
        if model == 39:
            return a ^ 0x80000000
        if model == 40:
            return a & 0x7fffffff
        if model == 41:
            return a
        x, y = value(a), value(b)
        if model == 35:
            result = x + y
        elif model == 36:
            result = x * y
        elif model == 37:
            result = y - x
        elif model == 38:
            result = abs(x - y)
        elif model == 42:
            result = x != y
        elif model == 43:
            result = x > y
        elif model == 44:
            result = x >= y
        elif model == 45:
            result = x <= y
        elif model == 46:
            result = (x != 0) and (y != 0)
        elif model == 47:
            result = (x != 0) or (y != 0)
        elif model == 48:
            result = (x != 0) != (y != 0)
        elif model == 49:
            result = x == 0
        else:  # model 50: numeric boolean conversion, not a payload selector
            result = x != 0
        return word(result)

    return tuple(w for index in range(0, len(inputs), 2)
                 for w in (operation(inputs[index], inputs[index + 1]),
                           operation(inputs[index + 1], inputs[index])))
