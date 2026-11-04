// SPDX-License-Identifier: MIT
#pragma once
#include "esp_wifi.h"
#include <stdbool.h>
#include <stddef.h>
typedef struct cJSON cJSON;
enum { PLAYER_WIFI_SCAN_MAX=24 };
bool player_wifi_scan_results(cJSON *parent,const wifi_ap_record_t *records,size_t count);
