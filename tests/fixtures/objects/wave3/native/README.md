# Reproduce the native qualification

From the repository root, with Node, a Clang/GCC C/C++ toolchain and an
**authorised local RNBO 1.4.4 installation**:

```sh
python3 host/compiler/qualify_wave3.py --out build/wave3-qualification
```

The output directory must be new. Use `--rnbo-dir /path/to/RNBO` when the
exporter's standard package discovery does not find the authorised package.
Generated RNBO code stays in ignored `build/`, with its notices preserved.

The command exports all ten original graphs, applies normal strict runtime
corrections, creates the fixed input vectors and ordered boundary events, then
runs the actual production dynamic C ABI in O3 and UBSan builds. Reports keep
Float32/PCM captures, parameter traces, allocation counters, reconstruction
checks, immutable source snapshots and hashes. No device is accessed.

Exit status **0** means every gate passed, **1** means qualification failures
were retained in `report.json`, and **2** means setup or integrity failed. The
current strict baseline deliberately returns **1**: six cases exceed their
unchanged mathematical accuracy limits. Health and cross-build compatibility
are separate results; do not raise tolerances to make the run pass.

Select the original 15 onepole programs explicitly to compare the experimental
corrected profile:

```sh
python3 host/compiler/qualify_wave3.py --onepole-only --stable-onepole \
  --out build/qualify-stable-onepole
```

The recorded corrected run exits 0. The same selection without
`--stable-onepole` retains five strict-baseline accuracy failures and exits 1.
The default remains the full 45-program strict run. Without `--onepole-only`,
the profile flag affects only the three onepole graphs and other selected
objects remain strict. The report records both selection and profile. See the
[finite proof and wider qualification](../../../../../docs/stable-onepole.md);
these 15 cases are a subset of that evidence.

`probe.cpp` and `inputs.py` are original MIT test code. The native build uses
host libc/libm and does **not** link the target's `support.cpp`. Constructor and
finalizer counters are explicit native stubs. Native success does not prove
ELF loading, target import admission, hardware behavior or CPU savings. Direct
operator resets, aliases and codebox forms remain outside this wave.
