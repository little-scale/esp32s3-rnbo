/* SPDX-License-Identifier: MIT */
/* Original graceful shell admission, derived from the qualified RNBO loader
 * lifecycle/range policy. This does not make native code safe or authenticated.
 * SDK arena exhaustion inside generated code can trap: an admitted package must
 * specify a sufficient arena budget, not merely the structural descriptor min.
 */
#include "player_loader.h"
#include "private/elf_validate.h"
#include "esp_heap_caps.h"
#include "esp_memory_utils.h"
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

_Static_assert(sizeof(void *) == 4 && sizeof(void (*)(void)) == 4, "Xtensa32 ABI required");

static esp_err_t errorf(char *error, size_t bytes, esp_err_t result, const char *format, ...)
{
    if (error && bytes) {
        va_list args;
        va_start(args, format);
        vsnprintf(error, bytes, format, args);
        va_end(args);
    }
    return result;
}

/* Half-open, subtraction-based bounds. Empty spans cannot admit any pointer. */
static bool range(uintptr_t start, size_t size, uintptr_t pointer, size_t bytes)
{
    return start && bytes && pointer >= start && pointer - start < size &&
           bytes <= size - (pointer - start);
}

static bool executable(const esp_elf_t *elf, uintptr_t pointer)
{
    return range(esp_elf_runtime_base((esp_elf_t *)elf), elf->sec[ELF_SEC_TEXT].size, pointer, 1);
}

static bool data_span(const esp_elf_t *elf, const void *pointer, size_t bytes)
{
    const unsigned allowed[] = {ELF_SEC_DATA, ELF_SEC_BSS, ELF_SEC_RODATA, ELF_SEC_DRLRO};
    for (unsigned i = 0; i < sizeof allowed / sizeof *allowed; ++i) {
        const esp_elf_sec_t *section = &elf->sec[allowed[i]];
        if (range(section->addr, section->size, (uintptr_t)pointer, bytes)) return true;
    }
    return false;
}

static bool lifecycle_array(const esp_elf_t *elf, void (**array)(void), uint32_t count, unsigned section)
{
    if (!count) return true;
    if (count > UINT32_MAX / sizeof *array ||
        !range(elf->sec[section].addr, elf->sec[section].size, (uintptr_t)array, count * sizeof *array)) return false;
    for (uint32_t i = 0; i < count; ++i) {
        uintptr_t target = (uintptr_t)array[i];
        if (target && target != UINT32_MAX && !executable(elf, target)) return false;
    }
    return true;
}

/* The pinned loader validator checks all ELF offsets, table extents and symbol
 * string bounds first. Reject every named undefined symbol, including weak
 * imports: the player supplies no host symbol service to these modules.
 */
static bool import_free(const uint8_t *payload)
{
    elf32_hdr_t header;
    memcpy(&header, payload, sizeof header);
    bool symbol_table = false;
    for (uint32_t i = 0; i < header.shnum; ++i) {
        elf32_shdr_t section, strings;
        memcpy(&section, payload + header.shoff + i * sizeof section, sizeof section);
        if (section.type != SHT_SYMTAB && section.type != SHT_SYNSYM) continue;
        symbol_table = true;
        memcpy(&strings, payload + header.shoff + section.link * sizeof strings, sizeof strings);
        for (uint32_t j = 0; j < section.size / sizeof(elf32_sym_t); ++j) {
            elf32_sym_t symbol;
            memcpy(&symbol, payload + section.offset + j * sizeof symbol, sizeof symbol);
            if (symbol.shndx == SHN_UNDEF && payload[strings.offset + symbol.name] != 0) return false;
        }
    }
    return symbol_table;
}

