/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>
void allocation_probe_begin(void);
void allocation_probe_end(void);
uint32_t allocation_probe_allocations(void);
uint32_t allocation_probe_frees(void);
