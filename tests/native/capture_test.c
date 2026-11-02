/* SPDX-License-Identifier: MIT */
#include "pcm_capture.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void)
{
    for(unsigned channels=1;channels<=2;++channels) {
        const unsigned capacity=44100;
        int16_t *storage=malloc((capacity*channels+16)*sizeof(int16_t));assert(storage);
        for(unsigned i=0;i<capacity*channels+16;++i)storage[i]=12345;
        pcm_capture c;assert(pcm_capture_init(&c,storage,capacity,channels,44100,UINT32_MAX));
        uint32_t id;
        assert(!pcm_capture_begin(&c,capacity+1,&id));
        assert(!pcm_capture_begin(&c,0,&id));
        assert(pcm_capture_begin(&c,capacity,&id) && id==1);
        assert(!pcm_capture_begin(&c,1,&id));
        unsigned char chunk[1024];memset(chunk,0xa5,sizeof chunk);
        assert(!pcm_capture_read(&c,id,0,2,chunk,sizeof chunk));
        assert(chunk[0]==0xa5);
        for(unsigned block=0;block<173;++block) {
            int16_t input[512];
            for(unsigned i=0;i<256;++i)for(unsigned ch=0;ch<channels;++ch)
                input[i*channels+ch]=(int16_t)((block*256+i+ch*123)&0x7fff);
            pcm_capture_append(&c,input,256);
        }
        pcm_capture_info info;assert(pcm_capture_snapshot(&c,&info));
        assert(info.state==PCM_CAPTURE_COMPLETE && info.frames==capacity);
        assert(info.bytes==capacity*channels*2 && info.channels==channels);
        for(unsigned i=0;i<capacity;++i)for(unsigned ch=0;ch<channels;++ch)
            assert(storage[i*channels+ch]==(int16_t)((i+ch*123)&0x7fff));
        for(unsigned i=capacity*channels;i<capacity*channels+16;++i)assert(storage[i]==12345);
        unsigned offset=0;
        while(offset<info.bytes) {
            unsigned count=info.bytes-offset;if(count>sizeof chunk)count=sizeof chunk;
            assert(pcm_capture_read(&c,id,offset,count,chunk,sizeof chunk));
            assert(!memcmp(chunk,(unsigned char *)storage+offset,count));offset+=count;
        }
        assert(!pcm_capture_read(&c,id+1,0,2,chunk,sizeof chunk));
        assert(!pcm_capture_read(&c,id,info.bytes,1,chunk,sizeof chunk));
        assert(!pcm_capture_read(&c,id,UINT32_MAX,2,chunk,sizeof chunk));
        assert(!pcm_capture_read(&c,id,0,0,chunk,sizeof chunk));
        assert(!pcm_capture_read(&c,id,0,1025,chunk,sizeof chunk));
        assert(!pcm_capture_read(&c,id,0,2,chunk,1));
        uint32_t previous=id;assert(pcm_capture_begin(&c,1,&id) && id!=previous);
        int16_t zero[512]={0};pcm_capture_append(&c,zero,256);
        assert(pcm_capture_snapshot(&c,&info) && info.frames==1 && info.bytes==channels*2);
        assert(!pcm_capture_read(&c,previous,0,2,chunk,sizeof chunk));
        free(storage);
    }
    puts("pcm_capture: mono/stereo partial vectors, bounded reads, recording replacement and stale IDs passed");
}
