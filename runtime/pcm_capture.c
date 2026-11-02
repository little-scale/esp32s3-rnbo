/* SPDX-License-Identifier: MIT */
#include "pcm_capture.h"
#include <string.h>

int pcm_capture_init(pcm_capture *c, int16_t *storage, uint32_t capacity,
                     uint32_t channels, uint32_t rate, uint32_t initial_id)
{
    if (!c || !storage || !capacity || (channels!=1 && channels!=2) ||
        !rate || capacity>UINT32_MAX/(channels*sizeof(int16_t))) return 0;
    c->samples=storage;c->capacity_frames=capacity;c->channels=channels;
    c->sample_rate=rate;c->requested_frames=0;c->id=initial_id;
    atomic_init(&c->state,PCM_CAPTURE_EMPTY);
    atomic_init(&c->written_frames,0);
    return 1;
}

int pcm_capture_begin(pcm_capture *c, uint32_t frames, uint32_t *id)
{
    if (!c || !id || !frames || frames>c->capacity_frames) return 0;
    unsigned previous=atomic_load_explicit(&c->state,memory_order_acquire);
    if (previous!=PCM_CAPTURE_EMPTY && previous!=PCM_CAPTURE_COMPLETE) return 0;
    if (!atomic_compare_exchange_strong_explicit(&c->state,&previous,PCM_CAPTURE_RESERVED,
                                                 memory_order_acq_rel,memory_order_acquire)) return 0;
    c->requested_frames=frames;
    if (!++c->id) ++c->id;
    *id=c->id;
    atomic_store_explicit(&c->written_frames,0,memory_order_relaxed);
    atomic_store_explicit(&c->state,PCM_CAPTURE_RECORDING,memory_order_release);
    return 1;
}

void pcm_capture_append(pcm_capture *c, const int16_t *source, uint32_t frames)
{
    if (!c || !source || !frames || frames>256 ||
        atomic_load_explicit(&c->state,memory_order_acquire)!=PCM_CAPTURE_RECORDING) return;
    unsigned at=atomic_load_explicit(&c->written_frames,memory_order_relaxed);
    uint32_t count=c->requested_frames-at;
    if (count>frames) count=frames;
    memcpy(c->samples+(size_t)at*c->channels,source,(size_t)count*c->channels*sizeof(int16_t));
    at+=count;
    atomic_store_explicit(&c->written_frames,at,memory_order_release);
    if (at==c->requested_frames)
        atomic_store_explicit(&c->state,PCM_CAPTURE_COMPLETE,memory_order_release);
}

int pcm_capture_snapshot(const pcm_capture *c, pcm_capture_info *out)
{
    if (!c || !out) return 0;
    unsigned state=atomic_load_explicit(&c->state,memory_order_acquire);
    if (state==PCM_CAPTURE_RESERVED) return 0;
    *out=(pcm_capture_info){state,atomic_load_explicit(&c->written_frames,memory_order_acquire),
        c->requested_frames,c->channels,c->sample_rate,
        c->requested_frames*c->channels*(uint32_t)sizeof(int16_t),c->id};
    return 1;
}

int pcm_capture_read(const pcm_capture *c, uint32_t id, uint32_t offset,
                     uint32_t count, unsigned char *out, size_t capacity)
{
    if (!c || !out || !count || count>PCM_CAPTURE_CHUNK_BYTES || count>capacity ||
        atomic_load_explicit(&c->state,memory_order_acquire)!=PCM_CAPTURE_COMPLETE ||
        id!=c->id) return 0;
    uint32_t bytes=c->requested_frames*c->channels*(uint32_t)sizeof(int16_t);
    if (offset>bytes || count>bytes-offset) return 0;
    memcpy(out,(const unsigned char *)c->samples+offset,count);
    return 1;
}
