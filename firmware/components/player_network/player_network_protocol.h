// SPDX-License-Identifier: MIT
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define PLAYER_WIFI_MAX_SEQUENCE UINT64_C(9007199254740991)
#define PLAYER_WIFI_REQUEST_WIRE_BYTES (6u*8191u+512u)
#define PLAYER_WIFI_RESPONSE_WIRE_BYTES (6u*16384u+512u)

bool player_wifi_authenticate(const uint8_t key[32],const char server_nonce[65],
                              const char *line,size_t length,char client_nonce[65]);
bool player_wifi_request(const uint8_t key[32],const char server_nonce[65],const char client_nonce[65],
                         uint64_t sequence,const char *line,size_t length,char *command,size_t capacity);
bool player_wifi_response(const uint8_t key[32],const char server_nonce[65],const char client_nonce[65],
                          uint64_t sequence,const char *response,char *wire,size_t capacity);
