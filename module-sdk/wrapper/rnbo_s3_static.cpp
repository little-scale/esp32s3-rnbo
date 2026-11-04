/* SPDX-License-Identifier: MIT */
#include "rnbo_s3_module.h"
#include <cmath>
#include <cstddef>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <new>
#ifdef ESP_PLATFORM
#include "esp_heap_caps.h"
#endif
#include "patch_config.h"
#include "rnbo_s3_midi.h"
#ifndef RNBO_S3_PATCH_MIDI_INPUT_PORTS
#define RNBO_S3_PATCH_MIDI_INPUT_PORTS 0
#endif
#ifndef RNBO_S3_PATCH_DISCARD_MIDI_OUTPUT
#define RNBO_S3_PATCH_DISCARD_MIDI_OUTPUT 0
#endif
#define RNBO_USE_FLOAT32
#define RNBO_NOSTL
#define RNBO_NOTHROW
#define RNBO_NO_PATCHERFACTORY
#define RNBO_FIXEDLISTSIZE 16
#define RNBO_USECUSTOMALLOCATOR
#define RNBO_USECUSTOMPLATFORMPRINT
#include "RNBO_Common.h"

namespace {
struct AllocationState {
    unsigned char *arena = nullptr;
    size_t capacity = 0, used = 0;
    uint64_t allocations = 0, late = 0, errors = 0;
    bool running = false;
};
AllocationState *allocation = nullptr;
/* A native OOM cannot safely return NULL to unchecked generated accesses.
 * Abort is intentional; target recovery must use known-good firmware/module. */
[[noreturn]] void allocation_failure() { std::abort(); }
void *arena_allocate(size_t n) {
    if (!allocation) allocation_failure();
    constexpr size_t alignment = alignof(std::max_align_t);
    constexpr size_t header = alignment;
    static_assert(sizeof(size_t) <= header, "arena header must hold the allocation size");
    if (n > SIZE_MAX - header - (alignment - 1)) allocation_failure();
    size_t total = (n + header + alignment - 1) & ~(alignment - 1);
    if (total > allocation->capacity - allocation->used) allocation_failure();
    unsigned char *p = allocation->arena + allocation->used;
    std::memcpy(p, &n, sizeof n);
    allocation->used += total;
    ++allocation->allocations;
    if (allocation->running) ++allocation->late;
    return p + header;
}
}
namespace RNBO { namespace Platform {
void *malloc(size_t n) { return arena_allocate(n); }
void free(void *) {} // whole arena reclaimed only after patch destruction
void *calloc(size_t count, size_t n) {
    if (n && count > SIZE_MAX / n) allocation_failure();
    void *p = arena_allocate(count * n);
    std::memset(p, 0, count * n);
    return p;
}
void *realloc(void *p, size_t n) {
    if (!p) return arena_allocate(n);
    if (!n) return nullptr;
    if (!allocation) allocation_failure();
    constexpr size_t header = alignof(std::max_align_t);
    const uintptr_t base = reinterpret_cast<uintptr_t>(allocation->arena);
    const uintptr_t address = reinterpret_cast<uintptr_t>(p);
    if (address < base || address - base < header ||
        address - base > allocation->used || (address - base) % header)
        allocation_failure();
    size_t old;
    std::memcpy(&old, static_cast<unsigned char *>(p) - header, sizeof old);
    if (old > allocation->used - (address - base)) allocation_failure();
    if (n <= old) return p;
    void *q = arena_allocate(n);
    std::memcpy(q, p, old);
    return q;
}
static void printMessage(const char *) {}
static void printErrorMessage(const char *) { if (allocation) ++allocation->errors; }
} }
#ifndef RNBO_S3_PATCH_SOURCE
#define RNBO_S3_PATCH_SOURCE "rnbo_source.h"
#endif
#include RNBO_S3_PATCH_SOURCE
#undef trunc
#undef autoref

