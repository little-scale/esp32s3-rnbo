// SPDX-License-Identifier: MIT
#include "player_network_scan.h"
#include "cJSON.h"
#include <stdint.h>
#include <string.h>

static bool supported(wifi_auth_mode_t mode)
{
    switch(mode){
        case WIFI_AUTH_OPEN:case WIFI_AUTH_WPA_PSK:case WIFI_AUTH_WPA2_PSK:
        case WIFI_AUTH_WPA_WPA2_PSK:case WIFI_AUTH_WPA3_PSK:case WIFI_AUTH_WPA2_WPA3_PSK:
        case WIFI_AUTH_WPA3_EXT_PSK:case WIFI_AUTH_WPA3_EXT_PSK_MIXED_MODE:return true;
        default:return false;
    }
}
/* SDK exposes a33-byte SSID C string, not a binary SSID length. Reject empty,
 * nonterminated names, embedded-NUL suffix data, malformed UTF-8 and C0/C1
 * controls. Other raw SSID forms cannot be represented by this setup UI. */
static bool ssid_text(const uint8_t ssid[33])
{
    size_t length=0;while(length<33&&ssid[length])++length;
    if(!length||length>32)return false;
    for(size_t i=length;i<33;++i)if(ssid[i])return false;
    for(size_t i=0;i<length;){
        uint32_t c=ssid[i++];
        if(c<32||c==127)return false;
        if(c<128)continue;
        unsigned extra;uint32_t minimum;
        if(c>=0xc2&&c<=0xdf){extra=1;minimum=0x80;c&=0x1f;}
        else if(c>=0xe0&&c<=0xef){extra=2;minimum=0x800;c&=15;}
        else if(c>=0xf0&&c<=0xf4){extra=3;minimum=0x10000;c&=7;}
        else return false;
        if(length-i<extra)return false;
        for(unsigned j=0;j<extra;++j){uint8_t next=ssid[i++];if((next&0xc0)!=0x80)return false;c=(c<<6)|(next&63);}
        if(c<minimum||c>0x10ffff||(c>=0xd800&&c<=0xdfff)||(c>=128&&c<=159))return false;
    }
    return true;
}
bool player_wifi_scan_results(cJSON *parent,const wifi_ap_record_t *records,size_t count)
{
    if(!cJSON_IsObject(parent)||count>PLAYER_WIFI_SCAN_MAX||(count&&!records)||
       cJSON_GetObjectItemCaseSensitive(parent,"networks"))return false;
    unsigned order[PLAYER_WIFI_SCAN_MAX];size_t selected=0;
    for(size_t i=0;i<count;++i){
        if(!supported(records[i].authmode)||!ssid_text(records[i].ssid)||records[i].primary<1||records[i].primary>14)continue;
        size_t where=selected;
        while(where&&records[order[where-1]].rssi<records[i].rssi){order[where]=order[where-1];--where;}
        order[where]=(unsigned)i;++selected;
    }
    cJSON *array=cJSON_CreateArray();if(!array)return false;
    for(size_t i=0;i<selected;++i){
        const wifi_ap_record_t *record=&records[order[i]];bool duplicate=false;
        for(size_t j=0;j<i;++j)if(!strcmp((const char *)record->ssid,(const char *)records[order[j]].ssid)){duplicate=true;break;}
        if(duplicate)continue;
        cJSON *entry=cJSON_CreateObject();
        int rssi=record->rssi;if(rssi>0)rssi=0;if(rssi< -127)rssi=-127;
        if(!entry||!cJSON_AddStringToObject(entry,"ssid",(const char *)record->ssid)||
           !cJSON_AddNumberToObject(entry,"rssi",rssi)||!cJSON_AddNumberToObject(entry,"channel",record->primary)||
           !cJSON_AddBoolToObject(entry,"secure",record->authmode!=WIFI_AUTH_OPEN)||!cJSON_AddItemToArray(array,entry)){
            cJSON_Delete(entry);cJSON_Delete(array);return false;
        }
    }
    if(!cJSON_AddItemToObject(parent,"networks",array)){cJSON_Delete(array);return false;}
    return true;
}
