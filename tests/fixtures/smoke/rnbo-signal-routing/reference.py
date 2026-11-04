# SPDX-License-Identifier: MIT
"""Independent bounded signal-router and interpolation equations.

Gate uses two outlets and ramptime=0. Selector choices are exactly 0,1,2;
its second data choice is the negative of the first. Named buses are local
stereo copies. Interpolators use distinct asymmetric fixed keyframes, not
time/history models or fitted generated expressions. Other modes are excluded.
"""
import math
import struct

NAMES = ('gate~', 'selector~', 'send~', 's~', 'receive~', 'r~',
         'cubicinterp~', 'fastcubicinterp~', 'splineinterp~', 'spline6interp~',
         '==p~', '!=p~', '>p~', '>=p~', '<p~', '<=p~',
         'equals~', 'lessthan~', 'minus~', '?~')
MODEL_NAMES = {800 + i: name for i, name in enumerate(NAMES)}
MODELS = frozenset(MODEL_NAMES)
INTERPOLATORS = frozenset(NAMES[6:10])
BUSES = frozenset(NAMES[2:6])
ABSOLUTE_TOLERANCES = {m: 2e-6 if name in INTERPOLATORS else 0
                       for m, name in MODEL_NAMES.items()}
C4 = ((-.5, .25, 1.25, -.75), (.75, -1., .5, 1.5))
C6 = ((-1., .5, -.25, 1.25, -.75, 2.), (.75, -1.5, .25, -.5, 1.5, -.25))


def word(x):
    return struct.unpack('<I', struct.pack('<f', x))[0]


def value(w):
    return struct.unpack('<f', struct.pack('<I', w))[0]


WIDE = tuple(map(word, (-4, -2, -1.5, -1, -.75, -.5, -.25, -0.,
                        0., .25, .5, .75, 1, 1.5, 2, 4)))
CHOICES = tuple(map(word, (0, 1, 2, -0., 2, 1, 0, 2, 1, 0, 2, 1, 0, 1, 2, 0)))
PHASE = (0, 1, 0x00800000, word(1/32), word(1/16), word(3/32),
         word(1/8), word(5/32), word(3/16), word(7/32), word(1/4),
         word(9/32), word(5/16), word(11/32), word(3/8), word(13/32),
         word(7/16), word(15/32), word(.5)-1, word(.5), word(.5)+1,
         word(17/32), word(9/16), word(19/32), word(5/8), word(11/16),
         word(3/4), word(13/16), word(7/8), word(15/16), word(1)-1, word(1))


def _model(model):
    if type(model) is not int or model not in MODELS:
        raise ValueError('Unknown RNBO signal-routing model')


def input_words(frames=256):
    return case_input_words(800, frames)


def case_input_words(model, frames=256):
    _model(model)
    if type(frames) is not int or not 1 <= frames <= 16384:
        raise ValueError('Invalid vector length')
    name = MODEL_NAMES[model]
    if name in INTERPOLATORS:
        return tuple(w for n in range(frames)
                     for w in (PHASE[(n//8) % 32], PHASE[(n*7) % 32]))
    left = CHOICES if name in ('gate~', 'selector~') else WIDE
    return tuple(w for n in range(frames)
                 for w in (left[(n//16) % 16], WIDE[n % 16]))


def _hermite(t, x, y, m0, m1):
    return ((2*t**3-3*t*t+1)*x + (t**3-2*t*t+t)*m0
            + (-2*t**3+3*t*t)*y + (t**3-t*t)*m1)


def interpolate(name, t, points):
    if name == 'cubicinterp~':
        nodes = (-1, 0, 1, 2)
        return math.fsum(v * math.prod((t-nodes[j])/(nodes[i]-nodes[j])
                                      for j in range(4) if j != i)
                         for i, v in enumerate(points))
    w, x, y, z = points
    slope = .5 if name == 'splineinterp~' else 1.
    return _hermite(t, x, y, slope*(y-w), slope*(z-x))


def _bspline5(z):
    return math.fsum((-1)**k * math.comb(6, k) * max(z+3-k, 0.)**5
                     for k in range(7)) / 120


def spline6(t, points):
    return math.fsum(y*_bspline5(t-x)
                     for x, y in zip((-2, -1, 0, 1, 2, 3), points))


def reference_words(model, inputs):
    _model(model)
    name = MODEL_NAMES[model]
    inputs = tuple(inputs)
    if not inputs or len(inputs) % 2 or len(inputs) > 32768:
        raise ValueError('Expected bounded stereo input words')
    for i, w in enumerate(inputs):
        if type(w) is not int or not 0 <= w <= 0xffffffff or (w & 0x7f800000) == 0x7f800000:
            raise ValueError('Finite binary32 input words required')
        x = value(w)
        if name in INTERPOLATORS:
            if not 0 <= x <= 1:
                raise ValueError('Interpolation phase must be in [0,1]')
        elif name in ('gate~', 'selector~') and i % 2 == 0:
            if x not in (0, 1, 2):
                raise ValueError('Router choices must be integers 0,1,2')
        elif not -4 <= x <= 4:
            raise ValueError('Input exceeds declared [-4,4] domain')
    if name in BUSES:
        return inputs
    predicates = {'==p~': lambda x,y: x == y, '!=p~': lambda x,y: x != y,
                  '>p~': lambda x,y: x > y, '>=p~': lambda x,y: x >= y,
                  '<p~': lambda x,y: x < y, '<=p~': lambda x,y: x <= y}
    result = []
    for i in range(0, len(inputs), 2):
        x, y = (value(w) for w in inputs[i:i+2])
        if name == 'gate~':
            pair = (y if x == 1 else 0., y if x == 2 else 0.)
        elif name == 'selector~':
            pair = (y if x == 1 else -y if x == 2 else 0., y)
        elif name in predicates:
            p = predicates[name]
            pair = (x if p(x,y) else 0., y if p(y,x) else 0.)
        elif name == 'equals~':
            pair = (float(x == y), float(y == x))
        elif name == 'lessthan~':
            pair = (float(x < y), float(y < x))
        elif name == 'minus~':
            pair = (x-y, y-x)
        elif name == '?~':
            pair = (1. if x != 0 else -1., -1. if y != 0 else 1.)
        elif name == 'spline6interp~':
            pair = (spline6(x, C6[0]), spline6(y, C6[1]))
        else:
            pair = (interpolate(name, x, C4[0]), interpolate(name, y, C4[1]))
        result.extend(word(v) for v in pair)
    return tuple(result)
