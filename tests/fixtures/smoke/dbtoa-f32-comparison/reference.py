# SPDX-License-Identifier: MIT
"""Independent bounded dbtoa comparison reference: y = 10 ** (binary32_input / 20).

No generated DSP or candidate powf implementation is used as the oracle.
Decimal transcendental evaluation is checked at two precisions; direct exact
distance rounding avoids converting the high-precision result through binary64.
This is a bounded experimental reference, not an exhaustive rounding proof.
"""
from decimal import Decimal, localcontext
from functools import lru_cache
import math
import struct

LOW, HIGH = -24.0, 6.0
FRAMES = 256
ABSOLUTE_LIMIT = 2e-6
MUSICAL_DB = (-24., -21., -18., -15., -12., -9., -6., -3., -0., 0., 1., 2., 3., 4., 5., 6.)


def word(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def value(bits):
    if type(bits) is not int or not 0 <= bits <= 0xffffffff:
        raise ValueError('Expected one binary32 word')
    return struct.unpack('<f', struct.pack('<I', bits))[0]


def exact(bits):
    return Decimal.from_float(value(bits))


def round_decimal(value):
    """Nearest/even binary32, by exact decimal distances to adjacent values."""
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError('Expected a finite Decimal')
    sign = 0x80000000 if value.is_signed() else 0
    magnitude = value.copy_abs()
    if magnitude > exact(0x7f7fffff):
        raise ValueError('Reference rounding supports finite binary32 range only')
    low, high = 0, 0x7f7fffff
    while low < high:
        middle = (low + high + 1) // 2
        if exact(middle) <= magnitude:
            low = middle
        else:
            high = middle - 1
    if exact(low) == magnitude or low == 0x7f7fffff:
        return sign | low
    # Decimal subtraction itself must be exact even for a subnormal midpoint.
    with localcontext() as context:
        context.prec = max(200, len(magnitude.as_tuple().digits) + 200)
        below, above = magnitude - exact(low), exact(low + 1) - magnitude
    result = low if below < above or (below == above and low % 2 == 0) else low + 1
    return sign | result


def checked_input(bits):
    number = value(bits)
    if not math.isfinite(number) or not LOW <= number <= HIGH:
        raise ValueError('dbtoa corpus requires finite binary32 input in [-24, 6]')
    return number


@lru_cache(maxsize=None)
def reference_word(bits, precision=120):
    checked_input(bits)
    if type(precision) is not int or precision < 60:
        raise ValueError('Reference precision must be at least sixty decimal digits')
    with localcontext() as context:
        context.prec = precision
        ideal = (exact(bits) * Decimal(10).ln() / Decimal(20)).exp()
    return round_decimal(ideal)


def reference_words(inputs, precision=120):
    inputs = tuple(inputs)
    if len(inputs) != FRAMES * 2:
        raise ValueError('Expected one interleaved stereo 256-frame vector')
    return tuple(reference_word(bits, precision) for bits in inputs)


def ulp_distance_positive(actual, expected):
    """Diagnostic rank distance only; dbtoa outputs are positive and normal."""
    a, e = value(actual), value(expected)
    if not math.isfinite(a) or not math.isfinite(e) or a <= 0 or e <= 0:
        raise ValueError('ULP diagnostic requires finite positive outputs')
    return abs(actual - expected)


def neighbors(bits):
    if bits & 0x7fffffff == 0:
        return (0x80000001, bits, 1)
    return (bits + 1, bits, bits - 1) if bits & 0x80000000 else (bits - 1, bits, bits + 1)


def _pad(words):
    words = tuple(words)
    if not words or len(words) > FRAMES * 2:
        raise ValueError('Corpus seed does not fit one stereo vector')
    for bits in words:
        checked_input(bits)
    return tuple(words[n % len(words)] for n in range(FRAMES * 2))


def corpus():
    musical = tuple(word(x) for x in MUSICAL_DB)
    published = tuple(w for n in range(FRAMES)
                      for w in (musical[(n // 16) % 16], musical[n % 16]))
    boundary = [0x80000000, 0, 0x80000001, 1, 0x807fffff, 0x007fffff,
                0x80800000, 0x00800000]
    for number in (-24., -21., -20., -18., -15., -12., -9., -6., -3., -1., 0., 1., 2., 3., 4., 5., 6.):
        boundary.extend(bits for bits in neighbors(word(number)) if LOW <= value(bits) <= HIGH)
    dense = tuple(word(LOW + k / 16) for k in range(481))
    # Pick output rounding boundaries independently of any pow/powf result.
    # The exact midpoint of adjacent output words is inverted using logarithms;
    # the three neighboring binary32 dB inputs around each preimage are tested.
    lower = reference_word(word(LOW))
    upper = reference_word(word(HIGH))
    midpoint_words, anchors = [], []
    with localcontext() as context:
        context.prec = 160
        for n in range(64):
            output = lower + (upper - lower - 1) * n // 63
            midpoint = (exact(output) + exact(output + 1)) / 2
            db = Decimal(20) * midpoint.ln() / Decimal(10).ln()
            around = tuple(bits for bits in neighbors(round_decimal(db)) if LOW <= value(bits) <= HIGH)
            midpoint_words.extend(around)
            anchors.append({'lower_output_word': f'{output:08x}',
                            'upper_output_word': f'{output + 1:08x}',
                            'input_words': [f'{bits:08x}' for bits in around]})
    return ({'published-musical-grid': published,
             'boundary-neighbors': _pad(boundary),
             'dense-sixteenth-db': _pad(dense),
             'output-midpoint-neighbors': _pad(midpoint_words)}, anchors)


# Frozen before any candidate execution. These files are original input vectors,
# not generated DSP. Every expected output is computed from the math above.
from pathlib import Path
import hashlib

MODEL_CASES = {900: 'published-musical-grid', 901: 'boundary-neighbors',
               902: 'dense-sixteenth-db', 903: 'output-midpoint-neighbors'}
ABSOLUTE_TOLERANCES = {model: ABSOLUTE_LIMIT for model in MODEL_CASES}
REFERENCE_POLICIES = {model: 'independent-10-power-exact-binary32-db-over20' for model in MODEL_CASES}
VECTOR_SHA256 = {'published-musical-grid': 'a576426a1cb9f58b06e6abd96e5c5efda62057ecb85264be4b88d305277c835d', 'boundary-neighbors': '9724e80004451de6b4fff3190e457070b74e9e3504e7a907e16288bc9c211a6e', 'dense-sixteenth-db': '8f7b85d217b9c57d859571b3f39eecd4b827257f67f0740be4fb6d208fceeca2', 'output-midpoint-neighbors': '836785fc1c738ac62227d8265262ca6318e869a8c8e657c1a11757b3d87dc54a'}


def case_input_words(model, frames=256):
    if type(model) is not int or model not in MODEL_CASES or type(frames) is not int or frames != FRAMES:
        raise ValueError('dbtoa comparison requires one known 256-frame model')
    name = MODEL_CASES[model]
    data = (Path(__file__).resolve().parent / 'vectors' / (name + '.input.f32')).read_bytes()
    if len(data) != 2048 or hashlib.sha256(data).hexdigest() != VECTOR_SHA256[name]:
        raise ValueError('Frozen dbtoa input vector changed')
    return struct.unpack('<512I', data)


def input_words(frames=256):
    return case_input_words(900, frames)
