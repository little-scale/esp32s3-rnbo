/* SPDX-License-Identifier: MIT */
#pragma once
#include "allocation_probe.h"
#include "esp_log.h"
#include <stdlib.h>
#define CHECK(c) do { if (!(c)) { allocation_probe_end();ESP_LOGE("rnbo_object_benchmark","FAIL file=%s line=%d condition=%s",__FILE__,__LINE__,#c);abort(); } } while(0)
