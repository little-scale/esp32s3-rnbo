// SPDX-License-Identifier: MIT
#pragma once
#include "esp_err.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct cJSON cJSON;
enum { PLAYER_NETWORK_PORT=8789, PLAYER_NETWORK_COMMAND_BYTES=8192,
       PLAYER_NETWORK_RESPONSE_BYTES=16384 };

/* Boot/control owner only: read saved metadata, without starting the radio.
 * No Wi-Fi driver/task/buffers are allocated, even with saved credentials. */
esp_err_t player_network_init(void);
/* Root calls once AFTER boot audio health clears its guard, with DMA parked.
 * Unconfigured boot is an allocation-free no-op. */
bool player_network_start_saved(char *error,size_t capacity);

/* USB provisioning only, while audio DMA is parked. Credentials are copied;
 * only this component's NVS blob is written. Wi-Fi driver storage is RAM. */
bool player_network_configure(const uint8_t *ssid,size_t ssid_length,
                              const uint8_t *password,size_t password_length,
                              const uint8_t key[32],char *error,size_t capacity);
bool player_network_forget(char *error,size_t capacity);
/* USB/control owner only, with DMA parked. Visible personal/open networks only;
 * up to24 unique UTF-8 SSIDs, strongest first. No credential/NVS writes. */
bool player_network_scan(cJSON *parent,char *error,size_t capacity);

/* Appends wifi:{supported,configured,connected,ip,device_id,port,error?}.
 * Does not publish SSID, password, pairing key, nonce or authentication MAC. */
void player_network_add_status(cJSON *parent);

/* Nonblocking single outstanding command. Returns session ID, or zero if none;
 * the control owner processes the copied line, then responds once. Buffers are component
 * owned and retained even if the client times out while control is working.
 * A stale response is discarded before another request can take the slot. */
uint32_t player_network_poll_request(char *line,size_t capacity);
uint32_t player_network_current_session_id(void);
bool player_network_respond(const char *json_response);
