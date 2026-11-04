# SPDX-License-Identifier: MIT
"""Independent mathematical references for short RNBO function/conversion checks.

Case domains and tolerances are fixed before execution. Musical conversion uses
12-tone equal temperament, default A4=440Hz/ref69, and ftom's documented default
round=true. Amplitude decibels use unity gain as0dB:20log10(a), inverse10^(d/20).
Time/frequency conversions use the fixed44100Hz sample rate. Constant radtodeg
and degtorad forms ignore the two declared FX inputs; they are not converters.

All nonconstant functions compare against once-binary32-rounded Float64 ideal
mathematics. Fast sine/cosine/tangent's1e-3 is an explicit basic smoke threshold,
not a documented accuracy guarantee. Taylor cosine vectors use small arguments
(or small arguments after period wrapping), not its full possible range. No
nonfinite/fenv claim or evidence inheritance from Gen/RNBO sibling spellings.
"""
import math
import struct

RATE = 44100
MODEL_NAMES = {
    115: 'sin', 116: 'cos', 117: 'tan', 118: 'tanh', 119: 'asin',
    120: 'acos', 121: 'atan', 122: 'atan2', 123: 'sinh', 124: 'cosh',
    125: 'asinh', 126: 'acosh', 127: 'atanh', 128: 'hypot',
    129: 'degrees', 130: 'radians', 131: 'radtodeg-constant', 132: 'degtorad-constant',
    133: 'mtof-default-tuning', 134: 'ftom-default-rounded',
    135: 'atodb-unity-reference', 136: 'dbtoa-unity-reference',
    137: 'mstosamps', 138: 'sampstoms', 139: 'hztoms', 140: 'mstohz',
    141: 'hztosamps', 142: 'sampstohz',
    143: 'fastsin', 144: 'fastcos', 145: 'fasttan', 146: 'cosT8', 147: 'cosT8safe',
}
MODELS = frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES = {model: 2e-6 for model in MODELS}
ABSOLUTE_TOLERANCES.update({131: 0, 132: 0, 133: 5e-4, 134: 0,
                            137: 5e-4, 138: 5e-4, 139: 5e-4, 140: 5e-4,
                            141: 5e-4, 142: 5e-4,
                            143: 1e-3, 144: 1e-3, 145: 1e-3})
REFERENCE_POLICIES = {
    122: 'rnbo-atan2-first-opposite-second-adjacent',
    131: 'rnbo-constant-180-over-pi-no-input', 132: 'rnbo-constant-pi-over180-no-input',
    133: 'rnbo-equal-temperament-ref69-base440-5e-4Hz-smoke',
    134: 'rnbo-default-nearest-integer-midi-no-halfway-inputs',
    135: 'rnbo-amplitude-decibels-relative-to-unity',
    136: 'rnbo-decibels-relative-to-unity-to-amplitude',
    137: 'rnbo-44100Hz-ms-to-samples-5e-4samples-smoke',
    138: 'rnbo-44100Hz-samples-to-ms-5e-4ms-smoke',
    139: 'rnbo-Hz-to-ms-5e-4ms-smoke',
    140: 'rnbo-ms-to-Hz-5e-4Hz-smoke',
    141: 'rnbo-44100Hz-frequency-to-sample-period-5e-4samples-smoke',
    142: 'rnbo-44100Hz-sample-period-to-frequency-5e-4Hz-smoke',
    143: 'ideal-sine-smoke-threshold-not-fast-accuracy-promise',
    144: 'ideal-cosine-smoke-threshold-not-fast-accuracy-promise',
    145: 'ideal-tangent-smoke-threshold-not-fast-accuracy-promise',
    146: 'ideal-cosine-small-angle-taylor-domain',
    147: 'ideal-cosine-small-reduced-angle-period-wrap-domain',
}