static bool admit_table(player_image *a, uint32_t role)
{
    const rnbo_s3_module *m = &a->module;
    const rnbo_s3_dynamic_info *d = &a->info;
    const uint32_t dynamic_flags = RNBO_S3_DYNAMIC_CALLER_STATE |
        RNBO_S3_DYNAMIC_PRIVATE_CPP_ALLOCATOR | RNBO_S3_DYNAMIC_DETERMINISTIC_SAMPLE_CLOCK;
    if (d->struct_bytes != sizeof *d || d->abi_major != RNBO_S3_DYNAMIC_ABI_MAJOR ||
        d->abi_minor > RNBO_S3_DYNAMIC_ABI_MINOR || d->pointer_bits != 32 ||
        d->flags != dynamic_flags || d->constructor_runs != 1 || !d->registered_finalizers ||
        d->registered_finalizers > 32 || d->state_alignment < 16 || d->state_alignment > 64 ||
        (d->state_alignment & (d->state_alignment - 1)) ||
        !d->context_bytes || d->context_bytes > 1024u * 1024u ||
        d->minimum_arena_bytes < 4096 || d->minimum_arena_bytes > a->arena_bytes ||
        d->maximum_arena_bytes < a->arena_bytes || d->maximum_arena_bytes > PLAYER_MAX_ARENA_BYTES ||
        d->minimum_state_bytes < d->context_bytes || d->maximum_state_bytes > 5u * 1024u * 1024u ||
        d->minimum_state_bytes > d->maximum_state_bytes || d->maximum_state_bytes < d->context_bytes ||
        d->minimum_state_bytes - d->context_bytes < d->minimum_arena_bytes ||
        d->maximum_state_bytes - d->context_bytes < d->maximum_arena_bytes ||
        !data_span(&a->elf, d->descriptor_address, sizeof(uint32_t))) return false;
    uint32_t descriptor_bytes;
    memcpy(&descriptor_bytes, d->descriptor_address, sizeof descriptor_bytes);
    if (descriptor_bytes < sizeof *m || !data_span(&a->elf, d->descriptor_address, descriptor_bytes) ||
        memcmp(m, d->descriptor_address, sizeof *m) || m->struct_bytes < sizeof *m ||
        m->abi_major != RNBO_S3_ABI_MAJOR || m->abi_minor > RNBO_S3_ABI_MINOR || m->pointer_bits != 32 ||
        m->sample_rate != RNBO_S3_SAMPLE_RATE || m->block_frames != RNBO_S3_BLOCK_FRAMES ||
        m->role != role || m->audio_outputs != 2 || m->audio_inputs != (role == RNBO_S3_FX ? 2u : 0u) ||
        m->max_parameters > RNBO_S3_MAX_PARAMETERS) return false;
    const uint32_t allowed_flags = RNBO_S3_SINGLE_INSTANCE | RNBO_S3_BOUNDARY_EVENTS |
        RNBO_S3_PLATFORM_ALLOCATIONS_ONLY | RNBO_S3_DISCARDS_MIDI_OUTPUT | RNBO_S3_SHORT_MIDI_INPUT;
    if ((m->flags & ~allowed_flags) || !(m->flags & RNBO_S3_SINGLE_INSTANCE) ||
        !(m->flags & RNBO_S3_BOUNDARY_EVENTS)) return false;
#define CALLBACK(name) if (!executable(&a->elf, (uintptr_t)m->name)) return false
    CALLBACK(create); CALLBACK(prepare); CALLBACK(process); CALLBACK(event); CALLBACK(panic);
    CALLBACK(parameter_count); CALLBACK(parameter_info); CALLBACK(parameter_value);
    CALLBACK(parameter_convert); CALLBACK(statistics); CALLBACK(destroy);
#undef CALLBACK
    return executable(&a->elf, (uintptr_t)d->statistics);
}

static int request(player_image *a, unsigned operation, void *state, uint32_t bytes)
{
    a->module = (rnbo_s3_module){.struct_bytes = sizeof a->module};
    a->info = (rnbo_s3_dynamic_info){.struct_bytes = sizeof a->info};
    rnbo_s3_dynamic_request command = {.struct_bytes = sizeof command, .magic = RNBO_S3_DYNAMIC_MAGIC,
        .abi_major = RNBO_S3_DYNAMIC_ABI_MAJOR, .abi_minor = RNBO_S3_DYNAMIC_ABI_MINOR,
        .operation = operation, .state = state, .state_bytes = bytes,
        .out_module = &a->module, .out_info = &a->info, .finalizer_observer = &a->finalized,
        .result = RNBO_S3_DYNAMIC_RESULT_PENDING};
    char *arguments[] = {(char *)&command};
    int result = esp_elf_request(&a->elf, 0, 1, arguments);
    return result ? result : command.result; /* Loader discards the entry's return. */
}

void player_image_unload(player_image *a)
{
    if (!a) return;
    if (a->context && a->callbacks_admitted && a->module.destroy) a->module.destroy(a->context);
    a->context = NULL;
    if (a->initialized) esp_elf_deinit(&a->elf);
    heap_caps_free(a->state);
    memset(a, 0, sizeof *a);
}

