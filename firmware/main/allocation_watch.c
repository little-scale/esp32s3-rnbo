/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "allocation_watch.h"
#include "sdkconfig.h"
#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_attr.h"
#include "esp_heap_caps.h"
#include "esp_memory_utils.h"

static allocation_watch_stats phases[3];
#ifdef CONFIG_RNBO_S3_ALLOCATION_WATCH
_Static_assert(sizeof(TaskHandle_t)==sizeof(unsigned), "Task handle must fit a lock-free integer");
/* Xtensa GCC advertises conditional lock freedom. Only aligned loads/stores
 * are used here; build_firmware.py checks this object's undefined symbols for
 * unexpected atomic/locking calls. Counters have a single non-ISR owner. */
_Alignas(4) static atomic_uint watched_task;
_Alignas(4) static atomic_uint watched_phase;

static unsigned IRAM_ATTR active_phase(void)
{
    unsigned phase=atomic_load_explicit(&watched_phase,memory_order_acquire);
    if (!phase || xPortInIsrContext()) return 0;
    if ((unsigned)(uintptr_t)xTaskGetCurrentTaskHandle()!=atomic_load_explicit(&watched_task,memory_order_relaxed)) return 0;
    return phase;
}

/* IDF 5.5 invokes these hooks after successful heap operations. They never
 * allocate, block, log, or call module code. Only the watched owner writes its
 * phase's counters, and that same owner snapshots them outside heap calls. */
void esp_heap_trace_alloc_hook(void *ptr, size_t bytes, uint32_t caps)
{
    (void)caps;
    unsigned phase=active_phase();
    if (!ptr || !phase) return;
    allocation_watch_stats *s=&phases[phase];
    ++s->allocations;
    s->requested_bytes+=bytes;
    if (esp_ptr_external_ram(ptr)) s->external_bytes+=bytes;
    else s->internal_bytes+=bytes;
}

void esp_heap_trace_free_hook(void *ptr)
{
    unsigned phase=active_phase();
    if (ptr && phase) ++phases[phase].frees;
}
#endif

void allocation_watch_start(unsigned phase)
{
#ifdef CONFIG_RNBO_S3_ALLOCATION_WATCH
    if (phase!=ALLOCATION_WATCH_PREPARE && phase!=ALLOCATION_WATCH_AUDIO) return;
    atomic_store_explicit(&watched_task,(unsigned)(uintptr_t)xTaskGetCurrentTaskHandle(),memory_order_relaxed);
    atomic_store_explicit(&watched_phase,phase,memory_order_release);
#else
    (void)phase;
#endif
}
void allocation_watch_stop(void)
{
#ifdef CONFIG_RNBO_S3_ALLOCATION_WATCH
    atomic_store_explicit(&watched_phase,0,memory_order_release);
#endif
}
allocation_watch_stats allocation_watch_snapshot(unsigned phase)
{
    if (phase!=ALLOCATION_WATCH_PREPARE && phase!=ALLOCATION_WATCH_AUDIO)
        return (allocation_watch_stats){0};
    return phases[phase];
}
