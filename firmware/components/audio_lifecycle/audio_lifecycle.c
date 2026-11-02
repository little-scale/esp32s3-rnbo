/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "audio_lifecycle.h"
void audio_lifecycle_init(audio_lifecycle *s)
{
    atomic_init(&s->panic,0);atomic_init(&s->resume,0);
    atomic_init(&s->owner,AUDIO_LIFECYCLE_AUDIO);
    atomic_init(&s->parked,0);atomic_init(&s->prepared,0);
}
unsigned audio_lifecycle_panic(audio_lifecycle *s)
{
    unsigned before=atomic_load_explicit(&s->panic,memory_order_acquire);
    unsigned after;
    do { after=(before+2u)|1u; }
    while (!atomic_compare_exchange_weak_explicit(&s->panic,&before,after,memory_order_acq_rel,memory_order_acquire));
    return after;
}
void audio_lifecycle_resume(audio_lifecycle *s)
{
    unsigned token=audio_lifecycle_token(s);
    atomic_store_explicit(&s->resume,(token&1u)?token:0,memory_order_release);
}
unsigned audio_lifecycle_token(const audio_lifecycle *s)
{ return atomic_load_explicit(&s->panic,memory_order_acquire); }
unsigned audio_lifecycle_owner(const audio_lifecycle *s)
{ return atomic_load_explicit(&s->owner,memory_order_acquire); }
bool audio_lifecycle_park(audio_lifecycle *s,unsigned token)
{
    unsigned owner=audio_lifecycle_owner(s);
    if (!(token&1u) || token!=audio_lifecycle_token(s) ||
        (owner!=AUDIO_LIFECYCLE_AUDIO && owner!=AUDIO_LIFECYCLE_READY && owner!=AUDIO_LIFECYCLE_FAULT)) return false;
    if ((owner==AUDIO_LIFECYCLE_FAULT || owner==AUDIO_LIFECYCLE_READY) &&
        token==atomic_load_explicit(&s->prepared,memory_order_relaxed)) return false;
    atomic_store_explicit(&s->parked,token,memory_order_relaxed);
    atomic_store_explicit(&s->owner,AUDIO_LIFECYCLE_PARKED,memory_order_release);
    return true;
}
bool audio_lifecycle_claim(audio_lifecycle *s,unsigned *token)
{
    unsigned expected=AUDIO_LIFECYCLE_PARKED;
    if (!token || !atomic_compare_exchange_strong_explicit(&s->owner,&expected,AUDIO_LIFECYCLE_PREPARING,
                                                           memory_order_acq_rel,memory_order_acquire)) return false;
    *token=atomic_load_explicit(&s->parked,memory_order_acquire);
    return true;
}
void audio_lifecycle_ready(audio_lifecycle *s,unsigned token,bool success)
{
    atomic_store_explicit(&s->prepared,token,memory_order_relaxed);
    atomic_store_explicit(&s->owner,success?AUDIO_LIFECYCLE_READY:AUDIO_LIFECYCLE_FAULT,memory_order_release);
}
bool audio_lifecycle_attach(audio_lifecycle *s)
{
    if (audio_lifecycle_owner(s)!=AUDIO_LIFECYCLE_READY) return false;
    unsigned token=audio_lifecycle_token(s);
    if (!(token&1u) || token!=atomic_load_explicit(&s->prepared,memory_order_relaxed)) return false;
    unsigned resume=atomic_exchange_explicit(&s->resume,0,memory_order_acq_rel);
    if (resume!=token || !atomic_compare_exchange_strong_explicit(&s->panic,&token,token&~1u,
                                                                 memory_order_acq_rel,memory_order_acquire)) return false;
    atomic_store_explicit(&s->owner,AUDIO_LIFECYCLE_AUDIO,memory_order_release);
    return true;
}
