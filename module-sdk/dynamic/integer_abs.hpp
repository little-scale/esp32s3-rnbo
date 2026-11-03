/* SPDX-License-Identifier: MIT */
#pragma once
#include <climits>
#include <cstdint>

namespace rnbo_dynamic {
// Private 32-bit libc support. INT_MIN has no representable positive int
// magnitude; our explicit extension returns INT_MIN, without signed overflow.
// This does not claim that C abs(INT_MIN) has a defined standard result.
inline int integer_abs32(int value) noexcept {
    static_assert(CHAR_BIT == 8 && sizeof(int) == 4 && INT_MAX == 2147483647 &&
                  INT_MIN == (-2147483647 - 1), "Private abs requires signed 32-bit int");
    if (value >= 0) return value;
    const std::uint32_t magnitude = std::uint32_t{0} - static_cast<std::uint32_t>(value);
    if (magnitude > static_cast<std::uint32_t>(INT_MAX)) return INT_MIN;
    return static_cast<int>(magnitude); // Proven representable before conversion.
}
}