esp_err_t player_image_statistics(player_image *a, char *error, size_t error_bytes)
{
    if (error && error_bytes) error[0] = 0;
    if (!a || !a->loaded || !a->callbacks_admitted || !a->context || a->finalized)
        return errorf(error, error_bytes, ESP_ERR_INVALID_STATE, "image is not prepared");
    a->stats = (rnbo_s3_stats){.struct_bytes = sizeof a->stats};
    a->dynamic_stats = (rnbo_s3_dynamic_stats){.struct_bytes = sizeof a->dynamic_stats};
    if (a->module.statistics(a->context, &a->stats) != RNBO_S3_OK ||
        a->info.statistics(a->context, &a->dynamic_stats) != RNBO_S3_OK)
        return errorf(error, error_bytes, ESP_FAIL, "module statistics failed");
    const rnbo_s3_stats *s = &a->stats;
    const rnbo_s3_dynamic_stats *d = &a->dynamic_stats;
    if (s->struct_bytes != sizeof *s || d->struct_bytes != sizeof *d || s->errors || s->invalid_samples ||
        s->late_platform_allocations || s->faulted || s->warmup_blocks != 4 || s->sample_position != a->position ||
        s->arena_capacity != a->arena_bytes || s->arena_used > s->arena_capacity ||
        d->late_cpp_new_calls || d->total_late_allocations || d->bootstrap_allocation_attempts ||
        d->arena_used > d->arena_capacity || d->arena_high_water > d->arena_capacity ||
        d->arena_capacity != a->arena_bytes)
        return errorf(error, error_bytes, ESP_FAIL, "module resource, position or sample health failed");
    return ESP_OK;
}

static bool schema_valid(player_image *a)
{
    a->parameter_count = a->module.parameter_count(a->context);
    if (a->parameter_count > PLAYER_MAX_PARAMETERS || a->parameter_count > a->module.max_parameters) return false;
    for (uint32_t i = 0; i < a->parameter_count; ++i) {
        rnbo_s3_parameter_info p = {.struct_bytes = sizeof p};
        float actual, normalized;
        if (a->module.parameter_info(a->context, i, &p) != RNBO_S3_OK ||
            p.struct_bytes != sizeof p || p.index != i || !memchr(p.id, 0, sizeof p.id) || !p.id[0] ||
            !memchr(p.name, 0, sizeof p.name) || !p.name[0] || !memchr(p.unit, 0, sizeof p.unit) ||
            !isfinite(p.minimum) || !isfinite(p.maximum) || p.minimum > p.maximum ||
            !isfinite(p.initial) || p.initial < p.minimum || p.initial > p.maximum ||
            !isfinite(p.exponent) || p.exponent <= 0 ||
            a->module.parameter_value(a->context, i, &actual, &normalized) != RNBO_S3_OK ||
            !isfinite(actual) || !isfinite(normalized) || normalized < 0 || normalized > 1) return false;
        for (uint32_t j = 0; j < i; ++j) {
            rnbo_s3_parameter_info previous = {.struct_bytes = sizeof previous};
            if (a->module.parameter_info(a->context, j, &previous) != RNBO_S3_OK ||
                !memchr(previous.id, 0, sizeof previous.id) || !strcmp(p.id, previous.id)) return false;
        }
    }
    return true;
}

