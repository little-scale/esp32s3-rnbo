// SPDX-License-Identifier: MIT
#pragma once
#include "midi_core.h"
typedef struct cJSON cJSON;
enum { PLAYER_MIDI_UART=1,PLAYER_MIDI_USB=2,PLAYER_MIDI_TEST=3,PLAYER_MIDI_QUEUE=128 };
typedef struct {uint32_t generation,epoch;uint8_t bytes[3],length,source;} player_midi_message;

/* Init/config/poll/status have one control owner. Configuration writes NVS and
 * must be called while DMA is parked. UART v1 is fixed UART1, D7/GPIO44. */
bool player_midi_init(bool xiao,char *error,size_t capacity);
bool player_midi_configure_uart(bool enabled,char *error,size_t capacity);
bool player_midi_uart_enabled(void);
void player_midi_poll(int64_t now_us);
void player_midi_add_status(cJSON *parent);
void player_midi_stream_test(const uint8_t *bytes,size_t count);
bool player_midi_uart_loopback(const uint8_t *bytes,size_t count,char *error,size_t capacity);

/* Fixed-size, nonblocking cross-task ingress. No module calls, JSON, allocation
 * or transport IO on the audio owner. Generation/epoch tags reject stale data. */
bool player_midi_submit(unsigned source,const uint8_t *bytes,unsigned length);
void player_midi_set_route(unsigned generation,bool has_input);
void player_midi_set_playing(bool playing);
bool player_midi_has_input(void);
bool player_midi_receive(player_midi_message *message);
unsigned player_midi_recovery_epoch(void); /* 0 if no recovery needed */
void player_midi_recovery_done(unsigned epoch);
void player_midi_flush_queue(void);
void player_midi_request_recovery(void);
void player_midi_delivered(void);

/* Optional USB-host build only. Driver callbacks live on its client task. */
bool player_usb_midi_start(char *error,size_t capacity);
void player_midi_usb_state(bool connected,unsigned errors,unsigned ignored);
void player_midi_usb_bytes(unsigned count);
