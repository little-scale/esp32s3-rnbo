/* SPDX-License-Identifier: MIT */
#pragma once
#include "lvgl.h"
lv_obj_t *patch_view_create(lv_obj_t *parent,void (*select)(unsigned index));
void patch_view_select(unsigned index);
LV_FONT_DECLARE(rnbo_barlow_12);
LV_FONT_DECLARE(rnbo_barlow_14);
LV_FONT_DECLARE(rnbo_barlow_16);
LV_FONT_DECLARE(rnbo_barlow_22);
