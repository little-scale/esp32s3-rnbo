# SPDX-License-Identifier: MIT
get_filename_component(repo_root "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
idf_component_register(SRCS "main.cpp" "${repo_root}/object-benchmark/main/allocation_probe.c"
    INCLUDE_DIRS "." "${repo_root}/object-benchmark/main"
    REQUIRES esp_psram esp_timer esp_app_format mbedtls)
if(CMAKE_BUILD_EARLY_EXPANSION)
    return()
endif()
if(NOT DEFINED GEN_PROBE_CONFIG_DIR OR NOT EXISTS "${GEN_PROBE_CONFIG_DIR}/programs.cmake")
    message(FATAL_ERROR "GEN_PROBE_CONFIG_DIR must name a verified closed probe configuration")
endif()
include("${GEN_PROBE_CONFIG_DIR}/programs.cmake")
target_sources(${COMPONENT_LIB} PRIVATE ${GEN_PROBE_PROGRAM_SOURCES} "${GEN_PROBE_CONFIG_DIR}/references.c")
target_include_directories(${COMPONENT_LIB} PRIVATE "${GEN_PROBE_CONFIG_DIR}" "${GEN_PROBE_COMMON_DIR}")
target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -fno-fast-math -ffp-contract=off -fno-strict-aliasing)
