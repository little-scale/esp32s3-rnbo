/* SPDX-License-Identifier: MIT */
#include "allocation_probe.h"
#include "esp_heap_caps.h"
#include "esp_attr.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <stdatomic.h>
#include <stdint.h>

_Alignas(4) static atomic_uint watched_task,enabled;
static uint32_t allocations,frees;
static int IRAM_ATTR watched(void)
{
    return atomic_load_explicit(&enabled,memory_order_acquire) && !xPortInIsrContext() &&
        (uintptr_t)xTaskGetCurrentTaskHandle()==atomic_load_explicit(&watched_task,memory_order_relaxed);
}
void esp_heap_trace_alloc_hook(void *pointer,size_t bytes,uint32_t capabilities)
{
    (void)bytes;(void)capabilities;
    if (pointer && watched()) ++allocations;
}
void esp_heap_trace_free_hook(void *pointer)
{
    if (pointer && watched()) ++frees;
}
void allocation_probe_begin(void)
{
    atomic_store_explicit(&watched_task,(unsigned)(uintptr_t)xTaskGetCurrentTaskHandle(),memory_order_relaxed);
    atomic_store_explicit(&enabled,1,memory_order_release);
}
void allocation_probe_end(void) { atomic_store_explicit(&enabled,0,memory_order_release); }
uint32_t allocation_probe_allocations(void) { return allocations; }
uint32_t allocation_probe_frees(void) { return frees; }
