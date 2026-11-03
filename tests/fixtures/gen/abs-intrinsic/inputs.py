# SPDX-License-Identifier: MIT
"""Exact, seekable finite magnitude edges; no generated DSP or fitted output."""
import struct

KIND='finite-magnitude-boundaries-v1'
MAGNITUDES=(0,1,2,0x3fffff,0x400000,0x7ffffe,0x7fffff,0x800000,0x800001,
            0xffffff,0x1000000,0x3e800000,0x3effffff,0x3f000000,0x3f000001,
            0x3f7ffffe,0x3f7fffff,0x3f800000)


def interleaved(frames=16384,*,first_frame=0):
    if (type(frames)is not int or type(first_frame)is not int or frames<1 or
            first_frame<0 or first_frame+frames>262144):
        raise ValueError('Invalid finite-magnitude stimulus span')
    def word(frame,channel):
        lane=frame+(17 if channel else 0)
        return MAGNITUDES[(lane//2)%len(MAGNITUDES)]|((lane&1)<<31)
    return b''.join(struct.pack('<II',word(n,0),word(n,1)) for n in range(first_frame,first_frame+frames))


def generate(frames=16384,*,first_frame=0):
    pairs=tuple(struct.iter_unpack('<ff',interleaved(frames,first_frame=first_frame)))
    return tuple(tuple(pair[channel]for pair in pairs)for channel in range(2))
