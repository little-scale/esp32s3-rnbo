/* SPDX-License-Identifier: MIT */
#include "player_boot_probe.h"
#include "pcm_output.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
int main(void)
{
    player_boot_probe probe={0};
    assert(!player_boot_probe_needed(&probe,0,1,true,true));
    assert(!player_boot_probe_needed(&probe,2,1,true,true));
    assert(!player_boot_probe_complete(&probe,2,1,true));
    assert(!player_boot_probe_needed(&probe,2,2,false,true));
    assert(!player_boot_probe_needed(&probe,2,2,true,false));
    pcm_output sink;pcm_output_init(&sink);
    float left[256],right[256];int16_t pcm[512];
    for(unsigned i=0;i<256;++i){left[i]=1;right[i]=-.75f;}
    for(unsigned block=0;block<2;++block){
        assert(player_boot_probe_needed(&probe,2,2,true,true));
        /* The real sink checks every input for finiteness even at maximum
         * volume with mute set. A successful probe must never emit PCM. */
        assert(pcm_output_render(&sink,left,right,pcm,256,2,100,.5f,1));
        for(unsigned i=0;i<512;++i)assert(pcm[i]==0);
        player_boot_probe_processed(&probe);
        assert(player_boot_probe_complete(&probe,2,2,true)==(block==1));
    }
    for(unsigned i=0;i<20;++i)assert(!player_boot_probe_needed(&probe,2,2,true,true));
    assert(!player_boot_probe_complete(&probe,2,3,true));
    assert(!player_boot_probe_complete(&probe,2,2,false));
    assert(player_boot_probe_needed(&probe,3,3,true,true));
    assert(!player_boot_probe_complete(&probe,3,3,true));
    left[0]=NAN;
    assert(pcm_output_render(&sink,left,right,pcm,256,2,100,.5f,1));
    assert(sink.nonfinite==1);
    for(unsigned i=0;i<512;++i)assert(pcm[i]==0);
    player_boot_probe_processed(&probe);player_boot_probe_processed(&probe);
    assert(!player_boot_probe_complete(&probe,3,3,sink.nonfinite==0));
    left[0]=1;
    assert(pcm_output_render(&sink,left,right,pcm,256,2,100,.5f,0));
    assert(pcm[0]>0 && pcm[1]<0);
    /* Explicit Resume before the silent check finishes supplies live blocks;
     * a later Pause must not advance the already verified patch again. */
    assert(!player_boot_probe_needed(&probe,4,4,false,true));
    player_boot_probe_processed(&probe);player_boot_probe_processed(&probe);
    assert(player_boot_probe_complete(&probe,4,4,true));
    assert(!player_boot_probe_needed(&probe,4,4,true,true));
    puts("PASS: bounded paused boot, stale generations, finite checks and forced-silent PCM");
}
