/* SPDX-License-Identifier: MIT */
#pragma once
#include <cstdint>
namespace rnbo_dynamic {
extern std::uint32_t constructor_runs;
extern volatile std::uint32_t *finalizer_observer;
std::uint32_t registered_finalizers();
}
