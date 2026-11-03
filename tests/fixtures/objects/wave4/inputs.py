# SPDX-License-Identifier: MIT
"""Original finite binary32 input programs, independent of observed outputs."""
import struct

KINDS = {"signed-grid-v1", "dense-binary32-v1", "vector-boundaries-v1"}


def _from_word(word):
    return struct.unpack("<f", struct.pack("<I", word))[0]


def _advance(seed, count):
    # Affine exponentiation mod2^32: seek to a chunk in logarithmic time.
    multiplier, increment = 1664525, 1013904223
    total_multiplier, total_increment = 1, 0
    while count:
        if count & 1:
            total_multiplier = (total_multiplier * multiplier) & 0xffffffff
            total_increment = (total_increment * multiplier + increment) & 0xffffffff
        increment = ((multiplier + 1) * increment) & 0xffffffff
        multiplier = (multiplier * multiplier) & 0xffffffff
        count >>= 1
    return (total_multiplier * seed + total_increment) & 0xffffffff


def generate(kind, frames, *, seed=305419896, start_frame=0):
    if type(kind) is not str or kind not in KINDS:
        raise ValueError("Unknown original wave4 input program")
    if type(frames) is not int or not 1 <= frames <= 1048576 or type(start_frame) is not int or not 0 <= start_frame <= 1048576:
        raise ValueError("Input frame bounds invalid")
    if frames + start_frame > 1048576 or type(seed) is not int or not 0 <= seed <= 0xffffffff:
        raise ValueError("Input seed/span invalid")
    grid = [(_from_word(a), _from_word(b)) for a, b in (
        (0x00000000, 0x80000000), (0xbf800000, 0x3f800000),
        (0x3f800000, 0xbf800000), (0x3f000000, 0x3f000000),
        (0xbf000000, 0xbf000000), (0x3f7fffff, 0x3f800000),
        (0x00000001, 0x00000000), (0x80000001, 0x00000000),
        (0x3f000001, 0x3f000000), (0x3effffff, 0x3f000000),
        (0x80000000, 0x00000000), (0x3f800000, 0x3f800000))]
    left, right = [], []
    state = _advance(seed, 2 * start_frame) if kind == "dense-binary32-v1" else seed
    for n in range(start_frame, start_frame + frames):
        if kind == "signed-grid-v1":
            a, b = grid[(n // 17) % len(grid)]
        elif kind == "dense-binary32-v1":
            values = []
            for _ in range(2):
                state = (1664525 * state + 1013904223) & 0xffffffff
                word = (state & 0x807fffff) | (((state >> 24) % 127) << 23)
                values.append(_from_word(word))
            a, b = values
            if n % 17 == 0: b = a
            if n % 31 == 0: b = -a
        else:
            # Explicit edges at 255/256, 511/512, 767/768; subsequent vectors
            # repeat with alternating signs and held plateaux for delta state.
            cycle = n % 1024
            a = (0.75 if n // 1024 % 2 == 0 else -0.75) if cycle in (0, 255, 256, 511, 512) else (0.25 if 768 <= cycle else 0.0)
            b = -0.5 if 256 <= cycle < 512 else 0.5 if 512 <= cycle < 768 else -0.0
        left.append(a); right.append(b)
    return tuple(left), tuple(right)
