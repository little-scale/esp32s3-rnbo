# SPDX-License-Identifier: MIT
"""Independent ASCII references for 85 exact RNBO codebox named values.

The character definitions, not generated C++ or captured outputs, determine
ord(character). The left output is that exactly representable integer; the
right output is the original input word, including subnormals and zero signs.
These are bare codebox names, not patcher objects or strings.
"""
import math
import string
import struct

PUNCTUATION = {
    'SPACE': ' ', 'BANG': '!', 'QUOTE': '"', 'HASH': '#', 'DOLLAR': '$',
    'PERCENT': '%', 'AMP': '&', 'APOS': "'", 'LPAREN': '(', 'RPAREN': ')',
    'AST': '*', 'PLUS': '+', 'COMMA': ',', 'HYPHEN': '-', 'PERIOD': '.',
    'SLASH': '/', 'COLON': ':', 'SEMI': ';', 'LT': '<', 'EQUALS': '=',
    'GT': '>', 'QUEST': '?', 'AT': '@', 'LBRACKET': '[', 'BACKSLASH': '\\',
    'RBRACKET': ']', 'CARET': '^', 'UNDERSCORE': '_', 'BACKTICK': '`',
    'LCURLY': '{', 'PIPE': '|', 'RCURLY': '}', 'TILDE': '~',
}
CHARACTERS = {'CHAR_'+suffix: char for suffix, char in PUNCTUATION.items()}
CHARACTERS.update({'CHAR_'+char: char for char in string.ascii_letters})
EXACT_NAMES = tuple(sorted(CHARACTERS))
MODEL_NAMES = {1000+i: name for i, name in enumerate(EXACT_NAMES)}
MODELS = frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES = {model: 0 for model in MODELS}
STRICT_ZERO_SIGN_CHANNELS = 2  # Bit 1: right input-word observer.
REFERENCE_CALL_COUNT = 20


def word(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def value(bits):
    return struct.unpack('<f', struct.pack('<I', bits))[0]


# Symmetric finite pilot grid, including both zero signs and binary32 boundaries.
PILOT_WORDS = (word(-4), word(-2), word(-1), word(-.5), 0x80800000, 0x807fffff,
               0x80000001, 0x80000000, 0, 1, 0x007fffff, 0x00800000,
               word(.5), word(1), word(2), word(4))


def _model(model):
    if type(model) is not int or model not in MODELS:
        raise ValueError('Unknown exact RNBO character constant')


def input_words(frames=256):
    if type(frames) is not int or not 1 <= frames <= 16384:
        raise ValueError('Invalid finite stereo vector length')
    return tuple(w for frame in range(frames)
                 for w in (PILOT_WORDS[(frame//16)%16], PILOT_WORDS[frame%16]))


def case_input_words(model, frames=256):
    _model(model)
    return input_words(frames)


def reference_words(model, inputs):
    _model(model); inputs = tuple(inputs)
    if not inputs or len(inputs)%2 or len(inputs)>32768:
        raise ValueError('Expected bounded interleaved stereo input')
    if any(type(w) is not int or not 0 <= w <= 0xffffffff or
           (w & 0x7f800000) == 0x7f800000 or abs(value(w)) > 4 for w in inputs):
        raise ValueError('Expected finite binary32 input in [-4,4]')
    constant = word(ord(CHARACTERS[MODEL_NAMES[model]]))
    return tuple(w for n in range(0,len(inputs),2) for w in (constant,inputs[n+1]))
