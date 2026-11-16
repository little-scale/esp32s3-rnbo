# SPDX-License-Identifier: MIT
"""Explicit audio/deployment contracts; no patch resampling or rate retagging."""
LEGACY = 'esp32s3-44100-256-v1'
PROFILES = {
    LEGACY: dict(sample_rate=44100, block_frames=256, boards=('xiao','amoled')),
    'voice-pe-48000-256-v1': dict(sample_rate=48000, block_frames=256, boards=('voice-pe',)),
    'voice-pe-16000-256-v1': dict(sample_rate=16000, block_frames=256, boards=('voice-pe','xiao')),
}

def checked(identity=LEGACY, board=None):
    if not isinstance(identity,str) or identity not in PROFILES:
        raise ValueError('Choose an explicit supported audio profile')
    result=dict(PROFILES[identity], id=identity)
    if board is not None and board not in result['boards']:
        raise ValueError('Board and audio profile do not match')
    return result

def for_audio(rate, frames):
    if type(rate) is not int or type(frames) is not int:
        raise ValueError('Audio rate and vector size must be integers')
    for identity,value in PROFILES.items():
        if (rate,frames)==(value['sample_rate'],value['block_frames']):
            return checked(identity)
    raise ValueError('Unsupported audio rate/vector profile')
