# Native RNBO module SDK

This development route compiles a prepared RNBO Minimal Export into an Xtensa
ELF for the pinned Espressif section loader. It is separate from the unchanged
static wrapper. Package storage, network admission, and a permanent-player UI
are later integration work.

```sh
python3 host/compiler/build_module.py --export build/prepared/sine-v2 \
  --build-dir build/modules/sine
```

The default per-module arena ceiling is 1 MiB. A measured patch can explicitly
request a higher ceiling, up to 4 MiB, with `--max-arena-bytes`. This changes the
module's declared budget; it does not narrow buffers or shorten delay times.

The build uses the content-locked `project_elf` implementation staged under
`build/vendor-loader-spike`. It keeps strict floating-point options and privately
links selected `libm`/`libgcc` archive members. The final ELF must have **zero
undefined imports**. No firmware allocator, unrestricted libc registry, or C++
symbol namespace is borrowed. Generated fixed-array null-check diagnostics stay
visible but are not fatal for the RNBO wrapper translation unit under GCC 14.

The linker can emit exact zero `R_XTENSA_NONE` relocation tombstones, which the
pinned loader rejects. The builder preserves the raw ELF, removes only those
exact zero records, and reduces the relocation section size. It rejects overlap
with protected code/data/header tables. Code/data addresses and bytes, and every
remaining relocation, stay unchanged. Both ELF hashes and normalization counts
are recorded before the normalized artifact passes independent admission.

`rnbo_s3_dynamic.h` defines an allocation-free `DESCRIBE` handshake followed by
`BIND` to caller-owned, aligned PSRAM storage. The shell initializes the explicit
result field to `PENDING`, because `esp_elf_request` discards the entry's C return
value. The descriptor and dynamic-info callback addresses must be checked against
loaded section ranges. The shell must validate relocated constructor/finalizer
targets before executing them.

The context occupies its separately reported prefix of caller storage; the
selected arena follows it. The advertised minimum arena is structural admission,
not a measured initialization requirement. State and executable admission must
consider the whole system, including simultaneous Main and FX, before loading.

There is one live context per loaded image. Each image has its own generated
globals, PRNG, logger, private allocator, and finalizer registry. Initialization
and warm-up happen while detached. The seed is explicit; the private `clock()`
fallback derives ticks from processed sample frames. RNBO's scheduler remains
double precision and processing uses the authoritative 64-bit sample position.

RNBO platform allocations retain their existing base-statistics meaning. The
dynamic statistics extension separately counts C++ `new`, late C++ allocation,
total arena allocation, and arena high-water use. Ordinary, array, sized,
nothrow, and aligned allocation/deallocation routes stay module-local. Late
allocation faults the instance and suppresses its output. Arena exhaustion is a
native trap because unchecked generated accesses cannot safely recover from a
null allocation; sufficient preparation budgets are mandatory.

Destruct the patch after audio detachment, then run ELF finalizers/unmapping,
and only then release caller storage. Destroy permits reconstruction within the
same binding; a live instance prevents rebinding. Metadata strings are copied
through the C ABI. Loaded native code is trusted and is not memory-isolated.

Successful module compilation/import admission does not establish target
execution, timing, allocation behavior, or unload safety. The isolated target
qualification project records those separately.
