/* SPDX-License-Identifier: MIT */
#pragma once
#include "player_remote_core.h"
#include "esp_err.h"
/* Control owner binds before releasing old metadata; no I/O under route lock. */
void player_remote_bind(const remote_route *route,const char *patch_name);
void player_remote_gate(bool playing,bool maintenance);
/* Called once with audio parked when a provisioned station is first started. */
esp_err_t player_remote_start(const char *device_id);
void player_remote_network(bool online);
/* Audio owner only: bounded nonblocking queue, no schema/JSON/network access. */
bool player_remote_receive(remote_batch *batch,unsigned budget);
void player_remote_delivered(unsigned count,bool discarded);
/* On-demand readback sweep, max8 parameters per audio block while a page polls. */
bool player_remote_refresh_requested(void);
/* Atomic cache reader; it must not call the module from HTTP/network tasks. */
typedef bool (*player_remote_read_fn)(unsigned index,float *actual,float *normalized);
void player_remote_set_reader(player_remote_read_fn reader);
void player_remote_add_status(cJSON *parent);
