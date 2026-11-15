/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once
#include "esp_err.h"
#include <stdbool.h>
#include <stddef.h>
typedef struct cJSON cJSON;
esp_err_t voice_pe_runtime_init(void);
bool voice_pe_runtime_ready(void);
void voice_pe_runtime_poll(bool reset,bool paused,bool fault,bool (*publish)(unsigned,float));
void voice_pe_runtime_values(float values[3]);
void voice_pe_runtime_status(cJSON *parent);
esp_err_t voice_pe_led_init(void);
void voice_pe_led_poll(void);
void voice_pe_led_frame(const float rgb[36]);
