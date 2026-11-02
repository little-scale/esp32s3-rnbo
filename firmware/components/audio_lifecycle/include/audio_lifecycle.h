/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once
#include <stdatomic.h>
#include <stdbool.h>
enum { AUDIO_LIFECYCLE_AUDIO=0, AUDIO_LIFECYCLE_PARKED=1,
       AUDIO_LIFECYCLE_PREPARING=2, AUDIO_LIFECYCLE_READY=3,
       AUDIO_LIFECYCLE_FAULT=4 };
typedef struct {
    atomic_uint panic, resume, owner, parked, prepared;
} audio_lifecycle;
void audio_lifecycle_init(audio_lifecycle *);
unsigned audio_lifecycle_panic(audio_lifecycle *);
void audio_lifecycle_resume(audio_lifecycle *);
unsigned audio_lifecycle_token(const audio_lifecycle *);
unsigned audio_lifecycle_owner(const audio_lifecycle *);
/* Audio task calls after ALL module callbacks and its heap watch have stopped.
 * Publishing PARKED transfers context ownership to maintenance. */
bool audio_lifecycle_park(audio_lifecycle *, unsigned panic_token);
/* Maintenance acquires exclusive context ownership before snapshot/destroy.
 * ready() publishes the replacement context and completed parameter restore. */
bool audio_lifecycle_claim(audio_lifecycle *, unsigned *panic_token);
void audio_lifecycle_ready(audio_lifecycle *, unsigned panic_token, bool success);
/* Audio task acquire: attaches only a prepared matching generation with an
 * explicit matching Resume. A newer concurrent Panic wins its CAS. */
bool audio_lifecycle_attach(audio_lifecycle *);
