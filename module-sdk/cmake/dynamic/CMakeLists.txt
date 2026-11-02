# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.22)
set(COMPONENTS main)
set(RNBO_S3_MAX_ARENA_BYTES "1048576" CACHE STRING "Explicit per-module arena ceiling (default 1 MiB; maximum 4 MiB)")
if(NOT RNBO_S3_MAX_ARENA_BYTES MATCHES "^[0-9]+$" OR RNBO_S3_MAX_ARENA_BYTES LESS 4096 OR RNBO_S3_MAX_ARENA_BYTES GREATER 4194304)
  message(FATAL_ERROR "RNBO_S3_MAX_ARENA_BYTES must be 4096..4194304")
endif()
if(NOT RNBO_S3_DEPENDENCIES_DIR OR NOT RNBO_S3_EXPORT_DIR)
  message(FATAL_ERROR "Supply pinned RNBO_S3_DEPENDENCIES_DIR and a prepared RNBO_S3_EXPORT_DIR")
endif()
set(EXTRA_COMPONENT_DIRS "${RNBO_S3_DEPENDENCIES_DIR}/elf_loader" "${RNBO_S3_DEPENDENCIES_DIR}/cmake_utilities")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(rnbo_s3_dynamic)
# Private static arithmetic/math support, never the firmware's C++ runtime or
# allocator registry. Exclude archive exports and bind defined module symbols
# locally so two separately loaded RNBO images keep independent namespaces.
execute_process(COMMAND ${CMAKE_C_COMPILER} -print-libgcc-file-name OUTPUT_VARIABLE module_libgcc OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
execute_process(COMMAND ${CMAKE_C_COMPILER} -print-file-name=libm.a OUTPUT_VARIABLE module_libm OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
set(ELF_LIBS "-Wl,-Bsymbolic -Wl,--exclude-libs,ALL -Wl,--start-group ${module_libm} ${module_libgcc} -Wl,--end-group")
include("${RNBO_S3_DEPENDENCIES_DIR}/elf_loader/elf_loader.cmake")
project_elf(rnbo_s3_dynamic)
