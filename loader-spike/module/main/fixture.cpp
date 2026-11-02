/* SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 * SPDX-License-Identifier: Apache-2.0
 * Lifecycle bookkeeping adapted from elf_loader/tests/idf_cpp_lifecycle at
 * d2d935d0ee3e78deffa3981cc8c39ac8f534932b. Added original RNBO port ABI,
 * callbacks, virtual processing, state isolation and import rejection probes. */
#include "spike_abi.h"
#include <stddef.h>

extern "C" __attribute__((visibility("default"))) int rnbo_spike_host_marker(int);
#ifdef SPIKE_BAD_IMPORT
extern "C" __attribute__((visibility("default"))) int rnbo_spike_unapproved_import(int);
#endif
extern "C" { __attribute__((weak)) void *__dso_handle = &__dso_handle; }
struct Finalizer { void (*function)(void *); void *argument; };
static Finalizer finalizers[4];
static unsigned finalizer_count;
extern "C" int __cxa_atexit(void (*function)(void *), void *argument, void *) {
    if (finalizer_count >= 4) return -1;
    finalizers[finalizer_count++] = {function, argument};
    return 0;
}
static uint32_t startup_count, startup_stage;
static volatile uint32_t *finalizer_observer;
__attribute__((constructor(101))) static void early_startup() {
    ++startup_count;
    startup_stage = startup_count == 1 ? 1 : 0xffffffffu;
}
struct Lifecycle {
    Lifecycle() { startup_stage = startup_stage == 1 ? 42 : 0xffffffffu; }
    ~Lifecycle() { if (finalizer_observer) *finalizer_observer = *finalizer_observer + 1; }
};
static Lifecycle lifecycle;
__attribute__((destructor)) static void late_shutdown() {
    while (finalizer_count) {
        Finalizer entry = finalizers[--finalizer_count];
        entry.function(entry.argument);
    }
}
class VoiceBase {
public:
    virtual float sample(float value) const { return value; }
};
class Voice final : public VoiceBase {
public:
    float sample(float value) const override { return value * 0.25f; }
};
static Voice voice;
static VoiceBase *voice_pointer = &voice;
__attribute__((noinline)) static float virtual_sample(const VoiceBase *object, float value) {
    return object->sample(value);
}
static volatile uint32_t initialized_data = 37;
static const float readonly_constants[] = {0.25f, 0.5f, 0.75f, 1.0f};
static float bss_state[SPIKE_FRAMES];
static uint32_t runs;
static const spike_host *services;
static uint32_t run_count() { return runs; }
static int process(const float *input, float *output, uint32_t frames) {
    if (!services || !input || !output || frames != SPIKE_FRAMES) return -1;
    for (uint32_t i = 0; i < frames; ++i) {
        bss_state[i] += input[i];
        services->psram_state[i] += input[i] * 2.0f;
        output[i] = services->float_callback(virtual_sample(voice_pointer,
                    bss_state[i] + services->psram_state[i])) +
                    static_cast<float>(services->integer_callback(2, 6)) * 0.125f;
    }
    ++runs;
    return 0;
}
/* project_elf() maps main to the app_main ELF entry. No POSIX dlopen or
 * fixed-address API table is assumed. All returned addresses expire at unload. */
extern "C" int main(int argc, char *argv[]) {
    if (argc != 1 || !argv || !argv[0]) return -1;
    auto *request = reinterpret_cast<spike_handshake *>(argv[0]);
    if (request->struct_bytes < sizeof(*request) || !request->host || !request->module) return -2;
    const spike_host *host = request->host;
    if (host->struct_bytes < sizeof(*host) || host->abi != SPIKE_ABI ||
        !host->integer_callback || !host->float_callback || !host->psram_state ||
        host->state_frames != SPIKE_FRAMES || !host->finalizer_observer) return -3;
    if (startup_count != 1 || startup_stage != 42 || rnbo_spike_host_marker(23) != (23 ^ 0x5a)) return -4;
#ifdef SPIKE_BAD_IMPORT
    if (rnbo_spike_unapproved_import(23) != 23) return -5;
#endif
    services = host;
    finalizer_observer = host->finalizer_observer;
    *request->module = {sizeof(spike_module), SPIKE_ABI, startup_count, startup_stage,
                       initialized_data, readonly_constants[1], readonly_constants, bss_state, process, run_count};
    return 0;
}
