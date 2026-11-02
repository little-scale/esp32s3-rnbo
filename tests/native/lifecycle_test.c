/* SPDX-License-Identifier: MIT */
#include "audio_lifecycle.h"
#include <assert.h>
#include <stdio.h>

static void cycle(audio_lifecycle *s)
{
    unsigned claimed;
    unsigned token=audio_lifecycle_panic(s);
    assert(token&1u);
    assert(!audio_lifecycle_attach(s));
    assert(audio_lifecycle_park(s,token));
    assert(audio_lifecycle_claim(s,&claimed) && claimed==token);
    assert(!audio_lifecycle_claim(s,&claimed));
    assert(!audio_lifecycle_park(s,token));
    assert(!audio_lifecycle_attach(s));
    audio_lifecycle_ready(s,token,true);
    assert(!audio_lifecycle_park(s,token)); // polling cannot revoke prepared state
    assert(!audio_lifecycle_attach(s)); // prepared does not imply Resume
    audio_lifecycle_resume(s);
    assert(audio_lifecycle_attach(s));
    assert(audio_lifecycle_owner(s)==AUDIO_LIFECYCLE_AUDIO);
    assert(!(audio_lifecycle_token(s)&1u));
}

int main(void)
{
    audio_lifecycle s;audio_lifecycle_init(&s);
    unsigned token;
    assert(audio_lifecycle_owner(&s)==AUDIO_LIFECYCLE_AUDIO);
    assert(!audio_lifecycle_claim(&s,&token));
    assert(!audio_lifecycle_park(&s,0));
    audio_lifecycle_resume(&s);assert(!audio_lifecycle_attach(&s));
    for(unsigned i=0;i<10000;++i) cycle(&s);

    /* A stale Resume is unable to release a newer Panic. */
    unsigned old=audio_lifecycle_panic(&s);audio_lifecycle_resume(&s);
    unsigned newer=audio_lifecycle_panic(&s);
    assert(!audio_lifecycle_park(&s,old));
    assert(audio_lifecycle_park(&s,newer));
    assert(audio_lifecycle_claim(&s,&token) && token==newer);
    audio_lifecycle_ready(&s,token,true);
    assert(!audio_lifecycle_park(&s,token));
    assert(!audio_lifecycle_attach(&s));
    audio_lifecycle_resume(&s);assert(audio_lifecycle_attach(&s));

    /* Panic during construction requires the new generation to be prepared;
     * neither a queued Resume nor a previous successful prepare can attach it. */
    old=audio_lifecycle_panic(&s);assert(audio_lifecycle_park(&s,old));
    assert(audio_lifecycle_claim(&s,&token) && token==old);
    newer=audio_lifecycle_panic(&s);audio_lifecycle_resume(&s);
    assert(!audio_lifecycle_attach(&s));
    audio_lifecycle_ready(&s,old,true);assert(!audio_lifecycle_attach(&s));
    assert(audio_lifecycle_park(&s,newer));assert(audio_lifecycle_claim(&s,&token));
    audio_lifecycle_ready(&s,token,true);assert(audio_lifecycle_attach(&s));

    /* Failed reconstruction stays muted; an explicit new Panic permits a
     * retry, which still needs an independently matching Resume. */
    old=audio_lifecycle_panic(&s);assert(audio_lifecycle_park(&s,old));
    assert(audio_lifecycle_claim(&s,&token));audio_lifecycle_ready(&s,token,false);
    audio_lifecycle_resume(&s);assert(!audio_lifecycle_attach(&s));
    assert(audio_lifecycle_owner(&s)==AUDIO_LIFECYCLE_FAULT);
    assert(!audio_lifecycle_park(&s,old));
    newer=audio_lifecycle_panic(&s);assert(audio_lifecycle_park(&s,newer));
    assert(audio_lifecycle_claim(&s,&token));audio_lifecycle_ready(&s,token,true);
    assert(!audio_lifecycle_attach(&s));audio_lifecycle_resume(&s);
    assert(audio_lifecycle_attach(&s));
    puts("audio_lifecycle: 10000 ownership transfers, stale Resume, generation changes during preparation and failure/retry passed");
}
