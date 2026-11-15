/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once
#include "esp_err.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "rnbo_s3_led.h"
typedef struct cJSON cJSON;
esp_err_t voice_pe_runtime_init(void);
bool voice_pe_runtime_ready(void);
void voice_pe_runtime_poll(bool reset,bool paused,bool fault,bool (*publish)(unsigned,float));
void voice_pe_runtime_values(float values[3]);
void voice_pe_runtime_status(cJSON *parent);
void voice_pe_runtime_ring(uint32_t generation,bool owned,const rnbo_s3_led_frame *frame,bool fresh);
bool voice_pe_led_healthy(void);
esp_err_t voice_pe_led_init(void);
void voice_pe_led_poll(void);
void voice_pe_led_frame(const float rgb[36]);
