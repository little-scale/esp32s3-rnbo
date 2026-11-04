# SPDX-License-Identifier: MIT
"""Predeclared continuous Gen phase, reset, multiplication and delay models.

Fresh initialization precedes twenty 256-frame callbacks. Phasor captures the
initial/reset phase before advancing; train captures ordinal0 first. These
capture policies are explicit comparison policies where prose is less precise,
not inferred from generated code. Rate unwraps positive incoming phase ramps
then divides by its fixed sync-off time multiplier (values below1 speed up).
Multiplication is post-reset: multiply, reset
to1 when requested, then emit. Delay reads precede writes; no zero-delay tap.
The feedback reference is a fresh finite input convolution, not DSP recurrence.
"""
import math
import struct

BLOCK_FRAMES = 256
REFERENCE_CALL_COUNT = 20
MODEL_NAMES = {
    820: 'phasor-free-dyadic', 821: 'phasor-signal-reset',
    822: 'train-odd-periods', 823: 'train-onset-variable-width',
    824: 'rate-sync-off', 825: 'mulequals-nonzero-init-post-reset',
    826: 'delay-one-and-three-samples', 827: 'delay-three-sample-feedback',
}
MODELS = frozenset(MODEL_NAMES)
ABSOLUTE_TOLERANCES = {m: 2e-6 if m == 827 else 0 for m in MODELS}
PHASOR_STEPS = (3/1024, 5/2048)
PHASOR_FREQUENCIES = (129.19921875, 107.666015625)
PERIODS = (7, 11)
FEEDBACK_TERMS = 64
FEEDBACK_TAIL_BOUND = 2**-65  # |input|<=1/4; sum_{k>=64}(1/2)^k/4


def word(x):
    return struct.unpack('<I', struct.pack('<f', x))[0]


def value(w):
    return struct.unpack('<f', struct.pack('<I', w))[0]


def _model(model):
    if type(model) is not int or model not in MODELS:
        raise ValueError('Unknown Gen state-boundary model')


def input_words(frames=256):
    return case_input_words(826, frames)


def case_input_words(model, frames=256):
    _model(model)
    if type(frames) is not int or frames != BLOCK_FRAMES:
        raise ValueError('State-boundary reference requires256 frames')
    data = (0., .125, -.0625, .25, -.125, -0., .0625, -.25,
            0., -.125, .25, .125, -.25, .0625, -.0625, .125)
    result = []
    for n in range(frames):
        if model == 821:
            pair = (float(n in (1,63,255)), float(n in (0,127,254)))
        elif model == 823:
            widths = (0., .25, .5, .75, 1., 1., .5, 0.)
            pair = (widths[n % 8], widths[(n//8) % 8])
        elif model == 824:
            pair = ((n % 64)/64, (n % 32)/32)
        elif model == 825:
            pair = ((2., .5, -1., -1.)[n % 4], float(n in (0,17,127,255)))
        else:
            pair = (data[n % 16], data[(n*3+5) % 16])
        result.extend(word(x) for x in pair)
    return tuple(result)


def _checked_inputs(model, inputs):
    inputs = tuple(inputs)
    if len(inputs) != 512:
        raise ValueError('Expected one interleaved256-frame vector')
    for i, w in enumerate(inputs):
        if type(w) is not int or not 0 <= w <= 0xffffffff or (w & 0x7f800000) == 0x7f800000:
            raise ValueError('Finite binary32 input words required')
        x = value(w)
        if model == 821:
            valid = x in (0,1)
        elif model == 823:
            valid = x in (0,.25,.5,.75,1)
        elif model == 824:
            period = 64 if i % 2 == 0 else 32
            valid = 0 <= x < 1 and x*period == int(x*period)
        elif model == 825:
            valid = x in (2.,.5,-1.,1.) if i % 2 == 0 else x in (0.,1.)
        else:
            valid = abs(x) <= .25
        if not valid:
            raise ValueError('Input exceeds the predeclared model domain')
    return inputs


def reference_blocks(model, inputs, call_count=20):
    _model(model)
    if type(call_count) is not int or not 1 <= call_count <= REFERENCE_CALL_COUNT:
        raise ValueError('Invalid stateful call count')
    inputs = _checked_inputs(model, inputs)
    values = tuple(value(w) for w in inputs)
    phase = [.125, .375] if model == 821 else [0.,0.]
    products = [1.,1.]
    previous_phase = [0.,0.]
    phase_wraps = [0,0]
    blocks = []
    def sample(n, channel):
        return 0. if n < 0 else values[2*(n % 256)+channel]
    for call in range(call_count):
        block = []
        for frame in range(BLOCK_FRAMES):
            n = call*BLOCK_FRAMES+frame
            x, y = values[2*frame:2*frame+2]
            if model in (820,821):
                pair = []
                for ch, reset in enumerate((x,y)):
                    if model == 821 and reset != 0:
                        phase[ch] = (.125,.375)[ch]
                    pair.append(phase[ch])
                    phase[ch] = (phase[ch]+PHASOR_STEPS[ch]) % 1
            elif model in (822,823):
                widths = (.5,.5) if model == 822 else (x,y)
                onset = 0 if model == 822 else .25
                pair = [float(((n % period)/period-onset) % 1 < width)
                        for period,width in zip(PERIODS,widths)]
            elif model == 824:
                pair = []
                for ch, p in enumerate((x,y)):
                    if p < previous_phase[ch]:
                        phase_wraps[ch] += 1
                    previous_phase[ch] = p
                    pair.append(((phase_wraps[ch]+p)/(8 if ch == 0 else 16)) % 1)
            elif model == 825:
                for ch, factor in enumerate((x,1/x)):
                    products[ch] *= factor
                    if y != 0:
                        products[ch] = 1.
                if any(not math.isfinite(v) for v in products):
                    raise ValueError('Multiplication exceeded the bounded finite scenario')
                pair = products
            elif model == 826:
                # Copy stored input words, including its zero sign.
                block.extend(0 if n < delay else inputs[2*((n-delay) % 256)+ch]
                             for ch,delay in enumerate((1,3)))
                continue
            else:
                result = math.fsum(math.ldexp(sample(n-3*k,0),-k)
                                   for k in range(min(FEEDBACK_TERMS,n//3+1)))
                block.extend((word(result),inputs[2*frame+1]))
                continue
            block.extend(word(v) for v in pair)
        blocks.append(tuple(block))
    return tuple(blocks)


def reference_words(model, inputs):
    return reference_blocks(model,inputs,1)[0]
