# SPDX-License-Identifier: MIT
"""Independent finite-input references for short RNBO numeric smoke checks.

Simple models compare exactly, treating zero signs as separate diagnostics.
Models 66..75 compare with a predeclared absolute tolerance 2e-6 against the
once-binary32-rounded mathematical reference. Their case inputs keep outputs
within[-8,8]. This is a short functional check, without nonfinite/fenv claims.

Primary object definitions: RNBO1.4.4 object XML and public object references
https://rnbo.cycling74.com/objects/ref/ . Round's tie policy is explicitly
nearest-away-from-zero; fract/mod use signed remainder with truncating quotient.
These policies are declared rather than inferred from generated algorithms.
"""
from fractions import Fraction
import math
import struct

MODEL_NAMES = {
    51: 'div', 52: 'rdiv', 53: 'mod', 54: 'rmod', 55: 'floor',
    56: 'ceil', 57: 'trunc', 58: 'round', 59: 'fract', 60: 'sign',
    61: 'isnan', 62: 'fixnan', 63: 'isdenorm', 64: 'fixdenorm',
    65: 'intnum', 66: 'sqrt', 67: 'cbrt', 68: 'exp', 69: 'exp2',
    70: 'expm1', 71: 'log', 72: 'log2', 73: 'log10', 74: 'log1p',
    75: 'pow',
}
MODELS = frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES = {model: 2e-6 if model >= 66 else 0 for model in MODELS}
REFERENCE_POLICIES = {
    53: 'signed-remainder-truncating-quotient',
    54: 'reversed-signed-remainder-truncating-quotient',
    58: 'nearest-integer-ties-away-from-zero',
    59: 'signed-fraction-convention',
    60: 'sign-zero-returns-itself',
    61: 'finite-inputs-only', 62: 'finite-inputs-only',
    63: 'binary32-subnormal-predicate', 64: 'binary32-subnormal-to-zero',
}


