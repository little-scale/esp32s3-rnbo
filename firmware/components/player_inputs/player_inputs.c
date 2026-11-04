// SPDX-License-Identifier: MIT
#include "player_inputs.h"
#include "cJSON.h"
#include "driver/gpio.h"
#include "driver/touch_sens.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_timer.h"
#include <stdio.h>
#include <string.h>

static player_input_plan current;
static player_input_state states[PLAYER_INPUT_MAX];
static adc_oneshot_unit_handle_t adc;
static touch_sensor_handle_t touch;
static touch_channel_handle_t touch_channels[PLAYER_INPUT_MAX];
static bool touch_enabled,touch_scanning,valid[PLAYER_INPUT_MAX];
static int64_t last_scan;
static unsigned scans,scan_us,peak_scan_us,read_errors[PLAYER_INPUT_MAX];
static char startup_error[128];

static void close_inputs(void)
{
    if(touch_scanning)(void)touch_sensor_stop_continuous_scanning(touch);
    if(touch_enabled)(void)touch_sensor_disable(touch);
    for(unsigned i=0;i<PLAYER_INPUT_MAX;++i)if(touch_channels[i]) {
        (void)touch_sensor_del_channel(touch_channels[i]);touch_channels[i]=NULL;
    }
    if(touch){(void)touch_sensor_del_controller(touch);touch=NULL;}
    if(adc){(void)adc_oneshot_del_unit(adc);adc=NULL;}
    for(unsigned i=0;i<current.count;++i)(void)gpio_reset_pin(current.bindings[i].gpio);
    touch_enabled=touch_scanning=false;memset(&current,0,sizeof current);
}
bool player_inputs_open(const player_input_plan *plan,char *error,size_t capacity)
{
    close_inputs();current=*plan;
    memset(states,0,sizeof states);memset(valid,0,sizeof valid);memset(read_errors,0,sizeof read_errors);
    startup_error[0]=0;last_scan=0;scans=scan_us=peak_scan_us=0;
    esp_err_t r=ESP_OK;
    bool need_adc=false,need_touch=false;
    for(unsigned i=0;i<plan->count;++i){need_adc|=plan->bindings[i].kind==PLAYER_INPUT_ANALOG;need_touch|=plan->bindings[i].kind==PLAYER_INPUT_TOUCH;}
    if(need_adc) {
        adc_oneshot_unit_init_cfg_t cfg={.unit_id=ADC_UNIT_1,.ulp_mode=ADC_ULP_MODE_DISABLE};
        r=adc_oneshot_new_unit(&cfg,&adc);if(r!=ESP_OK)goto fail;
    }
    if(need_touch) {
        touch_sensor_sample_config_t sample=TOUCH_SENSOR_V2_DEFAULT_SAMPLE_CONFIG(500,TOUCH_VOLT_LIM_L_0V5,TOUCH_VOLT_LIM_H_2V2);
        touch_sensor_config_t cfg=TOUCH_SENSOR_DEFAULT_BASIC_CONFIG(1,&sample);
        r=touch_sensor_new_controller(&cfg,&touch);if(r!=ESP_OK)goto fail;
    }
    for(unsigned i=0;i<plan->count;++i) {
        const player_input_binding *b=&plan->bindings[i];
        if(b->kind==PLAYER_INPUT_ANALOG) {
            adc_oneshot_chan_cfg_t cfg={.atten=ADC_ATTEN_DB_12,.bitwidth=ADC_BITWIDTH_12};
            /* Admitted GPIO1..6 are ADC1 channels0..5 on ESP32-S3. */
            r=adc_oneshot_config_channel(adc,(adc_channel_t)(b->gpio-1),&cfg);
        } else if(b->kind==PLAYER_INPUT_DIGITAL) {
            gpio_config_t cfg={.pin_bit_mask=1ULL<<b->gpio,.mode=GPIO_MODE_INPUT,
                .pull_up_en=b->pull>0?GPIO_PULLUP_ENABLE:GPIO_PULLUP_DISABLE,
                .pull_down_en=b->pull<0?GPIO_PULLDOWN_ENABLE:GPIO_PULLDOWN_DISABLE,.intr_type=GPIO_INTR_DISABLE};
            r=gpio_config(&cfg);
        } else {
            touch_channel_config_t cfg={.active_thresh={2000},.charge_speed=TOUCH_CHARGE_SPEED_7,.init_charge_volt=TOUCH_INIT_CHARGE_VOLT_DEFAULT};
            /* ESP32-S3 touch channel number equals its GPIO number. */
            r=touch_sensor_new_channel(touch,b->gpio,&cfg,&touch_channels[i]);
        }
        if(r!=ESP_OK)goto fail;
    }
    if(need_touch) {
        touch_sensor_filter_config_t filter=TOUCH_SENSOR_DEFAULT_FILTER_CONFIG();
        r=touch_sensor_config_filter(touch,&filter);if(r!=ESP_OK)goto fail;
        r=touch_sensor_enable(touch);if(r!=ESP_OK)goto fail;touch_enabled=true;
        r=touch_sensor_start_continuous_scanning(touch);if(r!=ESP_OK)goto fail;touch_scanning=true;
    }
    return true;
fail:
    snprintf(startup_error,sizeof startup_error,"Physical inputs unavailable: %s",esp_err_to_name(r));
    if(error&&capacity)snprintf(error,capacity,"%s",startup_error);
    close_inputs();return false;
}
void player_inputs_poll(int64_t now,void (*publish)(unsigned,float))
{
    if(!current.count||now-last_scan<PLAYER_INPUT_SCAN_US)return;
    last_scan=now;int64_t began=esp_timer_get_time();++scans;
    for(unsigned i=0;i<current.count;++i) {
        const player_input_binding *b=&current.bindings[i];uint32_t raw=0;esp_err_t r=ESP_OK;
        if(b->kind==PLAYER_INPUT_ANALOG) {
            int value=0;r=adc_oneshot_read(adc,(adc_channel_t)(b->gpio-1),&value);if(r==ESP_OK)raw=(uint32_t)value;
        } else if(b->kind==PLAYER_INPUT_DIGITAL)raw=(uint32_t)gpio_get_level(b->gpio);
        else r=touch_channel_read_data(touch_channels[i],TOUCH_CHAN_DATA_TYPE_SMOOTH,&raw);
        valid[i]=r==ESP_OK && (b->kind!=PLAYER_INPUT_TOUCH||raw!=0);
        if(!valid[i]){++read_errors[i];continue;}
        float value;
        if(player_input_sample(b,&states[i],raw,now,&value))publish(b->parameter_index,value);
    }
    scan_us=(unsigned)(esp_timer_get_time()-began);if(scan_us>peak_scan_us)peak_scan_us=scan_us;
}
void player_inputs_add_status(cJSON *parent)
{
    cJSON *o=cJSON_AddObjectToObject(parent,"physical_inputs");
    cJSON_AddNumberToObject(o,"version",1);cJSON_AddNumberToObject(o,"scan_interval_us",PLAYER_INPUT_SCAN_US);
    cJSON_AddNumberToObject(o,"scans",scans);cJSON_AddNumberToObject(o,"scan_us",scan_us);cJSON_AddNumberToObject(o,"peak_scan_us",peak_scan_us);
    if(startup_error[0])cJSON_AddStringToObject(o,"error",startup_error);
    cJSON *rows=cJSON_AddArrayToObject(o,"bindings");
    for(unsigned i=0;i<current.count;++i) {
        const player_input_binding *b=&current.bindings[i];const player_input_state *s=&states[i];
        cJSON *row=cJSON_CreateObject();cJSON_AddNumberToObject(row,"index",b->parameter_index);
        cJSON_AddStringToObject(row,"pin",b->pin);cJSON_AddNumberToObject(row,"gpio",b->gpio);
        cJSON_AddStringToObject(row,"type",b->kind==PLAYER_INPUT_ANALOG?"analog":b->kind==PLAYER_INPUT_DIGITAL?"digital":"touch");
        cJSON_AddBoolToObject(row,"valid",valid[i]);cJSON_AddNumberToObject(row,"raw",s->raw);
        cJSON_AddBoolToObject(row,"ready",s->sent_once);cJSON_AddNumberToObject(row,"normalized",s->sent);
        cJSON_AddNumberToObject(row,"read_errors",read_errors[i]);
        if(b->kind==PLAYER_INPUT_TOUCH){cJSON_AddNumberToObject(row,"calibration_samples",s->calibration_samples);cJSON_AddNumberToObject(row,"baseline",s->baseline);}
        cJSON_AddItemToArray(rows,row);
    }
}
