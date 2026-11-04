// SPDX-License-Identifier: MIT
#include "player_midi.h"
#include "cJSON.h"
#include "driver/uart.h"
#include "driver/gpio.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "nvs.h"
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>

static QueueHandle_t received,uart_events;
static StaticQueue_t received_storage;
static uint8_t received_bytes[PLAYER_MIDI_QUEUE*sizeof(player_midi_message)];
static atomic_uint route_generation,epoch=1,recovered=1,accepted,delivered,dropped_inactive,dropped_no_input,dropped_recovery,overflows;
static atomic_uint bytes_uart,bytes_usb,bytes_test,uart_errors,usb_errors,usb_ignored,recoveries;
static unsigned loopback_runs;
static atomic_bool route_input,playing,usb_connected;
static midi_stream uart_parser,test_parser;
static bool supports_uart,uart_on,uart_saved,active_sensing;
static int64_t last_uart_byte;
static char midi_error[128];

static bool fail(char *error,size_t capacity,const char *text)
{if(error&&capacity)snprintf(error,capacity,"%s",text);snprintf(midi_error,sizeof midi_error,"%s",text);return false;}
static bool uart_open(char *error,size_t capacity)
{
    uart_config_t cfg={.baud_rate=31250,.data_bits=UART_DATA_8_BITS,.parity=UART_PARITY_DISABLE,
        .stop_bits=UART_STOP_BITS_1,.flow_ctrl=UART_HW_FLOWCTRL_DISABLE,.source_clk=UART_SCLK_DEFAULT};
    esp_err_t r=uart_param_config(UART_NUM_1,&cfg);
    if(r==ESP_OK)r=uart_set_pin(UART_NUM_1,UART_PIN_NO_CHANGE,44,UART_PIN_NO_CHANGE,UART_PIN_NO_CHANGE);
    if(r==ESP_OK)r=uart_driver_install(UART_NUM_1,1024,0,16,&uart_events,0);
    if(r!=ESP_OK){gpio_reset_pin(44);return fail(error,capacity,esp_err_to_name(r));}
    gpio_pullup_en(44);uart_on=true;active_sensing=false;midi_stream_init(&uart_parser);return true;
}
static void uart_close(void)
{
    if(uart_on){(void)uart_driver_delete(UART_NUM_1);(void)gpio_reset_pin(44);}
    uart_on=false;uart_events=NULL;active_sensing=false;midi_stream_init(&uart_parser);
}
bool player_midi_init(bool xiao,char *error,size_t capacity)
{
    supports_uart=xiao;
    received=xQueueCreateStatic(PLAYER_MIDI_QUEUE,sizeof(player_midi_message),received_bytes,&received_storage);
    if(!received)return fail(error,capacity,"MIDI queue initialization failed");
    midi_stream_init(&uart_parser);midi_stream_init(&test_parser);
    nvs_handle_t h;uint8_t enabled=0;esp_err_t r=nvs_open("rnbo_midi",NVS_READONLY,&h);
    if(r==ESP_OK){r=nvs_get_u8(h,"uart",&enabled);nvs_close(h);}
    if(r!=ESP_OK&&r!=ESP_ERR_NVS_NOT_FOUND)return fail(error,capacity,"Cannot read MIDI configuration");
    if(enabled>1)return fail(error,capacity,"Invalid saved MIDI configuration");
    uart_saved=enabled!=0;
    return !enabled||!supports_uart||uart_open(error,capacity);
}
bool player_midi_configure_uart(bool enabled,char *error,size_t capacity)
{
    if(!supports_uart)return fail(error,capacity,"UART MIDI requires free D7/GPIO44 on XIAO");
    bool old=uart_on;
    if(enabled==old&&enabled==uart_saved){midi_error[0]=0;return true;}
    if(enabled&&!old&&!uart_open(error,capacity))return false;
    if(!enabled)uart_close();
    nvs_handle_t h;esp_err_t r=nvs_open("rnbo_midi",NVS_READWRITE,&h);
    if(r==ESP_OK){r=nvs_set_u8(h,"uart",enabled?1:0);if(r==ESP_OK)r=nvs_commit(h);nvs_close(h);}
    if(r!=ESP_OK){uart_close();if(old)(void)uart_open(NULL,0);return fail(error,capacity,"Cannot save MIDI configuration");}
    uart_saved=enabled;midi_error[0]=0;player_midi_request_recovery();return true;
}
bool player_midi_uart_enabled(void){return uart_on;}
bool player_midi_has_input(void){return atomic_load(&route_input);}
void player_midi_request_recovery(void)
{if(atomic_load(&route_input))atomic_fetch_add(&epoch,1);}
void player_midi_set_route(unsigned generation,bool has_input)
{
    atomic_store(&route_input,false);atomic_store(&playing,false);
    /* Control owner, audio parked: consume old RX bytes with routing closed so
     * buffered notes cannot be relabelled as belonging to the new package. */
    if(uart_on)for(unsigned i=0;i<8;++i)player_midi_poll(esp_timer_get_time());
    atomic_store(&route_generation,generation);unsigned next=atomic_fetch_add(&epoch,1)+1;
    if(received)xQueueReset(received);
    midi_stream_boundary(&uart_parser);midi_stream_init(&test_parser);
    atomic_store(&recovered,next);atomic_store(&route_input,has_input);
}
void player_midi_set_playing(bool value)
{
    bool old=atomic_exchange(&playing,value);
    if(old&&!value)player_midi_request_recovery();
}
unsigned player_midi_recovery_epoch(void)
{unsigned e=atomic_load(&epoch);return e==atomic_load(&recovered)?0:e;}
void player_midi_recovery_done(unsigned value)
{atomic_store(&recovered,value);atomic_fetch_add(&recoveries,1);}
void player_midi_flush_queue(void){if(received)xQueueReset(received);}
bool player_midi_submit(unsigned source,const uint8_t *bytes,unsigned length)
{
    if(!rnbo_s3_midi_valid(bytes,length))return false;
    unsigned generation=atomic_load(&route_generation),e=atomic_load(&epoch);
    if(!atomic_load(&route_input)){atomic_fetch_add(&dropped_no_input,1);return false;}
    if(!atomic_load(&playing)){atomic_fetch_add(&dropped_inactive,1);return false;}
    if(e!=atomic_load(&recovered)){atomic_fetch_add(&dropped_recovery,1);return false;}
    player_midi_message message={.generation=generation,.epoch=e,.length=(uint8_t)length,.source=(uint8_t)source};
    memcpy(message.bytes,bytes,length);
    if(xQueueSend(received,&message,0)==pdTRUE){atomic_fetch_add(&accepted,1);return true;}
    atomic_fetch_add(&overflows,1);player_midi_request_recovery();return false;
}
bool player_midi_receive(player_midi_message *message)
{
    /* Bound work even if a pre-reset producer finishes a stale enqueue later. */
    for(unsigned i=0;i<PLAYER_MIDI_QUEUE&&xQueueReceive(received,message,0)==pdTRUE;++i)
        if(message->generation==atomic_load(&route_generation)&&message->epoch==atomic_load(&epoch))return true;
    return false;
}
void player_midi_delivered(void){atomic_fetch_add(&delivered,1);}
static void emit(void *context,const uint8_t *bytes,unsigned length)
{(void)player_midi_submit((unsigned)(uintptr_t)context,bytes,length);}
void player_midi_stream_test(const uint8_t *bytes,size_t count)
{atomic_fetch_add(&bytes_test,(unsigned)count);midi_stream_bytes(&test_parser,bytes,count,emit,(void *)(uintptr_t)PLAYER_MIDI_TEST);}
bool player_midi_uart_loopback(const uint8_t *bytes,size_t count,char *error,size_t capacity)
{
    if(!uart_on||!count||count>128)return fail(error,capacity,"Internal loopback needs UART enabled and 1..128 bytes");
    /* UART1 TX has never been routed to a GPIO. The peripheral feeds its TX
     * signal directly to RX for this explicit diagnostic, then restores RX. */
    esp_err_t r=uart_set_loop_back(UART_NUM_1,true);
    if(r!=ESP_OK)return fail(error,capacity,esp_err_to_name(r));
    int written=uart_write_bytes(UART_NUM_1,bytes,count);
    r=uart_wait_tx_done(UART_NUM_1,pdMS_TO_TICKS(100));
    esp_err_t reset=uart_set_loop_back(UART_NUM_1,false);
    if(written!=(int)count||r!=ESP_OK||reset!=ESP_OK)return fail(error,capacity,"UART loopback transfer failed");
    ++loopback_runs;return true;
}
void player_midi_poll(int64_t now)
{
    if(!uart_on)return;
    uart_event_t event;
    for(unsigned i=0;i<16&&xQueueReceive(uart_events,&event,0)==pdTRUE;++i) {
        if(event.type==UART_FIFO_OVF||event.type==UART_BUFFER_FULL||event.type==UART_PARITY_ERR||event.type==UART_FRAME_ERR||event.type==UART_BREAK) {
            atomic_fetch_add(&uart_errors,1);player_midi_request_recovery();
            uart_flush_input(UART_NUM_1);midi_stream_init(&uart_parser);
        }
    }
    uint8_t bytes[128];int count=uart_read_bytes(UART_NUM_1,bytes,sizeof bytes,0);
    if(count>0) {
        atomic_fetch_add(&bytes_uart,(unsigned)count);last_uart_byte=now;
        for(int i=0;i<count;++i)if(bytes[i]==0xfe)active_sensing=true;
        midi_stream_bytes(&uart_parser,bytes,(size_t)count,emit,(void *)(uintptr_t)PLAYER_MIDI_UART);
    }
    if(active_sensing&&now-last_uart_byte>350000){active_sensing=false;player_midi_request_recovery();}
}
void player_midi_usb_state(bool connected,unsigned errors,unsigned ignored)
{
    bool was=atomic_exchange(&usb_connected,connected);
    atomic_fetch_add(&usb_errors,errors);atomic_fetch_add(&usb_ignored,ignored);
    if(was&&!connected)player_midi_request_recovery();
}
/* Called by the USB driver for complete packets, never from the audio task. */
void player_midi_usb_bytes(unsigned count){atomic_fetch_add(&bytes_usb,count);}
void player_midi_add_status(cJSON *parent)
{
    cJSON *o=cJSON_AddObjectToObject(parent,"midi");cJSON_AddNumberToObject(o,"version",1);
    cJSON_AddBoolToObject(o,"uart_supported",supports_uart);cJSON_AddBoolToObject(o,"uart_enabled",uart_on);
    cJSON_AddNumberToObject(o,"uart_rx_gpio",44);cJSON_AddStringToObject(o,"uart_rx_pin","D7");cJSON_AddNumberToObject(o,"uart_baud",31250);
#ifdef CONFIG_RNBO_S3_USB_MIDI_HOST
    cJSON_AddBoolToObject(o,"usb_host_compiled",true);
#else
    cJSON_AddBoolToObject(o,"usb_host_compiled",false);
#endif
    cJSON_AddBoolToObject(o,"usb_connected",atomic_load(&usb_connected));cJSON_AddBoolToObject(o,"patch_input_supported",atomic_load(&route_input));
    cJSON_AddBoolToObject(o,"playing",atomic_load(&playing));cJSON_AddBoolToObject(o,"recovery_pending",player_midi_recovery_epoch()!=0);
    cJSON_AddNumberToObject(o,"queue_capacity",PLAYER_MIDI_QUEUE);cJSON_AddNumberToObject(o,"queue_used",received?uxQueueMessagesWaiting(received):0);
#define COUNTER(name) cJSON_AddNumberToObject(o,#name,atomic_load(&name))
    COUNTER(accepted);COUNTER(delivered);COUNTER(dropped_inactive);COUNTER(dropped_no_input);COUNTER(dropped_recovery);COUNTER(overflows);
    COUNTER(bytes_uart);COUNTER(bytes_usb);COUNTER(bytes_test);COUNTER(uart_errors);COUNTER(usb_errors);COUNTER(usb_ignored);COUNTER(recoveries);
#undef COUNTER
    cJSON_AddNumberToObject(o,"uart_malformed",uart_parser.malformed);cJSON_AddNumberToObject(o,"uart_sysex_bytes",uart_parser.sysex_bytes);
    cJSON_AddNumberToObject(o,"uart_loopback_runs",loopback_runs);
    if(midi_error[0])cJSON_AddStringToObject(o,"error",midi_error);
}
#ifndef CONFIG_RNBO_S3_USB_MIDI_HOST
bool player_usb_midi_start(char *error,size_t capacity)
{(void)error;(void)capacity;return true;}
#endif
