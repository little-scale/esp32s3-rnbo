/* SPDX-License-Identifier: MIT */
#include "integer_abs.hpp"
#include <cstdint>
#include <cstdio>
#include <initializer_list>

static std::uint64_t checked = 0;
static bool check(int value) {
    const std::int64_t wide = value;
    const std::int64_t mathematical = wide < 0 ? -wide : wide;
    const int expected = mathematical > INT_MAX ? INT_MIN : static_cast<int>(mathematical);
    const int actual = rnbo_dynamic::integer_abs32(value);
    ++checked;
    if (actual != expected) {
        std::fprintf(stderr, "integer abs mismatch input=%d actual=%d expected=%d\n", value, actual, expected);
        return false;
    }
    return true;
}
int main() {
    for (int value = -32768; value <= 32767; ++value) if (!check(value)) return 1;
    for (int value : {INT_MIN, INT_MIN + 1, INT_MIN + 2, -1, 0, 1, INT_MAX - 1, INT_MAX})
        if (!check(value)) return 1;
    for (unsigned bit = 1; bit < 31; ++bit) {
        const int power = static_cast<int>(std::uint32_t{1} << bit);
        for (int value : {power - 1, power, power + 1, -power - 1, -power, -power + 1})
            if (!check(value)) return 1;
    }
    std::uint32_t state = 0x524e424fu;
    for (unsigned i = 0; i < 65536; ++i) {
        state = state * 1664525u + 1013904223u;
        const int value = state <= static_cast<std::uint32_t>(INT_MAX) ? static_cast<int>(state) :
                          -1 - static_cast<int>(UINT32_MAX - state);
        if (!check(value)) return 1;
    }
    std::printf("{\"checked_inputs\":%llu,\"signed_min_extension\":%d}\n",
                static_cast<unsigned long long>(checked), rnbo_dynamic::integer_abs32(INT_MIN));
}
