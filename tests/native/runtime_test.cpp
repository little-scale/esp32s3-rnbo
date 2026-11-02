/* SPDX-License-Identifier: MIT */
/* Exercise the prepared RNBO runtime primitives directly, independently of
 * the module allocator and wrapper. This is host evidence, not target timing. */
#include <cassert>
#include <cstddef>
#include <cstdio>
#include <utility>
#define RNBO_USE_FLOAT32
#define RNBO_NOSTL
#define RNBO_NOTHROW
#define RNBO_NO_PATCHERFACTORY
#define RNBO_FIXEDLISTSIZE 16
#include "patch_config.h"
#include "RNBO_Common.h"
#include "rnbo_source.h"
#undef trunc
#undef autoref

static float expected(std::size_t i) { return static_cast<float>(i * 7 + 3); }

template<std::size_t Fixed>
static void check(const RNBO::listbase<float, Fixed> &list, std::size_t count) {
    assert(static_cast<std::size_t>(list.length) == count);
    for (std::size_t i = 0; i < count; ++i) assert(list[i] == expected(i));
}

template<std::size_t Destination, std::size_t Source>
static void copy_assign_case(std::size_t count) {
    RNBO::listbase<float, Source> source;
    for (std::size_t i = 0; i < count; ++i) source.push(expected(i));
    RNBO::listbase<float, Destination> copied(source);
    check(copied, count);
    RNBO::listbase<float, Destination> assigned;
    /* Both growth and replacement of an existing overflow allocation matter. */
    assigned.push(-1);
    assigned = source;
    check(assigned, count);
    for (unsigned i = 0; i < 40; ++i) assigned.push(-2);
    assigned = source;
    check(assigned, count);
    check(source, count);
    if (count) {
        copied[0] = -9;
        assert(source[0] == expected(0)); // copies own independent storage
    }
}

template<std::size_t Fixed>
static void move_case(std::size_t count) {
    RNBO::listbase<float, Fixed> source;
    for (std::size_t i = 0; i < count; ++i) source.push(expected(i));
    RNBO::listbase<float, Fixed> moved(std::move(source));
    check(moved, count);
    assert(static_cast<std::size_t>(source.length) == 0);
    /* Reuse across the inline/overflow boundary detects an invalid moved-from
     * capacity, stale length, lost inline values and double-owned overflow. */
    for (unsigned i = 0; i < 40; ++i) source.push(expected(i));
    check(source, 40);
    check(moved, count);
    moved = moved; // self-assignment must retain inline and overflow contents
    check(moved, count);
}

template<std::size_t... Indices>
static void variadic_case(std::index_sequence<Indices...>) {
    RNBO::listbase<float, 16> list(expected(Indices)...);
    check(list, sizeof...(Indices));
}

template<std::size_t Destination>
static void destination_cases(std::size_t count) {
    copy_assign_case<Destination, 0>(count);
    copy_assign_case<Destination, 4>(count);
    copy_assign_case<Destination, 16>(count);
    copy_assign_case<Destination, 32>(count);
}

struct ClockTarget final : RNBO::EventTarget {
    unsigned calls = 0;
    RNBO::MillisecondTime time = 0;
    RNBO::ClockId index = 0;
    RNBO::ParameterValue value = 0;
    bool has_value = false;
    void processMidiEvent(RNBO::MillisecondTime, int, RNBO::ConstByteArray, RNBO::Index) override {}
    void processClockEvent(RNBO::MillisecondTime t, RNBO::ClockId i, bool has, RNBO::ParameterValue v) override {
        ++calls; time = t; index = i; value = v; has_value = has;
    }
};

/* A real generated patch provides all PatcherInterface implementations. Its
 * DSP remains uninitialized: this override observes root fallback clocks
 * without invoking any generated DSP/event state. */
struct ClockRoot final : RNBO::RNBO_S3_PATCH_CLASS<> {
    unsigned calls = 0;
    void processClockEvent(RNBO::MillisecondTime, RNBO::ClockId, bool, RNBO::ParameterValue) override { ++calls; }
};

static void clocks() {
    ClockRoot root;
    RNBO::MinimalEngine<4> engine(&root);
    ClockTarget first, second;
    engine.scheduleClockEvent(&first, 10, 1.0);
    engine.scheduleClockEventWithValue(&second, 20, 2.0, 0.75f);
    engine.processEventsUntil(0.5);
    assert(first.calls == 0 && second.calls == 0 && root.calls == 0);
    engine.processEventsUntil(1.0);
    assert(first.calls == 1 && first.time == 1.0 && first.index == 10 && !first.has_value);
    assert(second.calls == 0 && root.calls == 0);
    engine.processEventsUntil(2.0);
    assert(second.calls == 1 && second.time == 2.0 && second.index == 20 && second.has_value && second.value == 0.75f);
    assert(root.calls == 0 && engine.getQueueSize() == 0);
    engine.scheduleClockEvent(&first, 30, 3.0);
    engine.scheduleClockEvent(&second, 30, 3.0);
    engine.flushClockEvents(&first, 30, false);
    engine.processEventsUntil(3.0);
    assert(first.calls == 1 && second.calls == 2); // cancellation is target-specific
    engine.scheduleClockEventWithValue(&first, 40, 4.0, 0.25f);
    engine.scheduleClockEventWithValue(&first, 40, 4.0, 0.5f);
    engine.flushClockEventsWithValue(&first, 40, 0.25f, true);
    assert(first.calls == 2 && first.value == 0.25f);
    engine.processEventsUntil(4.0);
    assert(first.calls == 3 && first.value == 0.5f);
    engine.scheduleClockEvent(nullptr, 50, 5.0);
    engine.processEventsUntil(5.0);
    assert(root.calls == 1 && engine.getQueueSize() == 0);
}

int main() {
    for (std::size_t count : {0u, 15u, 16u, 17u, 32u}) {
        destination_cases<0>(count);
        destination_cases<4>(count);
        destination_cases<16>(count);
        destination_cases<32>(count);
        move_case<0>(count);
        move_case<4>(count);
        move_case<16>(count);
        move_case<32>(count);
    }
    variadic_case(std::make_index_sequence<15>{});
    variadic_case(std::make_index_sequence<16>{});
    variadic_case(std::make_index_sequence<17>{});
    variadic_case(std::make_index_sequence<32>{});
    clocks();
    std::puts("rnbo_runtime: inline/overflow list copy, assignment, move/reuse and nested clock dispatch/cancellation passed");
}
