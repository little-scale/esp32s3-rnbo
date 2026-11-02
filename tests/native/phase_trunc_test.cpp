/* SPDX-License-Identifier: MIT */
#include "phase_trunc.h"
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>

static uint64_t checked;
static void check(float value)
{
    assert(std::isfinite(value) && (double)value>=-9223372036854775808.0 &&
           (double)value<9223372036854775808.0);
    /* Independent mathematical oracle: truncate then reduce modulo 2^32.
     * Binary float values are represented exactly by double here. */
    double reduced=std::fmod(std::trunc((double)value),4294967296.0);
    if (reduced<0) reduced+=4294967296.0;
    assert(rnbo_s3_phase_trunc_f32(value)==(uint32_t)reduced);
    ++checked;
}
static float from_bits(uint32_t bits)
{
    float value;std::memcpy(&value,&bits,sizeof value);return value;
}
int main()
{
    const float edges[]={0.0f,-0.0f,0.25f,-0.25f,1.0f,-1.0f,2147483648.0f,
        -2147483648.0f,4294967040.0f,4294967296.0f,4294967808.0f,
        -4294967296.0f,-4294967808.0f,-9223372036854775808.0f,
        std::nextafter(9223372036854775808.0f,0.0f)};
    for(float value:edges)check(value);
    assert(rnbo_s3_phase_trunc_f32(-1.0f)==UINT32_MAX);
    assert(rnbo_s3_phase_trunc_f32(4294967040.0f)==UINT32_C(4294967040));
    assert(rnbo_s3_phase_trunc_f32(4294967296.0f)==0);
    assert(rnbo_s3_phase_trunc_f32(4294967808.0f)==512);
    /* Every mantissa in the upper accepted exponent, plus its negative
     * fallback counterpart. This includes signed/unsigned boundary lowering. */
    for(uint32_t mantissa=0;mantissa<UINT32_C(0x800000);++mantissa) {
        check(from_bits(UINT32_C(0x4f000000)|mantissa));
        check(from_bits(UINT32_C(0xcf000000)|mantissa));
    }
    const uint32_t boundaries[]={0,1,0x3fffff,0x7ffffe,0x7fffff};
    for(unsigned exponent=0;exponent<=189;++exponent)
        for(uint32_t mantissa: boundaries) {
            const uint32_t bits=(exponent<<23)|mantissa;
            check(from_bits(bits));check(from_bits(bits|UINT32_C(0x80000000)));
        }
    uint32_t random=0x12345678;
    for(unsigned i=0;i<100000;++i) {
        random^=random<<13;random^=random>>17;random^=random<<5;
        check(from_bits((random&UINT32_C(0x807fffff))|(((random>>23)%190)<<23)));
    }
    std::printf("phase_trunc: %llu exact mathematical comparisons passed; no speed claim\n",(unsigned long long)checked);
}
