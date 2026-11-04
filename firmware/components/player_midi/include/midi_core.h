// SPDX-License-Identifier: MIT
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "rnbo_s3_midi.h"

typedef void (*midi_emit_fn)(void *,const uint8_t *,unsigned);
typedef struct {
    uint8_t running,status,data[2],used,needed,discard;
    bool sysex,explicit_pending;
    uint32_t malformed,sysex_bytes,reserved;
} midi_stream;
void midi_stream_init(midi_stream *s);
void midi_stream_boundary(midi_stream *s); /* keep running status; discard old partial */
void midi_stream_bytes(midi_stream *s,const uint8_t *bytes,size_t count,midi_emit_fn emit,void *context);

enum { MIDI_USB_INVALID=-1, MIDI_USB_IGNORED=0, MIDI_USB_MESSAGE=1 };
int midi_usb1_packet(const uint8_t packet[4],uint8_t message[3],unsigned *length);
typedef struct {uint8_t interface,alternate,endpoint;uint16_t packet_bytes;} midi_usb1_endpoint;
bool midi_usb1_find_endpoint(const uint8_t *descriptor,size_t length,midi_usb1_endpoint *endpoint);

typedef struct {uint8_t notes[16][16];unsigned cursor;bool recovering;} midi_note_state;
void midi_notes_observe(midi_note_state *s,const uint8_t *bytes,unsigned length);
void midi_notes_recover(midi_note_state *s);
bool midi_notes_recovery_next(midi_note_state *s,uint8_t message[3]);
