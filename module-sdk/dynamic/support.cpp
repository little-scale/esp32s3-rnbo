/* SPDX-License-Identifier: MIT */
/* Private module libc subset. No firmware allocator, errno, clock, or global
 * C++ runtime namespace is imported. Compiled with -fno-builtin to keep these
 * loops from being lowered into recursive calls to themselves. */
#include "arena.hpp"
#include <cstddef>
#include <ctime>
extern "C" {
void *memcpy(void *destination,const void *source,std::size_t size) noexcept {
    auto *out=static_cast<unsigned char*>(destination);auto *in=static_cast<const unsigned char*>(source);
    for(std::size_t i=0;i<size;++i)out[i]=in[i];
    return destination;
}
void *memmove(void *destination,const void *source,std::size_t size) noexcept {
    auto *out=static_cast<unsigned char*>(destination);auto *in=static_cast<const unsigned char*>(source);
    if(out<in)for(std::size_t i=0;i<size;++i)out[i]=in[i];
    else if(out>in)while(size){--size;out[size]=in[size];}
    return destination;
}
void *memset(void *destination,int value,std::size_t size) noexcept {
    auto *out=static_cast<unsigned char*>(destination);for(std::size_t i=0;i<size;++i)out[i]=static_cast<unsigned char>(value);return destination;
}
int memcmp(const void *a,const void *b,std::size_t size) noexcept {
    auto *x=static_cast<const unsigned char*>(a);auto *y=static_cast<const unsigned char*>(b);
    for(std::size_t i=0;i<size;++i)if(x[i]!=y[i])return x[i]<y[i]?-1:1;
    return 0;
}
std::size_t strlen(const char *s) noexcept {std::size_t n=0;while(s[n])++n;return n;}
int strcmp(const char *a,const char *b) noexcept {while(*a && *a==*b){++a;++b;}return static_cast<unsigned char>(*a)-static_cast<unsigned char>(*b);}
int strncmp(const char *a,const char *b,std::size_t n) noexcept {while(n && *a && *a==*b){--n;++a;++b;}return n?static_cast<unsigned char>(*a)-static_cast<unsigned char>(*b):0;}
char *strcpy(char *out,const char *in) noexcept {char *start=out;while((*out++=*in++)){}return start;}
char *strncpy(char *out,const char *in,std::size_t n) noexcept {std::size_t i=0;for(;i<n && in[i];++i)out[i]=in[i];for(;i<n;++i)out[i]=0;return out;}
[[noreturn]] void abort() noexcept {rnbo_dynamic::allocation_failure();}
[[noreturn]] void __cxa_pure_virtual(){rnbo_dynamic::allocation_failure();}
[[noreturn]] void __cxa_deleted_virtual(){rnbo_dynamic::allocation_failure();}
[[noreturn]] void __cxa_throw_bad_array_new_length(){rnbo_dynamic::allocation_failure();}
static int local_errno;
int *__errno(){return &local_errno;}
clock_t clock() noexcept {
    // Truncating to the target clock_t width is deliberate. This fallback is
    // seed/systemticks support, not RNBO's authoritative double scheduler time.
    return static_cast<clock_t>((rnbo_dynamic::sample_clock/44100)*1000000+
                               (rnbo_dynamic::sample_clock%44100)*1000000/44100);
}
}
