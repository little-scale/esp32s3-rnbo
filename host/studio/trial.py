# SPDX-License-Identifier: MIT
"""Bounded numerical observations for experimental packages; no promotion."""
import array
import math
import sys
import wave

BLOCKS = 1024


def compare_audio(reference, candidate, frames=BLOCKS * 256):
    """Compare real renderer captures, including its actual PCM conversion."""
    words = frames * 2
    captures, pcm = [], []
    for stem in (reference, candidate):
        raw = stem.with_suffix('.f32').read_bytes()
        if len(raw) != words * 4:
            raise ValueError('Trial capture dimensions do not match the comparison')
        floats = array.array('f'); floats.frombytes(raw)
        if sys.byteorder != 'little': floats.byteswap()
        if not all(math.isfinite(v) for v in floats):
            raise ValueError('Trial comparison requires finite reference and candidate captures')
        captures.append(floats)
        with wave.open(str(stem.with_suffix('.wav')), 'rb') as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()) != (2, 2, 44100, frames):
                raise ValueError('Trial PCM dimensions do not match the comparison')
            raw = wav.readframes(frames)
        if len(raw) != words * 2:
            raise ValueError('Truncated trial PCM capture')
        samples = array.array('h'); samples.frombytes(raw)
        if sys.byteorder != 'little': samples.byteswap()
        pcm.append(samples)
    maximum = error_sum = reference_sum = candidate_sum = 0.0
    differing = 0
    for a, b in zip(*captures):
        error = float(b) - float(a)
        maximum = max(maximum, abs(error)); error_sum += error * error
        reference_sum += float(a) * a; candidate_sum += float(b) * b
        differing += a != b
    pcm_max = max(abs(int(a) - int(b)) for a, b in zip(*pcm))
    return dict(scope='native default-parameter smoke comparison against reviewed Auto; not an object oracle or hardware accuracy test',
                qualification='unverified', sample_rate=44100, block_frames=256, frames=frames,
                float_samples=words, warmup_blocks=4, seed=305419896,
                max_absolute_error=maximum, error_rms=math.sqrt(error_sum / words),
                reference_rms=math.sqrt(reference_sum / words), candidate_rms=math.sqrt(candidate_sum / words),
                differing_float_values=differing, max_pcm_difference_lsb=pcm_max,
                diagnostic_sample_limit=2e-6, diagnostic_sample_limit_pass=maximum <= 2e-6,
                diagnostic_pcm_limit_lsb=1, diagnostic_pcm_limit_pass=pcm_max <= 1,
                pcm_volume_percent=100, pcm_headroom=0.5,
                native_timing_is_target_performance=False, promotes_reviewed_catalog=False)


def device_check(snapshot):
    """Keep only useful runtime evidence; exclude pairing/network identifiers."""
    d = snapshot.get('device') or {}
    rate, frames = d.get('rate'), d.get('block_frames')
    percent = lambda us: us * rate / frames / 10000 if all(type(v) in (int, float) and math.isfinite(v) for v in (us, rate, frames)) and rate > 0 and frames > 0 else None
    counters = ('render_deadline_overruns','nonfinite','clipped','write_errors','dma_errors','module_errors',
                'queue_errors','audio_heap_allocations','audio_heap_frees','late_platform_allocations')
    return dict(scope='player admission and short post-load runtime smoke; outputs not captured', qualification='unverified',
                board=d.get('board'), firmware_elf_sha256=d.get('firmware_elf_sha256'),
                package_sha256=(d.get('main') or {}).get('package_sha256'), generation=d.get('generation'),
                sample_rate=rate, block_frames=frames, render_us=d.get('render_us'), peak_us=d.get('peak_us'),
                audio_cpu_percent=percent(d.get('render_us')), peak_audio_cpu_percent=percent(d.get('peak_us')),
                counters={k:d.get(k) for k in counters}, output_capture_checked=False,
                unusual_cpu=(type(d.get('peak_us')) is int and percent(d['peak_us']) is not None and percent(d['peak_us']) >= 80),
                promotes_reviewed_catalog=False)
