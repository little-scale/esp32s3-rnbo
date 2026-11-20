# SPDX-License-Identifier: MIT
"""Max/Studio selection names; the compiler and player retain their existing ABI."""
from host.profiles import LEGACY, checked

XIAO_NATIVE16 = 'xiao-16000-256-v1'
_DEFAULT_BOARD = object()


def resolve(identity=LEGACY, board=_DEFAULT_BOARD):
    xiao16 = identity == XIAO_NATIVE16
    profile = checked('voice-pe-16000-256-v1' if xiao16 else identity)
    if board is _DEFAULT_BOARD:
        board = 'xiao' if xiao16 or profile['sample_rate'] == 44100 else 'voice-pe'
    if board not in profile['boards'] or (xiao16 and board != 'xiao'):
        raise ValueError('Board and audio profile do not match')
    return dict(profile, board=board)
