/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Half-open range check without pointer+length overflow. A zero-size request
 * is never sufficient to admit a descriptor, function target or array. */
static inline bool rnbo_test_range(uintptr_t start,size_t size,uintptr_t pointer,size_t bytes)
{
    return start && bytes && pointer>=start && pointer-start<size && bytes<=size-(pointer-start);
}
