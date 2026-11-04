// SPDX-License-Identifier: MIT
#include "midi_core.h"
#include <string.h>

void midi_stream_init(midi_stream *s){memset(s,0,sizeof *s);}
void midi_stream_boundary(midi_stream *s)
{
    if(s->used||s->explicit_pending)s->discard=s->needed-s->used;
    s->used=0;s->explicit_pending=false;
    s->status=s->running;s->needed=s->running?(uint8_t)(rnbo_s3_midi_length(s->running)-1):0;
}
void midi_stream_bytes(midi_stream *s,const uint8_t *bytes,size_t count,midi_emit_fn emit,void *context)
{
    for(size_t i=0;i<count;++i) {
        uint8_t b=bytes[i];
        if(b>=0xf8) {
            if(rnbo_s3_midi_length(b))emit(context,&b,1);else ++s->reserved;
            continue; /* Realtime never consumes partial data or running status. */
        }
        if(b&0x80) {
            s->discard=0;
            if(s->used)++s->malformed;
            s->used=0;s->explicit_pending=false;
            if(b==0xf0){s->sysex=true;s->running=s->status=s->needed=0;++s->sysex_bytes;continue;}
            if(b==0xf7){if(s->sysex)++s->sysex_bytes;else ++s->malformed;s->sysex=false;s->running=s->status=s->needed=0;continue;}
            if(s->sysex){s->sysex=false;++s->malformed;}
            unsigned length=rnbo_s3_midi_length(b);
            s->running=b<0xf0?b:0;s->status=b;s->needed=length?(uint8_t)(length-1):0;
            if(!length){s->status=0;++s->reserved;continue;}
            if(length==1){emit(context,&b,1);s->status=0;continue;}
            s->explicit_pending=true;continue;
        }
        if(s->sysex){++s->sysex_bytes;continue;}
        if(s->discard){--s->discard;continue;}
        if(!s->status||!s->needed){++s->malformed;continue;}
        s->data[s->used++]=b;
        if(s->used==s->needed) {
            uint8_t message[3]={s->status,s->data[0],s->needed==2?s->data[1]:0};
            emit(context,message,s->needed+1);s->used=0;s->explicit_pending=false;
            s->status=s->running;s->needed=s->running?(uint8_t)(rnbo_s3_midi_length(s->running)-1):0;
        }
    }
}
int midi_usb1_packet(const uint8_t p[4],uint8_t message[3],unsigned *length)
{
    if(!p||!message||!length)return MIDI_USB_INVALID;
    unsigned cable=p[0]>>4,cin=p[0]&15;
    if(cable)return MIDI_USB_IGNORED; /* v1 routes cable0 to RNBO port0 only. */
    unsigned n=cin==2?2:cin==3?3:cin==5||cin==15?1:cin>=8&&cin<=14?(cin==12||cin==13?2:3):0;
    if(cin==4||cin==6||cin==7|| (cin==5&&p[1]==0xf7))return MIDI_USB_IGNORED;
    if(!n||!rnbo_s3_midi_valid(p+1,n))return MIDI_USB_INVALID;
    if(cin>=8&&cin<=14) {if((p[1]>>4)!=cin)return MIDI_USB_INVALID;}
    else if(cin==2) {if(p[1]!=0xf1&&p[1]!=0xf3)return MIDI_USB_INVALID;}
    else if(cin==3) {if(p[1]!=0xf2)return MIDI_USB_INVALID;}
    else if(cin==5) {if(p[1]!=0xf6)return MIDI_USB_INVALID;}
    else if(cin==15) {if(p[1]<0xf8)return MIDI_USB_INVALID;}
    memcpy(message,p+1,n);if(n<3)memset(message+n,0,3-n);*length=n;return MIDI_USB_MESSAGE;
}
bool midi_usb1_find_endpoint(const uint8_t *d,size_t length,midi_usb1_endpoint *out)
{
    if(!d||!out||length<9||d[0]!=9||d[1]!=2)return false;
    size_t total=(size_t)d[2]|((size_t)d[3]<<8);
    if(total<9||total>length)return false;
    bool streaming=false,version1=false;uint8_t interface=0,alternate=0;
    midi_usb1_endpoint found={0};bool have=false;
    for(size_t pos=0;pos<total;) {
        if(total-pos<2||d[pos]<2||d[pos]>total-pos)return false;
        const uint8_t *p=d+pos;unsigned n=p[0];
        if(p[1]==4) {
            if(n<9)return false;
            interface=p[2];alternate=p[3];streaming=p[5]==1&&p[6]==3&&p[7]==0&&alternate==0;version1=false;
        } else if(p[1]==0x24&&streaming&&n>=3&&p[2]==1) {
            if(n<7)return false;
            version1=p[3]==0&&p[4]==1; /* bcdMSC=0x0100, reject MIDI2.0. */
        } else if(p[1]==5&&streaming&&version1&&!have) {
            if(n<7)return false;
            unsigned packet=(unsigned)p[4]|((unsigned)p[5]<<8);
            if((p[2]&0x80)&&(p[2]&15)&& (p[3]&3)==2 && packet>=4&&packet<=64&&!(packet%4)) {
                found=(midi_usb1_endpoint){interface,alternate,p[2],(uint16_t)packet};have=true;
            }
        }
        pos+=n;
    }
    if(have)*out=found;
    return have;
}
void midi_notes_observe(midi_note_state *s,const uint8_t *b,unsigned n)
{
    if(n!=3||!rnbo_s3_midi_valid(b,n)||b[0]>=0xf0)return;
    unsigned ch=b[0]&15,kind=b[0]&0xf0,note=b[1];
    if(kind==0x90&&b[2])s->notes[ch][note>>3]|=(uint8_t)(1u<<(note&7));
    else if(kind==0x80||kind==0x90)s->notes[ch][note>>3]&=(uint8_t)~(1u<<(note&7));
}
void midi_notes_recover(midi_note_state *s){s->cursor=0;s->recovering=true;}
bool midi_notes_recovery_next(midi_note_state *s,uint8_t b[3])
{
    if(!s->recovering)return false;
    /* Sustain-off first. Explicit NoteOffs also reach plain RNBO notein patches
     * which do not interpret the channel-mode All Notes Off message. */
    while(s->cursor<16+16*128) {
        unsigned i=s->cursor++;
        if(i<16){b[0]=(uint8_t)(0xb0|i);b[1]=64;b[2]=0;return true;}
        i-=16;unsigned ch=i/128,note=i%128;
        if(s->notes[ch][note>>3]&(1u<<(note&7))) {
            s->notes[ch][note>>3]&=(uint8_t)~(1u<<(note&7));
            b[0]=(uint8_t)(0x80|ch);b[1]=(uint8_t)note;b[2]=0;return true;
        }
    }
    s->recovering=false;return false;
}
