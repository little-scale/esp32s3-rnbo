# SPDX-License-Identifier: MIT
"""Independent finite GenExpr mathematics for short smoke vectors.

No generated algorithm supplies these expected values. Gen's documented
opposite/adjacent atan2 inputs mean atan2(first, second); both operands are
nonzero in this batch. Division/remainder operands are also nonzero. Remainder
uses a truncating quotient and the dividend's sign. Other binary outputs reverse
arguments; unary functions operate independently on each input lane.

Models76..80 use exact binary32 comparisons (zero signs remain diagnostics).
Models81..103 use a fixed2e-6 absolute tolerance against once-binary32-rounded
Float64 mathematical references. All approximate outputs are bounded by8 in
magnitude by the declared case inputs. No nonfinite/fenv or full-domain accuracy
claim, and no qualification is inherited from similarly named RNBO objects.
"""
from fractions import Fraction
import math
import struct

MODEL_NAMES = {
    76: 'div', 77: 'rdiv', 78: 'mod', 79: 'rmod', 80: 'rsub',
    81: 'sqrt', 82: 'exp', 83: 'exp2', 84: 'log', 85: 'log2',
    86: 'log10', 87: 'pow', 88: 'sin', 89: 'cos', 90: 'tan',
    91: 'tanh', 92: 'asin', 93: 'acos', 94: 'atan', 95: 'atan2',
    96: 'sinh', 97: 'cosh', 98: 'asinh', 99: 'acosh', 100: 'atanh',
    101: 'hypot', 102: 'degrees', 103: 'radians',
}
MODELS = frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES = {model: 0 if model <= 80 else 2e-6 for model in MODELS}
REFERENCE_POLICIES = {
    76: 'gen-nonzero-divisors', 77: 'gen-reversed-nonzero-divisors',
    78: 'gen-signed-remainder-truncating-quotient',
    79: 'gen-reversed-signed-remainder-truncating-quotient',
    80: 'gen-right-minus-left',
    95: 'gen-atan2-opposite-adjacent-nonzero-operands',
    102: 'gen-radians-to-degrees', 103: 'gen-degrees-to-radians',
}


