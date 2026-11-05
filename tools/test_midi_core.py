# SPDX-License-Identifier: MIT
"""Actual transport parser/descriptor/note-state code; no USB or MIDI devices."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=r'''
#include "midi_core.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
typedef struct {uint8_t bytes[4096][3];unsigned length[4096],count;} capture;
static void record(void *context,const uint8_t *bytes,unsigned length) {
    capture *c=context;assert(rnbo_s3_midi_valid(bytes,length));assert(c->count<4096);
    memcpy(c->bytes[c->count],bytes,length);c->length[c->count++]=length;
}
static void validate(void *context,const uint8_t *bytes,unsigned length) {
    unsigned *count=context;assert(rnbo_s3_midi_valid(bytes,length));++*count;
}
static void equal(capture *c,unsigned i,unsigned status,unsigned a,unsigned b,unsigned n) {
    assert(i<c->count&&c->length[i]==n&&c->bytes[i][0]==status);
    if(n>1) {
        assert(c->bytes[i][1]==a);
    }
    if(n>2) {
        assert(c->bytes[i][2]==b);
    }
}
int main(void) {
    midi_stream s;midi_stream_init(&s);capture c={0};
    uint8_t stream[]={0x90,60,100,61,0,0xf8,0xc0,5,6,0xd0,70,0xfe,0x80,61,0};
    midi_stream_bytes(&s,stream,sizeof stream,record,&c);assert(c.count==8);
    equal(&c,0,0x90,60,100,3);equal(&c,1,0x90,61,0,3);equal(&c,2,0xf8,0,0,1);
    equal(&c,3,0xc0,5,0,2);equal(&c,4,0xc0,6,0,2);equal(&c,5,0xd0,70,0,2);
    equal(&c,6,0xfe,0,0,1);equal(&c,7,0x80,61,0,3);
    midi_stream_init(&s);memset(&c,0,sizeof c);
    uint8_t partial[]={0x90,60,0xf8,0xfa,100,0xf0,1,2,0xf8,3,0xf7,0xf2,1,0xfc,2,61,2};
    midi_stream_bytes(&s,partial,sizeof partial,record,&c);assert(c.count==6);
    equal(&c,0,0xf8,0,0,1);equal(&c,1,0xfa,0,0,1);equal(&c,2,0x90,60,100,3);
    equal(&c,3,0xf8,0,0,1);equal(&c,4,0xfc,0,0,1);equal(&c,5,0xf2,1,2,3);
    /* The last data bytes must NOT resurrect running status after F2. */
    assert(c.count==6&&s.malformed==2);
    midi_stream_init(&s);memset(&c,0,sizeof c);
    uint8_t first[]={0x90,60},rest[]={0xf8,100,61,99};
    midi_stream_bytes(&s,first,sizeof first,record,&c);midi_stream_boundary(&s);
    midi_stream_bytes(&s,rest,sizeof rest,record,&c);assert(c.count==2);
    equal(&c,0,0xf8,0,0,1);equal(&c,1,0x90,61,99,3);
    midi_stream_boundary(&s);uint8_t next[]={62,88};midi_stream_bytes(&s,next,2,record,&c);equal(&c,2,0x90,62,88,3);
    midi_stream_init(&s);memset(&c,0,sizeof c);uint8_t status=0x90;
    midi_stream_bytes(&s,&status,1,record,&c);midi_stream_boundary(&s);
    uint8_t tail[]={60,100,61,1};midi_stream_bytes(&s,tail,4,record,&c);assert(c.count==1);equal(&c,0,0x90,61,1,3);
    unsigned total=0;uint32_t random=1234567;
    for(unsigned i=0;i<250000;++i){random=random*1664525u+1013904223u;uint8_t b=(uint8_t)(random>>24);midi_stream_bytes(&s,&b,1,validate,&total);}
    assert(total>1000);
    uint8_t bytes[3];unsigned length=0;
    const uint8_t note[]={9,0x90,60,127},clock[]={15,0xf8,0,0},song[]={3,0xf2,1,2},bad[]={8,0x90,60,1},cable[]={0x19,0x90,60,1},sysex[]={4,0xf0,1,2};
    assert(midi_usb1_packet(note,bytes,&length)==1&&length==3&&bytes[2]==127);
    assert(midi_usb1_packet(clock,bytes,&length)==1&&length==1&&bytes[0]==0xf8);
    assert(midi_usb1_packet(song,bytes,&length)==1&&length==3&&bytes[0]==0xf2);
    assert(midi_usb1_packet(bad,bytes,&length)==-1);
    assert(midi_usb1_packet(cable,bytes,&length)==0&&midi_usb1_packet(sysex,bytes,&length)==0);
    for(unsigned st=0x80;st<0xf0;++st){uint8_t p[4]={(uint8_t)(st>>4),(uint8_t)st,2,3};assert(midi_usb1_packet(p,bytes,&length)==1&&length==rnbo_s3_midi_length(st));}
    uint8_t descriptor[]={9,2,39,0,1,1,0,0x80,50,9,4,2,0,1,1,3,0,0,7,0x24,1,0,1,7,0,9,5,0x81,2,64,0,0,0,0,5,0x25,1,1,1};
    midi_usb1_endpoint ep;assert(sizeof descriptor==39&&midi_usb1_find_endpoint(descriptor,sizeof descriptor,&ep));
    assert(ep.interface==2&&ep.endpoint==0x81&&ep.packet_bytes==64&&ep.alternate==0);
    for(unsigned n=0;n<sizeof descriptor;++n)assert(!midi_usb1_find_endpoint(descriptor,n,&ep));
    descriptor[22]=2;assert(!midi_usb1_find_endpoint(descriptor,sizeof descriptor,&ep));descriptor[22]=1;
    descriptor[27]=1;assert(!midi_usb1_find_endpoint(descriptor,sizeof descriptor,&ep));descriptor[27]=0x81;
    descriptor[25]=0;assert(!midi_usb1_find_endpoint(descriptor,sizeof descriptor,&ep));
    midi_note_state notes={0};uint8_t n1[]={0x90,60,100},n2[]={0x90,64,100},n3[]={0x91,60,100};
    midi_notes_observe(&notes,n1,3);midi_notes_observe(&notes,n2,3);midi_notes_observe(&notes,n3,3);
    midi_notes_recover(&notes);unsigned sustain=0,offs=0;
    while(midi_notes_recovery_next(&notes,bytes)){assert(rnbo_s3_midi_valid(bytes,3));if((bytes[0]&0xf0)==0xb0)++sustain;else ++offs;}
    assert(sustain==16&&offs==3&&!notes.recovering);
    midi_notes_observe(&notes,n1,3);n1[2]=0;midi_notes_observe(&notes,n1,3);midi_notes_recover(&notes);offs=0;
    while(midi_notes_recovery_next(&notes,bytes))if((bytes[0]&0xf0)==0x80)++offs;
    assert(offs==0);
    puts("MIDI framing, running status, realtime/clock, SysEx filtering, epochs, USB1 descriptors/packets and note recovery passed");
}
'''


class MidiCoreTests(unittest.TestCase):
    def test_real_parser_and_recovery_with_ubsan(self):
        cc=shutil.which('cc')
        if not cc:self.skipTest('Native C compiler required')
        component=ROOT/'firmware/components/player_midi'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.c').write_text(SOURCE)
            command=[cc,'-std=c11','-O2','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=all',
                '-I'+str(component/'include'),'-I'+str(ROOT/'module-sdk/include'),str(p/'test.c'),str(component/'midi_core.c'),'-o',str(p/'test')]
            result=subprocess.run(command,capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(p/'test')],capture_output=True,text=True,timeout=30);self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__':unittest.main()
