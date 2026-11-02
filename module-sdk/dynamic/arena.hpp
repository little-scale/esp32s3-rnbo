/* SPDX-License-Identifier: MIT */
#pragma once
#include <cstddef>
#include <cstdint>
namespace rnbo_dynamic {
constexpr std::size_t alignment=16;
enum class AllocationKind { platform, cpp };
struct AllocationState {
    unsigned char *arena=nullptr;
    std::size_t capacity=0,used=0,high_water=0;
    std::uint64_t allocations=0,late=0,errors=0;
    std::uint64_t cpp_new=0,cpp_late=0,cpp_delete=0,total=0,total_late=0;
    bool running=false;
};
extern AllocationState *allocation;
extern std::uint32_t bootstrap_allocation_attempts;
extern std::uint64_t sample_clock;
[[noreturn]] void allocation_failure();
void *allocate(std::size_t,AllocationKind,std::size_t requested_alignment=alignment);
std::size_t allocated_size(void *);
void deallocate(void *,bool cpp);
}
