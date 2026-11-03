/* SPDX-License-Identifier: MIT
 * Original direct-producer test. RNBO Float32, variable-block generator export;
 * not the module SDK's fixed-256 C ABI and not evidence of target execution. */
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#define RNBO_USE_FLOAT32
#define RNBO_NOSTL
#define RNBO_NOTHROW
#define RNBO_NO_PATCHERFACTORY
#define RNBO_FIXEDLISTSIZE 16
#include "RNBO_Common.h"
#include "rnbo_source.h"
#undef trunc
#undef autoref

#ifndef GEN_PROGRAM
#error GEN_PROGRAM must select an original fixture (1 feedback, 2 swap)
#endif

static constexpr unsigned frames = 4096;
static constexpr unsigned resets[] = {513, 1024, 2051, 3001};
static constexpr unsigned prepares[] = {257, 1300};
static void require(bool condition, const char *message) {
    if (!condition) { std::fprintf(stderr, "%s\n", message); std::exit(1); }
}
static std::uint32_t bits(float value) {
    std::uint32_t word; std::memcpy(&word, &value, sizeof word); return word;
}
static float input(unsigned frame, unsigned channel) {
    constexpr float pattern[] = {0.25f, -0.125f, 0.5f, 0.f, -0.25f, 0.125f, -0.5f};
    return pattern[(frame + channel * 3) % 7];
}
static double feedback_history(unsigned frame, unsigned start) {
    // Closed-form convolution over independent input words. Truncating after
    // 64 terms contributes <2^-64, well below the fixed numerical gate.
    double sum = 0;
    for (unsigned age = 1; age <= std::min(frame - start, 64u); ++age)
        sum += std::ldexp(static_cast<double>(input(frame - age, 0)), -static_cast<int>(age - 1));
    return sum;
}
static std::vector<float> render(unsigned partition, double &maximum_error, unsigned &reset_checks, unsigned &prepare_checks) {
    RNBO::rnbos3patch<> patch;
    patch.initialize();
    patch.prepareToProcess(44100, 256, true);
    require(patch.getNumInputChannels() == 2 && patch.getNumOutputChannels() == 2, "fixture channel metadata changed");
    require(patch.getNumParameters() == 1 && patch.getNumDataRefs() == 0, "fixture resource/parameter metadata changed");
    std::vector<float> result(frames * 2);
    std::array<float, 256> left{}, right{}, out_left{}, out_right{};
    const float *inputs[] = {left.data(), right.data()};
    float *outputs[] = {out_left.data(), out_right.data()};
    unsigned position = 0, epoch_start = 0, chunk = 0;
    while (position < frames) {
        for (unsigned event : resets) if (position == event) {
            // This is the actual authored param -> set reset -> Gen reset
            // action, including repeated identical values. It invokes history
            // initializers, rather than a guessed generated reset method.
            patch.setParameterValue(0, 1, RNBO::TimeNow);
            require(patch.getParameterValue(0) == 1, "reset parameter readback mismatch");
            epoch_start = position; ++reset_checks;
        }
        for (unsigned event : prepares) if (position == event) {
            patch.prepareToProcess(44100, 256, true);
            ++prepare_checks;
        }
        constexpr unsigned mixed[] = {1, 2, 7, 255, 256, 3, 17};
        unsigned count = partition ? partition : mixed[chunk++ % 7];
        count = std::min(count, frames - position);
        for (unsigned event : resets) if (event > position) count = std::min(count, event - position);
        for (unsigned event : prepares) if (event > position) count = std::min(count, event - position);
        for (unsigned i = 0; i < count; ++i) {
            left[i] = input(position + i, 0); right[i] = input(position + i, 1);
        }
        patch.process(inputs, 2, outputs, 2, count);
        for (unsigned i = 0; i < count; ++i) {
            const unsigned frame = position + i;
            double expected[2];
#if GEN_PROGRAM == 1
            expected[1] = feedback_history(frame, epoch_start);
            expected[0] = static_cast<double>(input(frame, 0)) + 0.5 * expected[1];
#elif GEN_PROGRAM == 2
            expected[0] = ((frame - epoch_start) & 1u) ? 2 : 1;
            expected[1] = ((frame - epoch_start) & 1u) ? 1 : 2;
#else
#error Unknown GEN_PROGRAM
#endif
            for (unsigned channel = 0; channel < 2; ++channel) {
                const float actual = channel ? out_right[i] : out_left[i];
                require(std::isfinite(actual), "nonfinite Gen output");
                const double error = std::abs(static_cast<double>(actual) - expected[channel]);
                maximum_error = std::max(maximum_error, error);
                require(error <= 2e-6, "independent one-sample history model failed");
                result[frame * 2 + channel] = actual;
            }
        }
        position += count;
    }
    return result;
}
int main(int argc, char **argv) {
    require(argc == 2, "usage: gen-probe OUTPUT.f32");
    double maximum_error = 0;
    unsigned reset_checks = 0, prepare_checks = 0;
    const auto reference = render(1, maximum_error, reset_checks, prepare_checks);
    unsigned comparisons = 0;
    // A new constructed patch for each partition, then another reconstruction
    // for each partition. Events remain at the same absolute sample boundaries.
    for (unsigned repeat = 0; repeat < 2; ++repeat) for (unsigned partition : {1u, 2u, 7u, 255u, 256u, 0u}) {
        const auto actual = render(partition, maximum_error, reset_checks, prepare_checks);
        for (unsigned i = 0; i < actual.size(); ++i) {
            require(bits(actual[i]) == bits(reference[i]), "partition/reconstruction changed output bits");
            ++comparisons;
        }
    }
    auto *file = std::fopen(argv[1], "wb");
    require(file != nullptr, "cannot create capture");
    require(std::fwrite(reference.data(), sizeof(float), reference.size(), file) == reference.size(), "capture write failed");
    require(std::fclose(file) == 0, "capture close failed");
    std::printf("{\"program\":%d,\"frames\":%u,\"channels\":2,\"reconstructions\":13,\"partition_compared_words\":%u,\"reset_actions\":%u,\"repeated_prepares\":%u,\"maximum_ideal_error\":%.17g,\"gate\":0.000002,\"module_abi\":false,\"hardware\":false}\n", GEN_PROGRAM, frames, comparisons, reset_checks, prepare_checks, maximum_error);
}
