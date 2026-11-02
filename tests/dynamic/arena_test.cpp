/* SPDX-License-Identifier: MIT */
/* Host-only allocator probe. The replacement new/delete operators live in
 * this disposable executable, never in the firmware's global C++ namespace. */
#include "arena.hpp"
#include <cassert>
#include <cstdint>
#include <cstring>
#include <new>

alignas(4096) static unsigned char storage[16384];

int main(int argc, char **argv) {
    rnbo_dynamic::AllocationState state;
    // Intentionally 16-byte aligned while NOT aligned to 32,64,...4096.
    state.arena = storage + 16;
    state.capacity = sizeof(storage) - 16;
    rnbo_dynamic::allocation = &state;
    if (argc == 2) {
        if (!std::strcmp(argv[1], "bootstrap")) {
            rnbo_dynamic::allocation = nullptr;
            (void)rnbo_dynamic::allocate(1, rnbo_dynamic::AllocationKind::cpp);
        } else if (!std::strcmp(argv[1], "exhaustion")) {
            (void)rnbo_dynamic::allocate(state.capacity, rnbo_dynamic::AllocationKind::cpp);
        } else if (!std::strcmp(argv[1], "invalid-alignment")) {
            (void)rnbo_dynamic::allocate(16, rnbo_dynamic::AllocationKind::cpp, 48);
        } else if (!std::strcmp(argv[1], "foreign-pointer")) {
            rnbo_dynamic::deallocate(storage, true);
        } else return 2;
        return 3; // all invalid paths must trap before returning
    }
    constexpr std::size_t alignments[] = {16u, 32u, 64u, 256u, 4096u};
    for (std::size_t alignment : alignments) {
        void *pointer = rnbo_dynamic::allocate(33, rnbo_dynamic::AllocationKind::cpp, alignment);
        assert(reinterpret_cast<std::uintptr_t>(pointer) % alignment == 0);
        assert(rnbo_dynamic::allocated_size(pointer) == 33);
        std::memset(pointer, 0xa5, 33);
        rnbo_dynamic::deallocate(pointer, true);
    }
    auto before_platform = state.allocations;
    auto before_cpp = state.cpp_new;
    auto before_late = state.total_late;
    state.running = true;
    void *platform = rnbo_dynamic::allocate(7, rnbo_dynamic::AllocationKind::platform);
    void *cpp = ::operator new(19, std::align_val_t(64));
    assert(reinterpret_cast<std::uintptr_t>(cpp) % 64 == 0);
    assert(state.allocations == before_platform + 1 && state.cpp_new == before_cpp + 1);
    assert(state.late == 1 && state.cpp_late == 1 && state.total_late == before_late + 2);
    assert(state.high_water == state.used && state.used <= state.capacity);
    ::operator delete(cpp, std::align_val_t(64));
    rnbo_dynamic::deallocate(platform, false);
    rnbo_dynamic::allocation = nullptr;
}
