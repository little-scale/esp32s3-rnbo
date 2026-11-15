/* SPDX-License-Identifier: MIT */
#ifndef PLAYER_BOOT_PROBE_H
#define PLAYER_BOOT_PROBE_H
#include <stdbool.h>

/* Audio-owner state only. Requests/completion cross tasks as generation tokens.
 * A paused saved Main gets exactly two silent live callbacks, then freezes.
 * A replacement generation can never inherit the previous Main's proof. */
typedef struct { unsigned generation, remaining; } player_boot_probe;
static inline bool player_boot_probe_needed(player_boot_probe *p, unsigned request,
                                            unsigned current, bool paused, bool healthy)
{
    if (p->generation != request) { p->generation=request; p->remaining=2; }
    return request && request==current && paused && healthy && p->remaining;
}
static inline void player_boot_probe_processed(player_boot_probe *p)
{ if (p->remaining) --p->remaining; }
static inline bool player_boot_probe_complete(const player_boot_probe *p, unsigned request,
                                              unsigned current, bool healthy)
{ return request && request==current && p->generation==request && !p->remaining && healthy; }
#endif
