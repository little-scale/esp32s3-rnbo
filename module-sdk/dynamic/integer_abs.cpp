/* SPDX-License-Identifier: MIT */
/* Keep this private libc entry in a separate translation unit. Adding a new
 * function to support.cpp changes GCC layout choices in unrelated routines. */
#include "integer_abs.hpp"

extern "C" __attribute__((visibility("hidden"))) int abs(int value) noexcept {
    return rnbo_dynamic::integer_abs32(value);
}
