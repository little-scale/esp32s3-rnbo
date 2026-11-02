# SPDX-License-Identifier: MIT
get_filename_component(sdk_root "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
idf_component_register(SRCS "${sdk_root}/dynamic/rnbo_s3_dynamic.cpp" "${sdk_root}/dynamic/arena.cpp" "${sdk_root}/dynamic/lifecycle.cpp" "${sdk_root}/dynamic/support.cpp"
  INCLUDE_DIRS "${sdk_root}/include" "${sdk_root}/dynamic" "${RNBO_S3_EXPORT_DIR}" "${RNBO_S3_EXPORT_DIR}/common")
target_compile_definitions(${COMPONENT_LIB} PRIVATE RNBO_S3_DYNAMIC_MAX_ARENA_BYTES=${RNBO_S3_MAX_ARENA_BYTES}u)
target_compile_options(${COMPONENT_LIB} PRIVATE -fno-fast-math -ffp-contract=off -fno-strict-aliasing
  -fno-exceptions -fno-rtti -fno-threadsafe-statics -fno-unwind-tables -fno-asynchronous-unwind-tables
  -fno-builtin -fno-tree-loop-distribute-patterns)
# RNBO 1.4.4 retains null checks on generated fixed signal-array members.
# GCC 14 proves those addresses nonnull; retain the warning without turning
# that generated-source-only diagnostic into a module build failure.
set_source_files_properties("${sdk_root}/dynamic/rnbo_s3_dynamic.cpp" PROPERTIES COMPILE_OPTIONS "-Wno-error=address")
