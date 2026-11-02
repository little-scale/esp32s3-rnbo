/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once
#include "esp_err.h"
#include <stdbool.h>
#include <stdint.h>
typedef struct {
    void (*panic)(void);
    void (*resume)(void);
    bool (*volume)(unsigned percent);
    bool (*parameter)(unsigned index,float normalized);
    bool (*parameter_value)(unsigned index,float *actual,float *normalized);
    unsigned initial_volume;
    const char *source_label;
} board_display_actions;
/* Called on core0 before enabling audio DMA. All callbacks are bounded shell
 * atomics/queue operations. No callback may call a live RNBO instance. */
esp_err_t board_display_start(const board_display_actions *actions);
void board_display_update(bool muted, bool fault, unsigned volume_percent,
                          uint32_t render_us, uint32_t peak_us);
