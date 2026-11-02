/* SPDX-License-Identifier: MIT */
#pragma once
#include "rnbo_s3_dynamic.h"
#include "esp_elf.h"
#include <stdbool.h>
typedef struct {
    esp_elf_t elf;
    rnbo_s3_module module;
    rnbo_s3_dynamic_info info;
    void *state,*context;
    uint32_t state_bytes,arena_bytes;
    volatile uint32_t finalized;
    uint64_t position;
    bool loaded;
} object_image;
void object_image_load(object_image *,const uint8_t *payload,size_t bytes,uint32_t role,uint32_t arena_bytes);
void object_image_prepare(object_image *,uint32_t warmup,uint32_t seed);
void object_image_statistics(object_image *,rnbo_s3_stats *,rnbo_s3_dynamic_stats *);
void object_image_destroy_context(object_image *);
void object_image_unload(object_image *);
