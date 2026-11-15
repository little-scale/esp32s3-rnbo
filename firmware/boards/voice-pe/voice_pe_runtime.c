/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Adapted from SynthDef headless_io_voice_pe.c; one control owner only. */
#include "voice_pe_runtime.h"
#include "voice_pe_pins.h"
#include "driver/gpio.h"
#include "driver/pulse_cnt.h"
#include "esp_timer.h"
#include "cJSON.h"
#include <stdint.h>
#include <math.h>
static pcnt_unit_handle_t encoder;
static int previous_count;
static float values[3]={.5f,0,0},sent[3];
static bool sent_once[3],ready;
static unsigned candidate,stable;
static int64_t next_poll;
esp_err_t voice_pe_runtime_init(void)
{
    pcnt_unit_config_t cfg={.low_limit=-30000,.high_limit=30000,.flags.accum_count=true};
    esp_err_t err=pcnt_new_unit(&cfg,&encoder);if(err!=ESP_OK)return err;
    pcnt_channel_handle_t a,b;
    pcnt_chan_config_t ca={.edge_gpio_num=VPE_ENCODER_A,.level_gpio_num=VPE_ENCODER_B};
    pcnt_chan_config_t cb={.edge_gpio_num=VPE_ENCODER_B,.level_gpio_num=VPE_ENCODER_A};
    if((err=pcnt_new_channel(encoder,&ca,&a))!=ESP_OK)return err;
    if((err=pcnt_new_channel(encoder,&cb,&b))!=ESP_OK)return err;
    if((err=pcnt_channel_set_edge_action(a,PCNT_CHANNEL_EDGE_ACTION_DECREASE,PCNT_CHANNEL_EDGE_ACTION_INCREASE))!=ESP_OK)return err;
    if((err=pcnt_channel_set_edge_action(b,PCNT_CHANNEL_EDGE_ACTION_INCREASE,PCNT_CHANNEL_EDGE_ACTION_DECREASE))!=ESP_OK)return err;
    if((err=pcnt_channel_set_level_action(a,PCNT_CHANNEL_LEVEL_ACTION_KEEP,PCNT_CHANNEL_LEVEL_ACTION_INVERSE))!=ESP_OK)return err;
    if((err=pcnt_channel_set_level_action(b,PCNT_CHANNEL_LEVEL_ACTION_KEEP,PCNT_CHANNEL_LEVEL_ACTION_INVERSE))!=ESP_OK)return err;
    if((err=pcnt_unit_add_watch_point(encoder,30000))!=ESP_OK)return err;
    if((err=pcnt_unit_add_watch_point(encoder,-30000))!=ESP_OK)return err;
    if((err=pcnt_unit_enable(encoder))!=ESP_OK)return err;
    if((err=pcnt_unit_clear_count(encoder))!=ESP_OK)return err;
    if((err=pcnt_unit_start(encoder))!=ESP_OK)return err;
    values[1]=gpio_get_level(VPE_BUTTON)==0;values[2]=gpio_get_level(VPE_MUTE_SENSE);
    candidate=(unsigned)values[1];ready=true;
    return voice_pe_led_init();
}
void voice_pe_runtime_values(float out[3]){for(unsigned i=0;i<3;++i)out[i]=values[i];}
bool voice_pe_runtime_ready(void){return ready;}
void voice_pe_runtime_poll(bool reset,bool paused,bool fault,bool (*publish)(unsigned,float))
{
    if(!ready)return;
    if(reset)for(unsigned i=0;i<3;++i)sent_once[i]=false;
    int64_t now=esp_timer_get_time();if(now<next_poll)return;next_poll=now+10000;
    int count;
    if(pcnt_unit_get_count(encoder,&count)==ESP_OK){
        int64_t delta=(int64_t)count-previous_count;previous_count=count;
        if(delta>=-1000&&delta<=1000){values[0]+=delta*.0125f;values[0]=fminf(1,fmaxf(0,values[0]));}
    }
    values[2]=gpio_get_level(VPE_MUTE_SENSE);
    unsigned button=gpio_get_level(VPE_BUTTON)==0;
    if(button!=candidate){candidate=button;stable=0;}
    else if(stable<2 && ++stable==2)values[1]=(float)button;
    for(unsigned i=0;i<3;++i)if(!sent_once[i]||values[i]!=sent[i]){
        if(publish(i,values[i])){sent[i]=values[i];sent_once[i]=true;}
    }
    float rgb[36]={0};unsigned lit=(unsigned)(values[0]*12+.5f);
    for(unsigned i=0;i<12;++i){rgb[i*3]=fault?.7f:paused?.2f:0;rgb[i*3+1]=!fault&&i<lit?.25f:0;rgb[i*3+2]=!fault&&i<lit?.35f:0;}
    voice_pe_led_frame(rgb);voice_pe_led_poll();
}
void voice_pe_runtime_status(cJSON *parent)
{
    cJSON_AddNumberToObject(parent,"voice_pe_inputs_version",ready?1:0);
    cJSON *o=cJSON_AddObjectToObject(parent,"voice_pe_controls");
    cJSON_AddBoolToObject(o,"ready",ready);cJSON_AddNumberToObject(o,"dial",values[0]);
    cJSON_AddNumberToObject(o,"button",values[1]);cJSON_AddNumberToObject(o,"microphone_mute",values[2]);
    cJSON_AddNumberToObject(o,"encoder_count",previous_count);
    cJSON_AddStringToObject(o,"ring_owner","board status and dial; no RNBO LED messages");
}