def word(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def value(word):
    return struct.unpack('<f', struct.pack('<I', word))[0]


def _words(values):
    return tuple(word(x) for x in values)


WORDS = _words((-4., -2., -1.5, -1., -.75, -.5, -.25, -0.,
                0., .25, .5, .75, 1., 1.5, 2., 4.))
DIVISORS = _words((-8., -4., -2., -1., -.5, -.25, -.125, -.0625,
                  .0625, .125, .25, .5, 1., 2., 4., 8.))
SQRT_INPUTS = _words((0., .015625, .0625, .125, .25, .375, .5, .75,
                      1., 1.25, 1.5, 2., 2.25, 2.5, 3., 4.))
EXP_INPUTS = _words((-2., -1.5, -1., -.75, -.5, -.25, -.125, -0.,
                     0., .125, .25, .5, .75, 1., 1.5, 2.))
LOG_INPUTS = _words((.125, .15625, .1875, .25, .3125, .375, .5, .625,
                     .75, 1., 1.25, 1.5, 2., 2.5, 3., 4.))
POWER_INPUTS = _words(n / 8 for n in range(1, 17))
UNIT_INPUTS = _words((-1., -.875, -.75, -.5, -.25, -.125, -.0625, -0.,
                      0., .0625, .125, .25, .5, .75, .875, 1.))
ATANH_INPUTS = _words((-.75, -.625, -.5, -.375, -.25, -.125, -.0625, -0.,
                       0., .0625, .125, .25, .375, .5, .625, .75))
ACOSH_INPUTS = _words(1 + n / 16 for n in range(16))
ANGLE_RADIANS = _words((-.125, -.09375, -.0625, -.046875, -.03125, -.015625, -.0078125, -0.,
                        0., .0078125, .015625, .03125, .046875, .0625, .09375, .125))
ANGLE_DEGREES = _words((-180., -135., -90., -60., -45., -30., -15., -0.,
                        0., 15., 30., 45., 60., 90., 135., 180.))

# Public, explicit domains prevent invalid arguments from becoming fabricated
# finite expectations. Source vectors, not captured DSP outputs, choose them.
DOMAINS = {model: (-1., 1.) for model in range(88, 99)}
DOMAINS.update({**{model: (-8., 8.) for model in (76, 77, 78, 79, 95)},
                80: (-4., 4.), 81: (0., 4.), 82: (-2., 2.), 83: (-2., 2.),
                84: (.125, 4.), 85: (.125, 4.), 86: (.125, 4.), 87: (.125, 2.),
                99: (1., 2.), 100: (-.75, .75), 101: (-4., 4.),
                102: (-.125, .125), 103: (-180., 180.)})


def _model(model):
    if type(model) is not int or model not in MODELS:
        raise ValueError('Unknown Gen mathematical smoke model')


def _frames(frames):
    if type(frames) is not int or not 1 <= frames <= 16384:
        raise ValueError('Invalid functional vector length')


def _grid(words, frames):
    return tuple(w for n in range(frames)
                 for w in (words[(n // len(words)) % len(words)], words[n % len(words)]))


def input_words(frames=256):
    _frames(frames)
    return _grid(WORDS, frames)


def case_input_words(model, frames=256):
    _model(model)
    _frames(frames)
    if model in (76, 77, 78, 79, 95):
        words = DIVISORS
    elif model == 80 or model == 101:
        words = WORDS
    elif model == 81:
        words = SQRT_INPUTS
    elif model in (82, 83):
        words = EXP_INPUTS
    elif model in (84, 85, 86):
        words = LOG_INPUTS
    elif model == 87:
        words = POWER_INPUTS
    elif model == 99:
        words = ACOSH_INPUTS
    elif model == 100:
        words = ATANH_INPUTS
    elif model == 102:
        words = ANGLE_RADIANS
    elif model == 103:
        words = ANGLE_DEGREES
    else:
        words = UNIT_INPUTS
    return _grid(words, frames)


def _remainder(x, y):
    quotient = math.trunc(Fraction(x) / Fraction(y))
    result = Fraction(x) - quotient * Fraction(y)
    return math.copysign(0., x) if not result else float(result)


def reference_words(model, inputs):
    _model(model)
    inputs = tuple(inputs)
    if not inputs or len(inputs) % 2 or len(inputs) > 32768:
        raise ValueError('Expected bounded stereo input words')
    low, high = DOMAINS[model]
    for w in inputs:
        if (type(w) is not int or not 0 <= w <= 0xffffffff
                or (w & 0x7f800000) == 0x7f800000 or not low <= value(w) <= high):
            raise ValueError('Input is outside this Gen mathematical smoke domain')
        if model in (76, 77, 78, 79, 95) and value(w) == 0:
            raise ValueError('Both operands must be nonzero for this case')

    def operation(a, b):
        x, y = value(a), value(b)
        if model == 76:
            result = x / y
        elif model == 77:
            result = y / x
        elif model == 78:
            result = _remainder(x, y)
        elif model == 79:
            result = _remainder(y, x)
        elif model == 80:
            result = y - x
        elif model == 81:
            result = math.sqrt(x)
        elif model == 82:
            result = math.exp(x)
        elif model == 83:
            result = 2. ** x
        elif model == 84:
            result = math.log(x)
        elif model == 85:
            result = math.log2(x)
        elif model == 86:
            result = math.log10(x)
        elif model == 87:
            result = math.pow(x, y)
        elif model == 88:
            result = math.sin(x)
        elif model == 89:
            result = math.cos(x)
        elif model == 90:
            result = math.tan(x)
        elif model == 91:
            result = math.tanh(x)
        elif model == 92:
            result = math.asin(x)
        elif model == 93:
            result = math.acos(x)
        elif model == 94:
            result = math.atan(x)
        elif model == 95:
            result = math.atan2(x, y)
        elif model == 96:
            result = math.sinh(x)
        elif model == 97:
            result = math.cosh(x)
        elif model == 98:
            result = math.asinh(x)
        elif model == 99:
            result = math.acosh(x)
        elif model == 100:
            result = math.atanh(x)
        elif model == 101:
            result = math.hypot(x, y)
        elif model == 102:
            result = math.degrees(x)
        else:
            result = math.radians(x)
        return word(result)

    return tuple(w for n in range(0, len(inputs), 2)
                 for w in (operation(inputs[n], inputs[n + 1]), operation(inputs[n + 1], inputs[n])))
