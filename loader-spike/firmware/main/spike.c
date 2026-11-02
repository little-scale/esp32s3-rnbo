/* SPDX-License-Identifier: MIT */
#include "spike_abi.h"
#include "esp_elf.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_memory_utils.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

static const char *TAG = "rnbo_loader_spike";
extern const uint8_t payload_start[] asm("_binary_spike_payload_bin_start");
extern const uint8_t payload_end[] asm("_binary_spike_payload_bin_end");
extern const uint8_t bad_start[] asm("_binary_spike_bad_payload_bin_start");
extern const uint8_t bad_end[] asm("_binary_spike_bad_payload_bin_end");
#define CHECK(condition) do { if (!(condition)) { ESP_LOGE(TAG, "FAIL line %d: %s", __LINE__, #condition); abort(); } } while (0)
static int integer_callback(int a, int b) { return a + b; }
static float float_callback(float value) { return value * 0.5f; }
static int host_marker(int value) { return value ^ 0x5a; }
/* One explicitly named import only. Libc, IDF and customer tables are disabled. */
static const struct esp_elfsym imports[] = {
    ESP_ELFSYM_EXPORT_NAMED("rnbo_spike_host_marker", host_marker), ESP_ELFSYM_END
};
static float input[SPIKE_FRAMES], output[SPIKE_FRAMES];

static void negative_cases(void) {
    esp_elf_t elf;
    CHECK(esp_elf_init(&elf) == 0);
    CHECK(esp_elf_relocate(&elf, payload_start, 16) != 0);
    esp_elf_deinit(&elf);
    CHECK(esp_elf_init(&elf) == 0);
    CHECK(esp_elf_relocate(&elf, bad_start, (size_t)(bad_end - bad_start)) != 0);
    esp_elf_deinit(&elf);
    CHECK(elf_find_sym("printf") == 0);
    CHECK(elf_find_sym("esp_restart") == 0);
    CHECK(elf_find_sym("rnbo_spike_unapproved_import") == 0);
}

static void load_one(esp_elf_t *elf, spike_host *host, spike_module *module) {
    CHECK(esp_elf_init(elf) == 0);
    CHECK(esp_elf_relocate(elf, payload_start, (size_t)(payload_end - payload_start)) == 0);
    CHECK(esp_elf_runtime_base(elf) != 0);
    spike_handshake request = {sizeof(request), host, module};
    char *arguments[] = {(char *)&request};
    CHECK(esp_elf_request(elf, 0, 1, arguments) == 0);
    CHECK(module->struct_bytes == sizeof(*module) && module->abi == SPIKE_ABI);
    CHECK(module->constructor_count == 1 && module->startup_stage == 42);
    CHECK(module->initialized_data == 37 && module->readonly_constant == 0.5f);
    CHECK(module->readonly_data && module->readonly_data[0] == 0.25f && module->readonly_data[3] == 1.0f);
    CHECK(module->bss_address && module->process && module->run_count);
    CHECK(module->run_count() == 0);
    /* Entry requests must not run constructor arrays a second time. */
    CHECK(esp_elf_request(elf, 0, 1, arguments) == 0);
    CHECK(module->constructor_count == 1 && module->startup_stage == 42);
}

static void run_one(const spike_module *module, unsigned iteration, float value) {
    for (unsigned i = 0; i < SPIKE_FRAMES; ++i) input[i] = value;
    CHECK(module->process(input, output, SPIKE_FRAMES) == 0);
    for (unsigned i = 0; i < SPIKE_FRAMES; ++i)
        CHECK(isfinite(output[i]) && output[i] == 1.0f + value * 0.375f * iteration);
    CHECK(module->run_count() == iteration);
}

static void cycle(void) {
    esp_elf_t first, second;
    spike_module a = {0}, b = {0};
    volatile uint32_t finalized_a = 0, finalized_b = 0;
    float *state_a = heap_caps_calloc(SPIKE_FRAMES, sizeof(float), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    float *state_b = heap_caps_calloc(SPIKE_FRAMES, sizeof(float), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    CHECK(state_a && state_b && esp_ptr_external_ram(state_a) && esp_ptr_external_ram(state_b));
    spike_host host_a = {sizeof(host_a), SPIKE_ABI, integer_callback, float_callback, state_a, SPIKE_FRAMES, &finalized_a};
    spike_host host_b = {sizeof(host_b), SPIKE_ABI, integer_callback, float_callback, state_b, SPIKE_FRAMES, &finalized_b};
    load_one(&first, &host_a, &a);
    load_one(&second, &host_b, &b);
    CHECK(a.bss_address != b.bss_address && a.process != b.process);
    run_one(&a, 1, 0.25f);
    run_one(&a, 2, 0.25f);
    CHECK(b.run_count() == 0);
    run_one(&b, 1, -0.5f);
    CHECK(a.run_count() == 2);
    /* Processing is detached before finalization; no function pointer from
     * an unloaded image is retained or called. The second stays callable. */
    esp_elf_deinit(&first);
    memset(&a, 0, sizeof(a));
    CHECK(finalized_a == 1 && finalized_b == 0);
    run_one(&b, 2, -0.5f);
    esp_elf_deinit(&second);
    memset(&b, 0, sizeof(b));
    CHECK(finalized_b == 1);
    heap_caps_free(state_a);
    heap_caps_free(state_b);
    CHECK(heap_caps_check_integrity_all(true));
}

void app_main(void) {
    /* Let the USB host re-enumerate and attach before emitting test evidence. */
    vTaskDelay(pdMS_TO_TICKS(2000));
    ESP_LOGI(TAG, "START ABI=%u frames=%u PSRAM executable loader; no audio output", SPIKE_ABI, SPIKE_FRAMES);
    CHECK(((uintptr_t)payload_start & 3u) == 0 && ((uintptr_t)bad_start & 3u) == 0);
    CHECK(esp_elf_register_symbol(imports) == 0);
    negative_cases();
    cycle(); // settle one-time shell allocations before the leak baseline
    vTaskDelay(pdMS_TO_TICKS(20));
    size_t internal_before = heap_caps_get_free_size(MALLOC_CAP_INTERNAL);
    size_t psram_before = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
    for (unsigned i = 0; i < 32; ++i) {
        cycle();
        vTaskDelay(pdMS_TO_TICKS(1));
        CHECK(heap_caps_get_free_size(MALLOC_CAP_SPIRAM) == psram_before);
        CHECK(heap_caps_get_free_size(MALLOC_CAP_INTERNAL) >= internal_before);
    }
    CHECK(esp_elf_unregister_symbol(imports) == 0);
    CHECK(elf_find_sym("rnbo_spike_host_marker") == 0);
    ESP_LOGI(TAG, "PASS cycles=32 modules_per_cycle=2 ctor_once=1 finalizers=1 callbacks=integer,float globals_isolated=1 psram_before=%u psram_after=%u internal_before=%u internal_after=%u",
             (unsigned)psram_before, (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM),
             (unsigned)internal_before, (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL));
}
