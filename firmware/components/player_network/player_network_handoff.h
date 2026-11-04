// SPDX-License-Identifier: MIT
#pragma once
#include "player_network.h"

/* Caller serializes these transitions with the component mutex. No allocation
 * or pointer ownership transfer occurs, including on disconnect/timeouts. */
typedef struct {
    bool pending,delivered,answered,abandoned;
    uint32_t session;
    char command[PLAYER_NETWORK_COMMAND_BYTES];
    char response[PLAYER_NETWORK_RESPONSE_BYTES+1];
} player_network_handoff;

bool player_handoff_publish(player_network_handoff *slot,uint32_t session);
void player_handoff_abandon(player_network_handoff *slot);
uint32_t player_handoff_poll(player_network_handoff *slot,char *line,size_t capacity);
bool player_handoff_reply(player_network_handoff *slot,const char *response);
