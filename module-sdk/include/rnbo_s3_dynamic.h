/* SPDX-License-Identifier: MIT */
#ifndef RNBO_S3_DYNAMIC_H
#define RNBO_S3_DYNAMIC_H
#include "rnbo_s3_module.h"
#ifdef __cplusplus
extern "C" {
#endif
#define RNBO_S3_DYNAMIC_MAGIC 0x524e4431u /* RND1 */
#define RNBO_S3_DYNAMIC_ABI_MAJOR 1u
#define RNBO_S3_DYNAMIC_ABI_MINOR 0u
#define RNBO_S3_DYNAMIC_RESULT_PENDING (-2147483647)
enum { RNBO_S3_DYNAMIC_DESCRIBE=1, RNBO_S3_DYNAMIC_BIND=2 };
enum { RNBO_S3_DYNAMIC_CALLER_STATE=1u, RNBO_S3_DYNAMIC_PRIVATE_CPP_ALLOCATOR=2u,
       RNBO_S3_DYNAMIC_DETERMINISTIC_SAMPLE_CLOCK=4u };

typedef struct {
    uint32_t struct_bytes, arena_capacity, arena_used, arena_high_water;
    uint64_t cpp_new_calls, late_cpp_new_calls, cpp_delete_calls;
    uint64_t total_arena_allocations, total_late_allocations;
    uint32_t bootstrap_allocation_attempts;
} rnbo_s3_dynamic_stats;

typedef struct {
    uint32_t struct_bytes, abi_major, abi_minor, pointer_bits;
    uint32_t state_alignment, context_bytes, minimum_arena_bytes, maximum_arena_bytes;
    uint32_t minimum_state_bytes, maximum_state_bytes, flags;
    uint32_t constructor_runs, registered_finalizers;
    /* Source descriptor address is returned for loader section/range auditing
     * before the shell accepts the copied table. Every function pointer below
     * and in that table must lie inside the loaded image's TEXT section. */
    const rnbo_s3_module *descriptor_address;
    int (*statistics)(void *context, rnbo_s3_dynamic_stats *out);
} rnbo_s3_dynamic_info;

typedef struct {
    uint32_t struct_bytes, magic, abi_major, abi_minor, operation;
    void *state; /* BIND: shell-owned aligned context + arena region in PSRAM */
    uint32_t state_bytes;
    rnbo_s3_module *out_module; /* shell-owned; initialize struct_bytes */
    rnbo_s3_dynamic_info *out_info; /* shell-owned; initialize struct_bytes */
    volatile uint32_t *finalizer_observer; /* optional; remains valid through ELF unload */
    int32_t result; /* host sets PENDING; esp_elf_request ignores entry's C result */
} rnbo_s3_dynamic_request;

/* Entry: project_elf app_main, argc=1 and argv[0]=(char *)&request.
 * DESCRIBE allocates nothing and requires state=NULL/state_bytes=0. Constructors
 * must already have run exactly once without requesting the arena.
 * BIND reserves caller storage, without constructing a patch. create then uses
 * options.arena_bytes within that region, followed by prepare and owner calls.
 * minimum_arena_bytes is structural admission, not a measured patch budget.
 * Use a measured sufficient budget for real preparation. Module caps default to
 * 1 MiB; an explicit per-module build option permits up to 4 MiB. This does not
 * shorten delays or change buffer precision. Host whole-system admission still
 * has to reserve sufficient state and executable memory before BIND/create.
 * One live context/image; after destroy the same binding may reconstruct.
 * Rebinding while live is rejected. Destroy before esp_elf_deinit, and release
 * caller state only after module finalizers/unmapping complete. All pointers to
 * loaded code expire at unload. The shell must validate lifecycle entry targets
 * before executing the ELF and validate the returned table/callback ranges.
 * Seed is supplied at create. clock()/systemticks are private deterministic
 * microsecond ticks derived from processed sample frames; no wall clock import.
 * Base platform allocation counters keep their RNBO-hook-only meaning; use the
 * extension statistics to observe module-local C++ and total arena requests.
 */
#ifdef __cplusplus
}
#endif
#endif