def word(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def value(word):
    return struct.unpack('<f', struct.pack('<I', word))[0]


def _words(values):
    return tuple(word(x) for x in values)


UNIT = _words((-1., -.875, -.75, -.5, -.25, -.125, -.0625, -0.,
               0., .0625, .125, .25, .5, .75, .875, 1.))
NONZERO = _words((-8., -4., -2., -1., -.5, -.25, -.125, -.0625,
                  .0625, .125, .25, .5, 1., 2., 4., 8.))
WIDE = _words((-4., -2., -1.5, -1., -.75, -.5, -.25, -0.,
               0., .25, .5, .75, 1., 1.5, 2., 4.))
ACOSH = _words(1 + n / 16 for n in range(16))
ATANH = _words((-.75, -.625, -.5, -.375, -.25, -.125, -.0625, -0.,
                0., .0625, .125, .25, .375, .5, .625, .75))
ANGLE_RADIANS = _words((-.125, -.09375, -.0625, -.046875, -.03125, -.015625, -.0078125, -0.,
                        0., .0078125, .015625, .03125, .046875, .0625, .09375, .125))
ANGLE_DEGREES = _words((-180., -135., -90., -60., -45., -30., -15., -0.,
                        0., 15., 30., 45., 60., 90., 135., 180.))
MIDI = _words((36., 48., 55., 57., 60., 60.25, 61., 64., 67., 69., 69.25, 70., 72., 76., 81., 84.))
# Practical note centres and quarter-semitone offsets, safely away from .5 ties.
FREQUENCIES = _words(440. * 2. ** ((note - 69.) / 12.) for note in
                     (48., 48.25, 55., 55.25, 57., 59.75, 60., 60.25,
                      64., 66.75, 67., 68.75, 69., 69.25, 72., 81.))
AMPLITUDES = _words((.5, .5625, .625, .6875, .75, .8125, .875, .9375,
                     1., 1.0625, 1.125, 1.25, 1.375, 1.5, 1.75, 2.))
DECIBELS = _words((-24., -21., -18., -15., -12., -9., -6., -3., -0., 0., 1., 2., 3., 4., 5., 6.))
MILLISECONDS = _words((0., .125, .25, .5, 1., 1.5, 2., 5., 10., 20., 50., 100., 125., 250., 500., 1000.))
SAMPLES = _words((0., 1., 2., 4., 8., 16., 32., 64., 128., 256., 441., 4410., 11025., 22050., 33075., 44100.))
HZ_PERIODS = _words((1., 2., 10., 20., 55., 110., 220., 440.,
                     880., 1000., 2000., 4000., 6000., 8000., 12000., 20000.))
MS_PERIODS = _words((.125, .25, .5, 1., 1.5, 2., 5., 10.,
                     20., 50., 100., 125., 250., 500., 1000., 2000.))
FREQUENCY_PERIODS = _words((1., 2., 10., 20., 55., 110., 220., 440.,
                            880., 1000., 2000., 4000., 5512.5, 11025., 22050., 44100.))
SAMPLE_PERIODS = _words((1., 2., 4., 8., 16., 32., 64., 128.,
                         256., 441., 4410., 5512.5, 11025., 22050., 33075., 44100.))
TAYLOR_SAFE = _words((-6.75, -6.5, -6.25, -6., -.5, -.25, -.125, -0.,
                      0., .125, .25, .5, 6., 6.25, 6.5, 6.75))
CASE_WORDS = {model: UNIT for model in MODELS}
CASE_WORDS.update({122: NONZERO, 126: ACOSH, 127: ATANH, 128: WIDE,
                   129: ANGLE_RADIANS, 130: ANGLE_DEGREES, 133: MIDI, 134: FREQUENCIES,
                   135: AMPLITUDES, 136: DECIBELS, 137: MILLISECONDS, 138: SAMPLES,
                   139: HZ_PERIODS, 140: MS_PERIODS, 141: FREQUENCY_PERIODS, 142: SAMPLE_PERIODS,
                   147: TAYLOR_SAFE})
DOMAINS = {model: (-1., 1.) for model in MODELS}
DOMAINS.update({122: (-8., 8.), 126: (1., 2.), 127: (-.75, .75), 128: (-4., 4.),
                129: (-.125, .125), 130: (-180., 180.), 133: (36., 84.), 134: (100., 1000.),
                135: (.5, 2.), 136: (-24., 6.), 137: (0., 1000.), 138: (0., 44100.),
                139: (1., 20000.), 140: (.125, 2000.),
                141: (1., 44100.), 142: (1., 44100.), 147: (-6.75, 6.75)})


def _model(model):
    if type(model) is not int or model not in MODELS:
        raise ValueError('Unknown RNBO function smoke model')


def _grid(words, frames):
    if type(frames) is not int or not 1 <= frames <= 16384:
        raise ValueError('Invalid functional vector length')
    return tuple(w for n in range(frames)
                 for w in (words[(n // len(words)) % len(words)], words[n % len(words)]))


def input_words(frames=256):
    return _grid(UNIT, frames)


def case_input_words(model, frames=256):
    _model(model)
    return _grid(CASE_WORDS[model], frames)


def reference_words(model, inputs):
    _model(model)
    inputs = tuple(inputs)
    if not inputs or len(inputs) % 2 or len(inputs) > 32768:
        raise ValueError('Expected bounded stereo input words')
    low, high = DOMAINS[model]
    for w in inputs:
        if (type(w) is not int or not 0 <= w <= 0xffffffff
                or (w & 0x7f800000) == 0x7f800000 or not low <= value(w) <= high):
            raise ValueError('Input outside the authored RNBO function smoke domain')
        if model == 122 and value(w) == 0:
            raise ValueError('Atan2 smoke operands are both nonzero')
        if model == 147 and abs(math.remainder(value(w), 2 * math.pi)) > 1:
            raise ValueError('Taylor-safe smoke uses only small reduced angles')

    def operation(a, b):
        x, y = value(a), value(b)
        if model in (115, 143): result = math.sin(x)
        elif model in (116, 144, 146, 147): result = math.cos(x)
        elif model in (117, 145): result = math.tan(x)
        elif model == 118: result = math.tanh(x)
        elif model == 119: result = math.asin(x)
        elif model == 120: result = math.acos(x)
        elif model == 121: result = math.atan(x)
        elif model == 122: result = math.atan2(x, y)
        elif model == 123: result = math.sinh(x)
        elif model == 124: result = math.cosh(x)
        elif model == 125: result = math.asinh(x)
        elif model == 126: result = math.acosh(x)
        elif model == 127: result = math.atanh(x)
        elif model == 128: result = math.hypot(x, y)
        elif model == 129: result = math.degrees(x)
        elif model == 130: result = math.radians(x)
        elif model == 131: result = 180. / math.pi
        elif model == 132: result = math.pi / 180.
        elif model == 133: result = 440. * 2. ** ((x - 69.) / 12.)
        elif model == 134: result = math.floor(69. + 12. * math.log2(x / 440.) + .5)
        elif model == 135: result = 20. * math.log10(x)
        elif model == 136: result = 10. ** (x / 20.)
        elif model == 137: result = x * RATE / 1000.
        elif model == 138: result = x * 1000. / RATE
        elif model in (139, 140): result = 1000. / x
        else: result = RATE / x  #141 Hz→samples;142 sample period→Hz
        return word(result)

    return tuple(w for n in range(0, len(inputs), 2)
                 for w in (operation(inputs[n], inputs[n + 1]), operation(inputs[n + 1], inputs[n])))
