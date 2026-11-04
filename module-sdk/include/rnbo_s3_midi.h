/* SPDX-License-Identifier: MIT */
#ifndef RNBO_S3_MIDI_H
#define RNBO_S3_MIDI_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* MIDI 1.0 complete short messages. SysEx and reserved statuses are excluded.
 * Does not change the event ABI: all supported messages fit its three bytes. */
static inline unsigned rnbo_s3_midi_length(uint8_t status)
{
    if(status<0x80)return 0;
    if(status<0xf0)return (status&0xf0)==0xc0||(status&0xf0)==0xd0?2:3;
    switch(status) {
    case 0xf1:case 0xf3:return 2;
    case 0xf2:return 3;
    case 0xf6:case 0xf8:case 0xfa:case 0xfb:case 0xfc:case 0xfe:case 0xff:return 1;
    default:return 0;
    }
}
static inline bool rnbo_s3_midi_valid(const uint8_t *bytes,size_t length)
{
    if(!bytes||!length||length>3||rnbo_s3_midi_length(bytes[0])!=length)return false;
    for(size_t i=1;i<length;++i)if(bytes[i]&0x80)return false;
    return true;
}
#endif
