/* SPDX-License-Identifier: MIT */
#include "arena.hpp"
#include <cstring>
#include <limits>
#include <new>
namespace rnbo_dynamic {
AllocationState *allocation=nullptr;
std::uint32_t bootstrap_allocation_attempts=0;
std::uint64_t sample_clock=0;
struct Header {std::size_t bytes,cookie;};
static_assert(sizeof(Header)<=alignment,"allocation header exceeds base alignment");
[[noreturn]] void allocation_failure() {
    if(allocation)++allocation->errors;
    /* Native code cannot safely continue after unchecked generated new/malloc
     * fails. No firmware heap, watchdog spin, or host allocator is borrowed. */
    __builtin_trap();
}
void *allocate(std::size_t requested,AllocationKind kind,std::size_t align) {
    if(!allocation){++bootstrap_allocation_attempts;allocation_failure();}
    if(align<alignment)align=alignment;
    if((align&(align-1)) || align>4096)allocation_failure();
    std::size_t size=requested?requested:1;
    constexpr auto maximum=std::numeric_limits<std::size_t>::max();
    const auto base=reinterpret_cast<std::uintptr_t>(allocation->arena);
    if(allocation->used>maximum-alignment-(align-1) ||
       base>maximum-allocation->used-alignment-(align-1))allocation_failure();
    const std::size_t start=((base+allocation->used+alignment+align-1)&~(align-1))-base;
    if(start>allocation->capacity || size>allocation->capacity-start ||
       start+size>maximum-(alignment-1))allocation_failure();
    const std::size_t end=(start+size+alignment-1)&~(alignment-1);
    if(end>allocation->capacity)allocation_failure();
    Header header{requested,static_cast<std::size_t>(0x524e424fu)^start^requested};
    std::memcpy(allocation->arena+start-alignment,&header,sizeof header);
    allocation->used=end;
    if(end>allocation->high_water)allocation->high_water=end;
    ++allocation->total;if(allocation->running)++allocation->total_late;
    if(kind==AllocationKind::platform){++allocation->allocations;if(allocation->running)++allocation->late;}
    else{++allocation->cpp_new;if(allocation->running)++allocation->cpp_late;}
    return allocation->arena+start;
}
std::size_t allocated_size(void *pointer) {
    if(!allocation || !pointer)allocation_failure();
    auto base=reinterpret_cast<std::uintptr_t>(allocation->arena);
    auto address=reinterpret_cast<std::uintptr_t>(pointer);
    if(address<base || address-base<alignment || address-base>=allocation->used ||
       (address-base)%alignment)allocation_failure();
    const auto offset=address-base;
    Header header{};std::memcpy(&header,allocation->arena+offset-alignment,sizeof header);
    if(header.cookie!=(static_cast<std::size_t>(0x524e424fu)^offset^header.bytes) ||
       header.bytes>allocation->used-offset)allocation_failure();
    return header.bytes;
}
void deallocate(void *pointer,bool cpp) {
    if(!pointer)return;
    (void)allocated_size(pointer);
    if(cpp)++allocation->cpp_delete;
    // Monotonic lifetime storage: destructor runs first, whole binding resets at create.
}
}
void *operator new(std::size_t bytes){return rnbo_dynamic::allocate(bytes,rnbo_dynamic::AllocationKind::cpp);}
void *operator new[](std::size_t bytes){return ::operator new(bytes);}
void *operator new(std::size_t bytes,const std::nothrow_t&) noexcept{return ::operator new(bytes);}
void *operator new[](std::size_t bytes,const std::nothrow_t&) noexcept{return ::operator new(bytes);}
void *operator new(std::size_t bytes,std::align_val_t align){return rnbo_dynamic::allocate(bytes,rnbo_dynamic::AllocationKind::cpp,static_cast<std::size_t>(align));}
void *operator new[](std::size_t bytes,std::align_val_t align){return ::operator new(bytes,align);}
void *operator new(std::size_t bytes,std::align_val_t align,const std::nothrow_t&) noexcept{return ::operator new(bytes,align);}
void *operator new[](std::size_t bytes,std::align_val_t align,const std::nothrow_t&) noexcept{return ::operator new(bytes,align);}
void operator delete(void *p) noexcept{rnbo_dynamic::deallocate(p,true);}
void operator delete[](void *p) noexcept{::operator delete(p);}
void operator delete(void *p,std::size_t) noexcept{::operator delete(p);}
void operator delete[](void *p,std::size_t) noexcept{::operator delete(p);}
void operator delete(void *p,const std::nothrow_t&) noexcept{::operator delete(p);}
void operator delete[](void *p,const std::nothrow_t&) noexcept{::operator delete(p);}
void operator delete(void *p,std::align_val_t) noexcept{::operator delete(p);}
void operator delete[](void *p,std::align_val_t) noexcept{::operator delete(p);}
void operator delete(void *p,std::size_t,std::align_val_t) noexcept{::operator delete(p);}
void operator delete[](void *p,std::size_t,std::align_val_t) noexcept{::operator delete(p);}
void operator delete(void *p,std::align_val_t,const std::nothrow_t&) noexcept{::operator delete(p);}
void operator delete[](void *p,std::align_val_t,const std::nothrow_t&) noexcept{::operator delete(p);}