def word(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def value(word):
    return struct.unpack('<f', struct.pack('<I', word))[0]


# Wide basic-function domain: all inputs are safe for a signed32-bit conversion.
# Include neighbors of quarter/half/integer values and both subnormal signs.
MAGNITUDES = (
    0, 1, 2, 0x003fffff, 0x00400000, 0x007ffffe, 0x007fffff, 0x00800000, 0x00800001,
    0x3e7fffff, 0x3e800000, 0x3e800001, 0x3effffff, 0x3f000000, 0x3f000001,
    0x3f400000, 0x3f7fffff, 0x3f800000, 0x3f800001, 0x3fbfffff, 0x3fc00000, 0x3fc00001,
    0x3fffffff, 0x40000000, 0x40000001, 0x407fffff, 0x40800000, 0x40800001,
    0x4a7fffff, 0x4a800000, 0x4a800001, 0x4affffff, 0x4b000000, 0x4b000001,
    0x4b7fffff, 0x4b800000, 0x4b800001, 0x4effffff,
)
WORDS = (*MAGNITUDES, *(w | 0x80000000 for w in MAGNITUDES), 0xcf000000)

# Both operands must be nonzero for forward and reverse division/remainder.
DIVISORS = tuple(word(x) for x in (
    -8., -4., -2., -1., -.5, -.25, -.125, -.0625,
    .0625, .125, .25, .5, 1., 2., 4., 8.,
))
SQRT_INPUTS = tuple(word(x) for x in (
    0., .015625, .0625, .125, .25, .375, .5, .75, 1., 1.25, 1.5, 2., 2.25, 2.5, 3., 4.,
))
CBRT_INPUTS = tuple(word(x) for x in (
    -4., -3.375, -2., -1., -.5, -.125, -0., 0., .125, .5, 1., 2., 3.375, 4.,
))
EXP_INPUTS = tuple(word(x) for x in (
    -2., -1.5, -1., -.75, -.5, -.25, -.125, -0.,
    0., .125, .25, .5, .75, 1., 1.5, 2.,
))
LOG_INPUTS = tuple(word(x) for x in (
    .125, .15625, .1875, .25, .3125, .375, .5, .625, .75, 1., 1.25, 1.5, 2., 2.5, 3., 4.,
))
LOG1P_INPUTS = tuple(word(x) for x in (
    -.75, -.5, -.25, -.125, -.0625, -0., 0., .0625,
    .125, .25, .5, .75, 1., 1.25, 1.5, 2.,
))
POWER_INPUTS = tuple(word(n / 8) for n in range(1, 17))


def _frames(frames):
    if type(frames) is not int or not 1 <= frames <= 16384:
        raise ValueError('Invalid functional vector length')


def _model(model):
    if type(model) is not int or model not in MODELS:
        raise ValueError('Unknown numeric functional model')


def input_words(frames=256):
    _frames(frames)
    return tuple(w for n in range(frames)
                 for w in (WORDS[n % len(WORDS)], WORDS[(n + 29) % len(WORDS)]))


def case_input_words(model, frames=256):
    _model(model)
    _frames(frames)
    if model in (51, 52, 53, 54):
        words = DIVISORS
    elif model == 66:
        words = SQRT_INPUTS
    elif model == 67:
        words = CBRT_INPUTS
    elif model in (68, 69, 70):
        words = EXP_INPUTS
    elif model in (71, 72, 73):
        words = LOG_INPUTS
    elif model == 74:
        words = LOG1P_INPUTS
    elif model == 75:
        words = POWER_INPUTS
    else:
        return input_words(frames)
    # Binary cases cover the full ordered16x16 grid in256 frames. Unary
    # cases need each lane's entire value set; the same grid supplies it.
    return tuple(w for n in range(frames)
                 for w in (words[(n // len(words)) % len(words)], words[n % len(words)]))


def _signed_remainder(x, y):
    quotient = math.trunc(Fraction(x) / Fraction(y))
    remainder = Fraction(x) - quotient * Fraction(y)
    return math.copysign(0., x) if not remainder else float(remainder)


def _nearest_away(x):
    magnitude = abs(Fraction(x))
    integer = (2 * magnitude.numerator + magnitude.denominator) // (2 * magnitude.denominator)
    return math.copysign(float(integer), x)


def reference_words(model, inputs):
    _model(model)
    inputs = tuple(inputs)
    if not inputs or len(inputs) % 2 or len(inputs) > 32768:
        raise ValueError('Expected bounded stereo input words')
    for w in inputs:
        if (type(w) is not int or not 0 <= w <= 0xffffffff or (w & 0x7f800000) == 0x7f800000
                or not -2147483648 <= value(w) <= 2147483520):
            raise ValueError('Expected finite inputs in the common signed32-bit-safe domain')
        x = value(w)
        if model in (51, 52, 53, 54) and x == 0:
            raise ValueError('Both operands must be nonzero for forward/reverse operations')
        if model == 66 and not 0 <= x <= 4:
            raise ValueError('Square-root smoke domain is[0,4]')
        if model == 67 and not -4 <= x <= 4:
            raise ValueError('Cube-root smoke domain is[-4,4]')
        if model in (68, 69, 70) and not -2 <= x <= 2:
            raise ValueError('Exponential smoke domain is[-2,2]')
        if model in (71, 72, 73) and not .125 <= x <= 4:
            raise ValueError('Logarithm smoke domain is[.125,4]')
        if model == 74 and not -.75 <= x <= 2:
            raise ValueError('Log1p smoke domain is[-.75,2]')
        if model == 75 and not .125 <= x <= 2:
            raise ValueError('Power smoke domain is[.125,2]for both operands')

    def operation(a, b):
        x, y = value(a), value(b)
        if model == 60:
            return a if x == 0 else word(1. if x > 0 else -1.)
        if model == 61:
            return 0  # all admitted inputs are finite; NaN handling is not tested
        if model == 62:
            return a  # finite-only identity, with no claim about nonfinite replacement
        if model in (63, 64):
            subnormal = (a & 0x7f800000) == 0 and (a & 0x007fffff) != 0
            return word(subnormal) if model == 63 else (0 if subnormal else a)
        if model == 51:
            result = x / y
        elif model == 52:
            result = y / x
        elif model == 53:
            result = _signed_remainder(x, y)
        elif model == 54:
            result = _signed_remainder(y, x)
        elif model == 55:
            result = math.floor(x)
        elif model == 56:
            result = math.ceil(x)
        elif model in (57, 65):
            result = math.trunc(x)
        elif model == 58:
            result = _nearest_away(x)
        elif model == 59:
            result = _signed_remainder(x, 1.)
        elif model == 66:
            result = math.sqrt(x)
        elif model == 67:
            result = math.copysign(abs(x) ** (1. / 3.), x)
        elif model == 68:
            result = math.exp(x)
        elif model == 69:
            result = 2. ** x
        elif model == 70:
            result = math.expm1(x)
        elif model == 71:
            result = math.log(x)
        elif model == 72:
            result = math.log2(x)
        elif model == 73:
            result = math.log10(x)
        elif model == 74:
            result = math.log1p(x)
        else:
            result = math.pow(x, y)
        return word(result)

    return tuple(w for n in range(0, len(inputs), 2)
                 for w in (operation(inputs[n], inputs[n + 1]), operation(inputs[n + 1], inputs[n])))
