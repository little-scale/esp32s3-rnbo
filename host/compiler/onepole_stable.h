/* SPDX-License-Identifier: MIT */
#pragma once
#include <cfloat>
#include <cmath>
#include <limits>
#if defined(__FAST_MATH__) || (defined(__FINITE_MATH_ONLY__) && __FINITE_MATH_ONLY__ > 0)
#error "Stable onepole requires strict floating-point compilation"
#endif
#if FLT_RADIX != 2 || FLT_MANT_DIG != 24 || FLT_MAX_EXP != 128 || FLT_MIN_EXP != -125 || FLT_EVAL_METHOD != 0
#error "Stable onepole requires binary32 without extended evaluation"
#endif
static_assert(sizeof(float) == 4 && ::std::numeric_limits<float>::is_iec559,
              "Stable onepole requires IEEE binary32");

namespace rnbo_s3_onepole {
constexpr float minimum_coefficient = 0.00001f;
constexpr float maximum_coefficient = 0.99999f;

// Fixed 44.1 kHz profile. Pre-bounds also keep every finite frequency's
// exponential argument finite, without evaluating positive overflow branches.
inline float coefficient(float hz) noexcept {
    if (hz <= 0.0f) return minimum_coefficient;
    if (hz >= 100000.0f) return maximum_coefficient;
    const float value = -::expm1f(-0x1.2acb24p-13f * hz);
    return value > maximum_coefficient ? maximum_coefficient :
           value < minimum_coefficient ? minimum_coefficient : value;
}

// For finite x/y and 0 <= a <= maximum_coefficient, this remains finite.
// Same-sign endpoints use a difference with a >165u rounding margin; opposite
// endpoints use bounded products whose weakly opposite-sign sum cannot overflow.
// See the independent proof; fixed nearest-even rounding is an execution contract.
inline float finite_lerp(float x, float y, float a) noexcept {
    if ((x >= 0.0f) == (y >= 0.0f)) return y + a * (x - y);
    return a * x + (1.0f - a) * y;
}

// The state words must be independent ordinary floats. The compiler pass pins
// private ownership and actual types; inputs cannot alias these state words.
// Accuracy/rounding intentionally differ from the original RNBO recurrence.
inline float step(float x, float a, float& y, float& correction) noexcept {
    const float delta = x - y;
    if (delta > FLT_MAX || delta < -FLT_MAX) {
        y = finite_lerp(x, y, a);
        correction = 0.0f;
        return y;
    }
    const float increment = a * delta - correction;
    const float next = y + increment;
    const float debt = (next - y) - increment;
    // With finite old y, nonfinite next necessarily makes debt nonfinite too.
    // Test before storing next so the fallback still has the finite old state.
    if (!(debt <= FLT_MAX && debt >= -FLT_MAX)) {
        y = finite_lerp(x, y, a);
        correction = 0.0f;
        return y;
    }
    y = next;
    correction = debt;
    return y;
}
} // namespace rnbo_s3_onepole
