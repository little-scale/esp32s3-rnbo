/* SPDX-License-Identifier: MIT */
#pragma once
#include "esp_err.h"
#include "lvgl.h"
bool bsp_display_lock(unsigned timeout);
void bsp_display_unlock(void);
esp_err_t bsp_display_brightness_set(unsigned value);
