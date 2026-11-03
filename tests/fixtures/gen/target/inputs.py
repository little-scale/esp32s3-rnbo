# SPDX-License-Identifier: MIT
"""Original dyadic stimulus, independent of observed/generated DSP outputs."""
import struct

KIND = "gen-history-dyadic-v1"
MAX_FRAMES = 16384
PATTERN = (0.25, -0.125, 0.5, 0.0, -0.25, 0.125, -0.5)


def generate(frames, *, first_frame=0):
    if type(frames) is not int or type(first_frame) is not int or frames < 1 or first_frame < 0 or first_frame + frames > MAX_FRAMES:
        raise ValueError("Gen stimulus requires a bounded positive frame span")
    return (tuple(PATTERN[n % 7] for n in range(first_frame, first_frame + frames)),
            tuple(PATTERN[(n + 3) % 7] for n in range(first_frame, first_frame + frames)))


def interleaved(frames=MAX_FRAMES, *, first_frame=0):
    left, right = generate(frames, first_frame=first_frame)
    return b"".join(struct.pack("<ff", a, b) for a, b in zip(left, right))
