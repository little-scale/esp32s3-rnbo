/* SPDX-License-Identifier: MIT */
#include "lifecycle.hpp"
#include "arena.hpp"
extern "C" { __attribute__((weak,visibility("hidden"))) void *__dso_handle=&__dso_handle; }
namespace rnbo_dynamic {
struct Finalizer {void(*function)(void*);void *argument;void *dso;};
static Finalizer finalizers[32];
static std::uint32_t count;
std::uint32_t constructor_runs=0;
volatile std::uint32_t *finalizer_observer=nullptr;
std::uint32_t registered_finalizers(){return count;}
__attribute__((constructor(101))) static void bootstrap(){++constructor_runs;}
}
extern "C" int __cxa_atexit(void(*function)(void*),void *argument,void *dso) {
    using namespace rnbo_dynamic;
    if(!function || count>=32)allocation_failure();
    finalizers[count++]={function,argument,dso};return 0;
}
extern "C" void __cxa_finalize(void *dso) {
    using namespace rnbo_dynamic;
    // Module unload is serialized and occurs after instance destroy. Clear
    // each entry before calling so explicit finalize cannot execute it twice.
    for(std::uint32_t i=count;i>0;--i) {
        auto entry=finalizers[i-1];
        if(entry.function && (!dso || entry.dso==dso)) {
            finalizers[i-1].function=nullptr;entry.function(entry.argument);
        }
    }
}
__attribute__((destructor)) static void shutdown() {
    if(rnbo_dynamic::allocation)rnbo_dynamic::allocation_failure();
    __cxa_finalize(nullptr);
    if(rnbo_dynamic::finalizer_observer)
        *rnbo_dynamic::finalizer_observer=*rnbo_dynamic::finalizer_observer+1;
}