esp_err_t player_image_load(player_image *a, const uint8_t *payload, size_t bytes,
                            uint32_t role, uint32_t arena_bytes, char *error, size_t error_bytes)
{
    if (error && error_bytes) error[0] = 0;
    if (!a || !payload || bytes < sizeof(elf32_hdr_t) || bytes > PLAYER_MAX_ELF_BYTES ||
        role != RNBO_S3_MAIN || arena_bytes < 4096 || arena_bytes > PLAYER_MAX_ARENA_BYTES)
        return errorf(error, error_bytes, ESP_ERR_INVALID_ARG, "invalid image, role or arena size");
    if (a->initialized || a->loaded || a->context || a->state)
        return errorf(error, error_bytes, ESP_ERR_INVALID_STATE, "unload the existing image first");
    memset(a, 0, sizeof *a);
    a->arena_bytes = arena_bytes;
    esp_err_t result = ESP_FAIL;
    uint8_t *copy = NULL;
    const uint8_t *aligned = payload;
    if ((uintptr_t)payload & 3u) {
        copy = heap_caps_aligned_alloc(16, bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
        if (!copy) { result = errorf(error, error_bytes, ESP_ERR_NO_MEM, "no memory for aligned ELF input"); goto failed; }
        memcpy(copy, payload, bytes);
        aligned = copy;
    }
#define ADMIT(condition, code, message) do { if (!(condition)) { result = errorf(error, error_bytes, code, message); goto failed; } } while (0)
    ADMIT(esp_elf_validate(aligned, bytes) == 0, ESP_ERR_INVALID_ARG, "malformed or unsupported Xtensa ELF");
    ADMIT(import_free(aligned), ESP_ERR_NOT_SUPPORTED, "module must contain a symbol table and zero undefined imports");
    ADMIT(esp_elf_init(&a->elf) == 0, ESP_FAIL, "ELF loader initialization failed");
    a->initialized = true;
    ADMIT(esp_elf_relocate(&a->elf, aligned, bytes) == 0, ESP_FAIL, "ELF relocation or executable allocation failed");
    a->loaded = true;
    ADMIT(executable(&a->elf, (uintptr_t)a->elf.entry) && esp_ptr_external_ram(a->elf.ptext),
          ESP_ERR_INVALID_ARG, "ELF entry or PSRAM executable mapping is invalid");
    ADMIT(!a->elf.init_done && a->elf.init_count && a->elf.fini_count &&
          lifecycle_array(&a->elf, a->elf.preinit_array, a->elf.preinit_count, ELF_SEC_PREINIT) &&
          lifecycle_array(&a->elf, a->elf.init_array, a->elf.init_count, ELF_SEC_INIT) &&
          lifecycle_array(&a->elf, a->elf.fini_array, a->elf.fini_count, ELF_SEC_FINI),
          ESP_ERR_INVALID_ARG, "invalid module constructor or finalizer arrays");
    ADMIT(request(a, RNBO_S3_DYNAMIC_DESCRIBE, NULL, 0) == RNBO_S3_OK && a->elf.init_done && admit_table(a, role),
          ESP_ERR_NOT_SUPPORTED, "module ABI, role, descriptor or callbacks failed admission");
    rnbo_s3_module first_module = a->module;
    rnbo_s3_dynamic_info first_info = a->info;
    ADMIT(request(a, RNBO_S3_DYNAMIC_DESCRIBE, NULL, 0) == RNBO_S3_OK && admit_table(a, role) &&
          !memcmp(&first_module, &a->module, sizeof first_module) && !memcmp(&first_info, &a->info, sizeof first_info),
          ESP_ERR_NOT_SUPPORTED, "module descriptor changed across repeated describe");
    ADMIT(a->info.context_bytes <= UINT32_MAX - arena_bytes, ESP_ERR_INVALID_SIZE, "context plus arena overflow");
    a->state_bytes = a->info.context_bytes + arena_bytes;
    ADMIT(a->state_bytes >= a->info.minimum_state_bytes && a->state_bytes <= a->info.maximum_state_bytes,
          ESP_ERR_INVALID_SIZE, "requested state does not fit module bounds");
    a->state = heap_caps_aligned_alloc(a->info.state_alignment, a->state_bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    ADMIT(a->state && esp_ptr_external_ram(a->state), ESP_ERR_NO_MEM, "not enough PSRAM for module context and arena");
    ADMIT(request(a, RNBO_S3_DYNAMIC_BIND, a->state, a->state_bytes) == RNBO_S3_OK && admit_table(a, role) &&
          !memcmp(&first_module, &a->module, sizeof first_module) && !memcmp(&first_info, &a->info, sizeof first_info),
          ESP_ERR_NOT_SUPPORTED, "module bind or immutable descriptor failed");
    a->callbacks_admitted = true;
    rnbo_s3_create_options options = {.struct_bytes = sizeof options, .arena_bytes = arena_bytes,
                                     .warmup_blocks = 4, .seed = 0x12345678};
    void *context = NULL;
    int created = a->module.create(&options, &context);
    bool context_valid = range((uintptr_t)a->state, a->state_bytes, (uintptr_t)context, a->info.context_bytes);
    if (context_valid) a->context = context; /* destroy a partial valid context on any later failure */
    ADMIT(created == RNBO_S3_OK && context_valid, created == RNBO_S3_NO_MEMORY ? ESP_ERR_NO_MEM : ESP_FAIL,
          "module create failed or returned a context outside caller state");
    ADMIT(a->module.prepare(a->context) == RNBO_S3_OK, ESP_FAIL, "module preparation failed");
    ADMIT(schema_valid(a), ESP_ERR_NOT_SUPPORTED, "module parameter schema/readbacks exceed the supported profile");
    ADMIT(player_image_statistics(a, error, error_bytes) == ESP_OK, ESP_FAIL, "module initial health or resource check failed");
    a->executable_base = esp_elf_runtime_base(&a->elf);
    a->text_bytes = a->elf.sec[ELF_SEC_TEXT].size;
    uint64_t data_bytes = 0;
    for (unsigned i = ELF_SEC_BSS; i < ELF_SECS; ++i) if (i != ELF_SEC_GOT_LOC) data_bytes += a->elf.sec[i].size;
    ADMIT(data_bytes <= UINT32_MAX, ESP_ERR_INVALID_SIZE, "mapped data size overflow");
    a->data_bytes = (uint32_t)data_bytes;
    heap_caps_free(copy);
    return ESP_OK;
failed:
    heap_caps_free(copy);
    player_image_unload(a);
    return result;
#undef ADMIT
}