namespace {
using Patch = RNBO::RNBO_S3_PATCH_CLASS<>;
static_assert(sizeof(RNBO::SampleValue) == 4, "float32 audio required");
static_assert(sizeof(RNBO::MillisecondTime) == 8, "double scheduler required");
static_assert(RNBO_S3_PATCH_RATE == RNBO_S3_SAMPLE_RATE, "rate mismatch");
static_assert(RNBO_S3_PATCH_BLOCK == RNBO_S3_BLOCK_FRAMES, "vector mismatch");
static_assert(RNBO_S3_PATCH_ROLE == RNBO_S3_MAIN || RNBO_S3_PATCH_ROLE == RNBO_S3_FX, "role mismatch");
struct Context {
    AllocationState memory;
    alignas(Patch) unsigned char patch_storage[sizeof(Patch)];
    Patch *patch = nullptr;
    float scratch[2][RNBO_S3_BLOCK_FRAMES] = {};
    float silence[RNBO_S3_BLOCK_FRAMES] = {};
    RNBO::Logger *previous_logger = nullptr;
    uint32_t warmup = 0;
    uint64_t position = 0, blocks = 0, bad_samples = 0;
    bool prepared = false, ready = false, fault = false, muted = false;
};
Context *live = nullptr;
class SilentLogger final : public RNBO::Logger {
    void log(RNBO::LogLevel level, const char *) override {
        if (level == RNBO::Error && allocation) ++allocation->errors;
    }
} logger;
bool valid(void *p) { return p && p == live; }
bool failed(Context *c) {
    if (c->memory.errors || c->memory.late || c->bad_samples) c->fault = true;
    return c->fault;
}
void silence(float *const *outputs, uint32_t frames) {
    if (outputs && frames == RNBO_S3_BLOCK_FRAMES)
        for (unsigned ch = 0; ch < 2; ++ch)
            if (outputs[ch]) std::memset(outputs[ch], 0, frames * sizeof(float));
}
bool copy_string(char *out, size_t cap, const char *in) {
    if (!in) in = "";
    size_t n = 0;
    while (n < cap && in[n]) ++n;
    if (n >= cap) return false;
    std::memcpy(out, in, n + 1);
    return true;
}
bool parameter_metadata(Context *c, uint32_t i, rnbo_s3_parameter_info &result) {
    RNBO::ParameterInfo info{};
    c->patch->getParameterInfo(i, &info);
    if (info.type != RNBO::ParameterTypeNumber || !std::isfinite(info.min) ||
        !std::isfinite(info.max) || !std::isfinite(info.initialValue) ||
        !std::isfinite(info.exponent) || info.min >= info.max ||
        info.initialValue < info.min || info.initialValue > info.max ||
        info.exponent <= 0 || info.steps < 0)
        return false;
    result = {};
    result.struct_bytes = sizeof(result); result.index = i;
    result.minimum = info.min; result.maximum = info.max;
    result.initial = info.initialValue; result.exponent = info.exponent;
    result.steps = static_cast<uint32_t>(info.steps);
    return copy_string(result.id, sizeof(result.id), c->patch->getParameterId(i)) &&
        result.id[0] &&
        copy_string(result.name, sizeof(result.name), info.displayName && *info.displayName ?
                    info.displayName : c->patch->getParameterName(i)) && result.name[0] &&
        copy_string(result.unit, sizeof(result.unit), info.unit);
}
void destroy(void *p) {
    if (!valid(p)) return;
    Context *c = live;
    c->memory.running = false;
    if (c->patch) c->patch->~Patch();
    RNBO::console = c->previous_logger;
#ifdef ESP_PLATFORM
    heap_caps_free(c->memory.arena);
#else
    std::free(c->memory.arena);
#endif
    allocation = nullptr;
    live = nullptr;
    delete c;
}
int create(const rnbo_s3_create_options *options, void **out) {
    if (!out) return RNBO_S3_INVALID;
    *out = nullptr;
    if (!options || options->struct_bytes < sizeof(*options) ||
        options->arena_bytes < 4096 || options->arena_bytes > 4 * 1024 * 1024 ||
        options->warmup_blocks > 64) return RNBO_S3_INVALID;
    if (live) return RNBO_S3_BUSY;
    Context *c = new(std::nothrow) Context;
    if (!c) return RNBO_S3_NO_MEMORY;
#ifdef ESP_PLATFORM
    c->memory.arena = static_cast<unsigned char *>(heap_caps_aligned_alloc(alignof(std::max_align_t), options->arena_bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
#else
    c->memory.arena = static_cast<unsigned char *>(std::malloc(options->arena_bytes));
#endif
    if (!c->memory.arena) { delete c; return RNBO_S3_NO_MEMORY; }
    c->memory.capacity = options->arena_bytes;
    c->warmup = options->warmup_blocks;
    allocation = &c->memory;
    live = c;
    c->previous_logger = RNBO::console;
    RNBO::console = &logger;
    /* Expand all 32 seed bits without float conversion or time dependence. */
    uint64_t seed = options->seed;
    for (unsigned i = 0; i < 4; ++i)
        RNBO::s_globalRandom.state[i] = seed = RNBO::xoshiro_splitmix32(seed);
    c->patch = new(c->patch_storage) Patch;
    *out = c;
    return RNBO_S3_OK;
}
int prepare(void *p) {
    if (!valid(p)) return RNBO_S3_INVALID;
    Context *c = live;
    if (c->prepared || c->patch == nullptr || c->fault) return RNBO_S3_INVALID;
    c->prepared = true; // initialize() is a one-shot operation, including failure
    c->patch->initialize();
    c->patch->prepareToProcess(RNBO_S3_SAMPLE_RATE, RNBO_S3_BLOCK_FRAMES, true);
    unsigned expected_inputs = RNBO_S3_PATCH_ROLE == RNBO_S3_FX ? 2 : 0;
    const RNBO::PatcherInterface *interface = c->patch;
    if (c->patch->getNumInputChannels() != expected_inputs ||
        c->patch->getNumOutputChannels() != 2 ||
        c->patch->getNumParameters() > RNBO_S3_MAX_PARAMETERS ||
        c->patch->getNumSignalInParameters() || c->patch->getNumSignalOutParameters() ||
        c->patch->getNumMidiInputPorts() > 1 ||
        c->patch->getNumMidiOutputPorts() > (RNBO_S3_PATCH_DISCARD_MIDI_OUTPUT ? 1u : 0u) ||
        c->patch->getNumMessages() || !interface->hasFixedVectorSize() ||
        interface->getSampleRate() != RNBO_S3_SAMPLE_RATE ||
        interface->getMaxBlockSize() != RNBO_S3_BLOCK_FRAMES) {
        c->fault = true;
        return RNBO_S3_UNSUPPORTED;
    }
    /* Admit the actual generated schema before any audio ownership transfer.
     * Never allow an otherwise playable patch whose IDs cannot be copied. */
    for (uint32_t i = 0; i < c->patch->getNumParameters(); ++i) {
        rnbo_s3_parameter_info info{};
        if (!parameter_metadata(c, i, info)) {
            c->fault = true;
            return RNBO_S3_UNSUPPORTED;
        }
        for (uint32_t j = 0; j < i; ++j) {
            if (std::strcmp(info.id, c->patch->getParameterId(j)) == 0) {
                c->fault = true;
                return RNBO_S3_UNSUPPORTED;
            }
        }
    }
    const float *in[] = {c->silence, c->silence};
    float *out[] = {c->scratch[0], c->scratch[1]};
    for (uint32_t i = 0; i < c->warmup; ++i) {
        c->patch->process(expected_inputs ? in : nullptr, expected_inputs, out, 2, RNBO_S3_BLOCK_FRAMES);
        for (unsigned ch = 0; ch < 2; ++ch)
            for (float sample : c->scratch[ch]) if (!std::isfinite(sample)) ++c->bad_samples;
    }
    c->ready = !failed(c);
    c->memory.running = c->ready;
    return c->ready ? RNBO_S3_OK : RNBO_S3_FAULT;
}
int process(void *p, const float *const *in, float *const *out, uint32_t n, uint64_t position) {
    if (!valid(p) || !out || n != RNBO_S3_BLOCK_FRAMES || !out[0] || !out[1]) {
        silence(out, n);
        return RNBO_S3_INVALID;
    }
    Context *c = live;
    if (!c->ready || position != c->position || position > UINT64_MAX - n) {
        silence(out, n);
        return RNBO_S3_INVALID;
    }
    if (failed(c) || c->muted) {
        silence(out, n);
        return RNBO_S3_FAULT;
    }
    constexpr unsigned inputs = RNBO_S3_PATCH_ROLE == RNBO_S3_FX ? 2 : 0;
    if (inputs && (!in || !in[0] || !in[1])) { silence(out, n); return RNBO_S3_INVALID; }
    c->patch->process(in, inputs, out, 2, n);
    for (unsigned ch = 0; ch < 2; ++ch)
        for (unsigned i = 0; i < n; ++i) if (!std::isfinite(out[ch][i])) ++c->bad_samples;
    c->position += n;
    ++c->blocks;
    if (failed(c)) { silence(out, n); return RNBO_S3_FAULT; }
    return RNBO_S3_OK;
}
bool midi_valid(const rnbo_s3_event &e) {
    return rnbo_s3_midi_valid(e.midi,e.midi_length) &&
        (e.midi[0]<0xf0 || RNBO_S3_PATCH_MIDI_INPUT_PORTS>0);
}
int event(void *p, const rnbo_s3_event *e) {
    if (!valid(p) || !e || e->struct_bytes < sizeof(*e)) return RNBO_S3_INVALID;
    Context *c = live;
    if (!c->ready || failed(c) || c->muted) return RNBO_S3_FAULT;
    if (e->kind == RNBO_S3_MIDI) {
        if (!midi_valid(*e) || e->midi_port >= c->patch->getNumMidiInputPorts()) return RNBO_S3_INVALID;
        c->patch->processMidiEvent(RNBO::TimeNow, e->midi_port, e->midi, e->midi_length);
    } else {
        if (e->parameter_index >= c->patch->getNumParameters() || !std::isfinite(e->value)) return RNBO_S3_INVALID;
        RNBO::ParameterInfo info{};
        c->patch->getParameterInfo(e->parameter_index, &info);
        if (e->kind == RNBO_S3_PARAMETER_NORMALIZED) {
            if (e->value < 0 || e->value > 1) return RNBO_S3_INVALID;
            c->patch->setParameterValueNormalized(e->parameter_index, e->value, RNBO::TimeNow);
        } else if (e->kind == RNBO_S3_PARAMETER_ACTUAL) {
            if (e->value < info.min || e->value > info.max) return RNBO_S3_INVALID;
            c->patch->setParameterValue(e->parameter_index, e->value, RNBO::TimeNow);
        } else return RNBO_S3_UNSUPPORTED;
    }
    return failed(c) ? RNBO_S3_FAULT : RNBO_S3_OK;
}
int panic(void *p) {
    if (!valid(p)) return RNBO_S3_INVALID;
    live->muted = true; // immediate bounded latch; cleanup happens detached
    return RNBO_S3_OK;
}
uint32_t parameter_count(void *p) {
    return valid(p) && live->ready ? static_cast<uint32_t>(live->patch->getNumParameters()) : 0;
}
int parameter_info(void *p, uint32_t i, rnbo_s3_parameter_info *out) {
    if (!valid(p) || !out || out->struct_bytes < sizeof(*out) || i >= parameter_count(p)) return RNBO_S3_INVALID;
    rnbo_s3_parameter_info result{};
    if (!parameter_metadata(live, i, result)) return RNBO_S3_UNSUPPORTED;
    *out = result; return RNBO_S3_OK;
}
int parameter_value(void *p, uint32_t i, float *actual, float *normalized) {
    if (!valid(p) || i >= parameter_count(p) || !actual || !normalized) return RNBO_S3_INVALID;
    *actual = live->patch->getParameterValue(i);
    *normalized = live->patch->convertToNormalizedParameterValue(i, *actual);
    return std::isfinite(*actual) && std::isfinite(*normalized) ? RNBO_S3_OK : RNBO_S3_FAULT;
}
int parameter_convert(void *p, uint32_t i, float value, uint32_t to_actual, float *out) {
    if (!valid(p) || i >= parameter_count(p) || !out || !std::isfinite(value) || to_actual > 1) return RNBO_S3_INVALID;
    if (to_actual && (value < 0 || value > 1)) return RNBO_S3_INVALID;
    RNBO::ParameterInfo info{}; live->patch->getParameterInfo(i, &info);
    if (!to_actual && (value < info.min || value > info.max)) return RNBO_S3_INVALID;
    *out = to_actual ? live->patch->convertFromNormalizedParameterValue(i, value) : live->patch->convertToNormalizedParameterValue(i, value);
    return std::isfinite(*out) ? RNBO_S3_OK : RNBO_S3_FAULT;
}
int statistics(void *p, rnbo_s3_stats *out) {
    if (!valid(p) || !out || out->struct_bytes < sizeof(*out)) return RNBO_S3_INVALID;
    Context *c = live;
    *out = {sizeof(*out), static_cast<uint32_t>(c->memory.capacity), static_cast<uint32_t>(c->memory.used),
            c->memory.allocations, c->memory.late, c->memory.errors, c->bad_samples, c->blocks,
            c->position, c->warmup, static_cast<uint32_t>(failed(c))};
    return RNBO_S3_OK;
}
const rnbo_s3_module module = {
    sizeof(rnbo_s3_module), RNBO_S3_ABI_MAJOR, RNBO_S3_ABI_MINOR, sizeof(void *) * 8,
    RNBO_S3_SAMPLE_RATE, RNBO_S3_BLOCK_FRAMES, RNBO_S3_PATCH_ROLE,
    RNBO_S3_PATCH_ROLE == RNBO_S3_FX ? 2u : 0u, 2,
    RNBO_S3_MAX_PARAMETERS, RNBO_S3_SINGLE_INSTANCE | RNBO_S3_BOUNDARY_EVENTS | RNBO_S3_PLATFORM_ALLOCATIONS_ONLY |
        (RNBO_S3_PATCH_DISCARD_MIDI_OUTPUT ? RNBO_S3_DISCARDS_MIDI_OUTPUT : 0u) |
        (RNBO_S3_PATCH_MIDI_INPUT_PORTS ? RNBO_S3_SHORT_MIDI_INPUT : 0u),
    create, prepare, process, event, panic, parameter_count, parameter_info, parameter_value,
    parameter_convert, statistics, destroy
};
}
extern "C" const rnbo_s3_module *rnbo_s3_static_module(void) { return &module; }
