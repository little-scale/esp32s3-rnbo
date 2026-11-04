// SPDX-License-Identifier: MIT
#include "player_network_handoff.h"
#include <string.h>

bool player_handoff_publish(player_network_handoff *slot,uint32_t session)
{
    if(!slot||slot->pending||!session)return false;
    size_t count=strnlen(slot->command,sizeof(slot->command));
    if(!count||count>=sizeof(slot->command))return false;
    slot->pending=true;slot->delivered=false;slot->answered=false;slot->abandoned=false;
    slot->session=session;slot->response[0]=0;return true;
}
void player_handoff_abandon(player_network_handoff *slot)
{
    if(!slot||!slot->pending)return;
    slot->abandoned=true;
    /* Once claimed, retain until root responds, even after the socket closes. */
    if(!slot->delivered||slot->answered)slot->pending=false;
}
uint32_t player_handoff_poll(player_network_handoff *slot,char *line,size_t capacity)
{
    if(!slot||!line||!capacity||!slot->pending||slot->delivered||slot->abandoned)return 0;
    size_t count=strnlen(slot->command,sizeof(slot->command));
    if(count>=capacity||count>=sizeof(slot->command))return 0;
    memcpy(line,slot->command,count+1);slot->delivered=true;return slot->session;
}
bool player_handoff_reply(player_network_handoff *slot,const char *response)
{
    if(!slot||!slot->pending||!slot->delivered||slot->answered)return false;
    size_t count=response?strnlen(response,sizeof(slot->response)):0;
    if(slot->abandoned||!count||count>=sizeof(slot->response)){
        slot->pending=false;slot->abandoned=true;return false;
    }
    memcpy(slot->response,response,count+1);slot->answered=true;return true;
}
