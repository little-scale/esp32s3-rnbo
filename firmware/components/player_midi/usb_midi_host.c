// SPDX-License-Identifier: MIT
/* Experimental class-compliant USB MIDI1 IN: one device/interface, cable0.
 * All Client API calls and transfer lifetime changes belong to client_task.
 * No GPIO is used to source VBUS; suitable external host power is required. */
#include "player_midi.h"
#include "usb/usb_host.h"
#include "esp_intr_alloc.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <stdatomic.h>
#include <stdio.h>

static struct {
    usb_host_client_handle_t client;
    usb_device_handle_t device;
    usb_transfer_t *transfer;
    midi_usb1_endpoint endpoint;
    uint8_t address;
    bool claimed,pending,submit,closing,halted;
} host;
static atomic_int client_result=ESP_ERR_NOT_FINISHED;
static atomic_bool stop_daemon,daemon_stopped;

static void event_callback(const usb_host_client_event_msg_t *event,void *context)
{
    (void)context;
    if(event->event==USB_HOST_CLIENT_EVENT_NEW_DEV) {
        if(!host.device&&!host.address)host.address=event->new_dev.address;
    } else if(event->event==USB_HOST_CLIENT_EVENT_DEV_GONE&&event->dev_gone.dev_hdl==host.device) {
        host.closing=true;player_midi_usb_state(false,0,0);
    }
}
static void transfer_callback(usb_transfer_t *transfer)
{
    host.pending=false;
    if(host.closing)return;
    if(transfer->status!=USB_TRANSFER_STATUS_COMPLETED) {
        host.closing=true;player_midi_usb_state(false,1,0);return;
    }
    unsigned errors=0,ignored=0;
    player_midi_usb_bytes((unsigned)transfer->actual_num_bytes);
    if(transfer->actual_num_bytes%4)++errors;
    else for(int i=0;i<transfer->actual_num_bytes;i+=4) {
        uint8_t bytes[3];unsigned length;
        int result=midi_usb1_packet(transfer->data_buffer+i,bytes,&length);
        if(result==MIDI_USB_MESSAGE)(void)player_midi_submit(PLAYER_MIDI_USB,bytes,length);
        else if(result==MIDI_USB_INVALID)++errors;
        else ++ignored;
    }
    player_midi_usb_state(true,errors,ignored);host.submit=true;
}
static void close_device(void)
{
    if(!host.halted&&host.claimed) {
        /* Flush causes any queued transfer to complete through the callback.
         * Never free its DMA buffer while a transfer remains in flight. */
        (void)usb_host_endpoint_halt(host.device,host.endpoint.endpoint);
        (void)usb_host_endpoint_flush(host.device,host.endpoint.endpoint);host.halted=true;
    }
    if(host.pending)return;
    if(host.transfer){(void)usb_host_transfer_free(host.transfer);host.transfer=NULL;}
    if(host.claimed){(void)usb_host_interface_release(host.client,host.device,host.endpoint.interface);host.claimed=false;}
    if(host.device){(void)usb_host_device_close(host.client,host.device);host.device=NULL;}
    host.address=0;host.closing=host.halted=host.submit=false;
}
static void open_device(void)
{
    esp_err_t r=usb_host_device_open(host.client,host.address,&host.device);
    if(r!=ESP_OK){host.address=0;player_midi_usb_state(false,1,0);return;}
    const usb_config_desc_t *config=NULL;
    r=usb_host_get_active_config_descriptor(host.device,&config);
    if(r!=ESP_OK||!config||!midi_usb1_find_endpoint((const uint8_t *)config,config->wTotalLength,&host.endpoint)) {
        player_midi_usb_state(false,0,1);host.closing=true;return;
    }
    r=usb_host_interface_claim(host.client,host.device,host.endpoint.interface,host.endpoint.alternate);
    if(r!=ESP_OK){player_midi_usb_state(false,1,0);host.closing=true;return;}
    host.claimed=true;
    r=usb_host_transfer_alloc(host.endpoint.packet_bytes,0,&host.transfer);
    if(r!=ESP_OK){player_midi_usb_state(false,1,0);host.closing=true;return;}
    host.transfer->device_handle=host.device;host.transfer->bEndpointAddress=host.endpoint.endpoint;
    host.transfer->callback=transfer_callback;host.transfer->num_bytes=host.endpoint.packet_bytes;
    player_midi_usb_state(true,0,0);host.submit=true;
}
static void client_task(void *unused)
{
    (void)unused;
    usb_host_client_config_t cfg={.is_synchronous=false,.max_num_event_msg=8,
        .async={.client_event_callback=event_callback,.callback_arg=NULL}};
    esp_err_t r=usb_host_client_register(&cfg,&host.client);
    atomic_store(&client_result,r);
    if(r!=ESP_OK){player_midi_usb_state(false,1,0);vTaskDelete(NULL);return;}
    for(;;) {
        r=usb_host_client_handle_events(host.client,pdMS_TO_TICKS(10));
        if(r!=ESP_OK&&r!=ESP_ERR_TIMEOUT){player_midi_usb_state(false,1,0);host.closing=host.device!=NULL;}
        if(host.address&&!host.device)open_device();
        if(host.closing){close_device();continue;}
        if(host.submit&&host.transfer&&!host.pending) {
            host.submit=false;host.pending=true;
            r=usb_host_transfer_submit(host.transfer);
            if(r!=ESP_OK){host.pending=false;host.closing=true;player_midi_usb_state(false,1,0);}
        }
    }
}
static void daemon_task(void *unused)
{
    (void)unused;
    while(!atomic_load(&stop_daemon)) {
        uint32_t flags=0;
        esp_err_t r=usb_host_lib_handle_events(pdMS_TO_TICKS(100),&flags);
        if(r!=ESP_OK&&r!=ESP_ERR_TIMEOUT)player_midi_usb_state(false,1,0);
        if(flags&USB_HOST_LIB_EVENT_FLAGS_NO_CLIENTS)(void)usb_host_device_free_all();
    }
    atomic_store(&daemon_stopped,true);vTaskDelete(NULL);
}
bool player_usb_midi_start(char *error,size_t capacity)
{
    usb_host_config_t cfg={.skip_phy_setup=false,.intr_flags=ESP_INTR_FLAG_LEVEL1};
    esp_err_t r=usb_host_install(&cfg);
    if(r!=ESP_OK)goto fail;
    if(xTaskCreatePinnedToCore(daemon_task,"rnbo_usb_host",8192,NULL,8,NULL,0)!=pdPASS) {
        r=ESP_ERR_NO_MEM;(void)usb_host_uninstall();goto fail;
    }
    if(xTaskCreatePinnedToCore(client_task,"rnbo_usb_midi",8192,NULL,5,NULL,0)!=pdPASS) {
        r=ESP_ERR_NO_MEM;atomic_store(&stop_daemon,true);
        for(unsigned i=0;i<100&&!atomic_load(&daemon_stopped);++i)vTaskDelay(pdMS_TO_TICKS(2));
        (void)usb_host_device_free_all();(void)usb_host_uninstall();goto fail;
    }
    for(unsigned i=0;i<500&&atomic_load(&client_result)==ESP_ERR_NOT_FINISHED;++i)vTaskDelay(pdMS_TO_TICKS(2));
    r=atomic_load(&client_result);if(r==ESP_OK)return true;
fail:
    player_midi_usb_state(false,1,0);
    if(error&&capacity)snprintf(error,capacity,"USB MIDI host unavailable: %s",esp_err_to_name(r));
    return false;
}
