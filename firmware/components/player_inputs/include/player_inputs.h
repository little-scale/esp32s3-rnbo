// SPDX-License-Identifier: MIT
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct cJSON cJSON;
enum { PLAYER_INPUT_MAX = 16, PLAYER_INPUT_SCAN_US = 4000 };
typedef enum { PLAYER_INPUT_ANALOG, PLAYER_INPUT_DIGITAL, PLAYER_INPUT_TOUCH } player_input_kind;
typedef struct {
    unsigned parameter_index;
    player_input_kind kind;
    char pin[8];
    int gpio, pull; /* -1 down, 0 none, 1 up */
    bool invert, active_low;
    unsigned raw_min, raw_max, debounce_ms;
    float smooth_ms, deadband, threshold, hysteresis;
} player_input_binding;
typedef struct { unsigned count; player_input_binding bindings[PLAYER_INPUT_MAX]; } player_input_plan;
typedef struct {
    float raw, filtered, sent, baseline, baseline_sum;
    int64_t previous_us, candidate_us;
    unsigned calibration_samples;
    bool sampled, sent_once, candidate, stable, stable_once, touched;
} player_input_state;

/* Pure admission and signal conditioning, also exercised by native tests.
 * id_at borrows a stable parameter ID; no module access occurs in this code. */
bool player_inputs_plan_parse(const cJSON *metadata, bool xiao, int bclk, int ws, int dout,
                             unsigned parameter_count, const char *(*id_at)(void *, unsigned), void *context,
                             player_input_plan *plan, char *error, size_t capacity);
/* A failed read must not call sample. Touch calibrates from 64 nonzero scans. */
bool player_input_sample(const player_input_binding *binding, player_input_state *state,
                         uint32_t raw, int64_t now_us, float *normalized);

/* One control owner only. Reconfigure while audio is parked; no driver call,
 * JSON operation or allocation is permitted from the audio callback. Opening
 * an empty plan only closes old inputs. No physical pin is touched at startup
 * unless the active package explicitly binds it. */
bool player_inputs_open(const player_input_plan *plan, char *error, size_t capacity);
void player_inputs_poll(int64_t now_us, void (*publish)(unsigned index, float normalized));
void player_inputs_add_status(cJSON *parent);
