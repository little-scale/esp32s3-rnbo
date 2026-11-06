/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once
#include "esp_err.h"
#include <stdbool.h>
#include <stdint.h>
#include "patch_layout.h"
#ifdef RNBO_S3_PLAYER
#include "player_inputs.h"
#endif
typedef struct {
    void (*panic)(void);
    void (*resume)(void);
    bool (*volume)(unsigned percent);
    bool (*parameter)(unsigned index,float normalized);
    bool (*parameter_value)(unsigned index,float *actual,float *normalized);
    uint32_t (*input_epoch)(void); /* Invalidates held gestures after pause/maintenance. */
    unsigned initial_volume;
    const char *source_label;
} board_display_actions;
/* Called on core0 before enabling audio DMA. All callbacks are bounded shell
 * atomics/queue operations. No callback may call a live RNBO instance. */
esp_err_t board_display_start(const board_display_actions *actions);
void board_display_update(bool muted, bool fault, unsigned volume_percent,
                          uint32_t render_us, uint32_t peak_us,unsigned output_peak_q15);
#ifdef RNBO_S3_PLAYER
/* Call from the control owner during maintenance, never from audio. All input
 * strings/layout/labels are copied; visual may be NULL or invalid (fallback).
 * Callbacks continue to use root-owned generation-safe atomics, not an image. */
esp_err_t board_display_player_layout(const char *title,const char *source_sha256,
                                     const cJSON *visual,const patch_parameter *labels,
                                     unsigned count,const player_screen_plan *touchscreen);
#endif
