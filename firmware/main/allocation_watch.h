/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once
#include <stdint.h>
typedef struct {
    uint32_t allocations, frees;
    uint64_t requested_bytes, external_bytes, internal_bytes;
} allocation_watch_stats;
enum { ALLOCATION_WATCH_PREPARE=1, ALLOCATION_WATCH_AUDIO=2 };
/* A single watched task at a time. The owner calls start/stop/snapshot.
 * ISR and other-task allocations are deliberately excluded. Byte counts are
 * cumulative successful requests, not live bytes or initialization peaks. */
void allocation_watch_start(unsigned phase);
void allocation_watch_stop(void);
allocation_watch_stats allocation_watch_snapshot(unsigned phase);
