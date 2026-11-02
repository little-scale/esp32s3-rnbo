/* SPDX-License-Identifier: MIT */
#ifndef RNBO_S3_PCM_CAPTURE_H
#define RNBO_S3_PCM_CAPTURE_H
#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>

/* C11 single producer (audio owner) / single controller. Storage is caller
 * owned and must outlive all operations. Controller calls are serialized;
 * UI reads a shell snapshot, never this structure concurrently. */
enum { PCM_CAPTURE_EMPTY=0, PCM_CAPTURE_RECORDING=1,
       PCM_CAPTURE_COMPLETE=2, PCM_CAPTURE_RESERVED=3 };
#define PCM_CAPTURE_CHUNK_BYTES 1024u
typedef struct {
    atomic_uint state, written_frames;
    int16_t *samples;
    uint32_t capacity_frames, channels, sample_rate, requested_frames, id;
} pcm_capture;
typedef struct {
    uint32_t state, frames, requested, channels, rate, bytes, capture_id;
} pcm_capture_info;

int pcm_capture_init(pcm_capture *, int16_t *storage, uint32_t capacity_frames,
                     uint32_t channels, uint32_t sample_rate, uint32_t initial_id);
int pcm_capture_begin(pcm_capture *, uint32_t frames, uint32_t *recording_id);
/* Append only after the corresponding sink write succeeds. At most256 frames.
 * The last block is clipped to remaining recording capacity, without allocation. */
void pcm_capture_append(pcm_capture *, const int16_t *interleaved, uint32_t frames);
int pcm_capture_snapshot(const pcm_capture *, pcm_capture_info *);
/* A stale recording ID, incomplete recording, or invalid range fails without
 * touching destination. Offsets/counts are bytes; count is1..1024. */
int pcm_capture_read(const pcm_capture *, uint32_t recording_id, uint32_t offset,
                     uint32_t count, unsigned char *destination, size_t capacity);
#endif
