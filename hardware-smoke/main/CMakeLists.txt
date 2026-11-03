# SPDX-License-Identifier: MIT
get_filename_component(repo_root "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
idf_component_register(SRCS "smoke.c"
    "${repo_root}/object-benchmark/main/module_host.c"
    "${repo_root}/object-benchmark/main/allocation_probe.c"
    INCLUDE_DIRS "." "${repo_root}/object-benchmark/main" "${repo_root}/module-sdk/include"
        "${SMOKE_CONFIG_DIR}" "${CMAKE_CURRENT_BINARY_DIR}"
    REQUIRES elf_loader esp_psram esp_timer mbedtls esp_app_format)
if(CMAKE_BUILD_EARLY_EXPANSION)
    return()
endif()
if(NOT DEFINED SMOKE_CONFIG_DIR OR NOT EXISTS "${SMOKE_CONFIG_DIR}/smoke_cases.h")
    message(FATAL_ERROR "SMOKE_CONFIG_DIR must contain the generated smoke_cases.h")
endif()
if(NOT DEFINED SMOKE_MODULES_CMAKE OR NOT EXISTS "${SMOKE_MODULES_CMAKE}")
    message(FATAL_ERROR "SMOKE_MODULES_CMAKE must name the ordered ELF manifest")
endif()
include("${SMOKE_MODULES_CMAKE}")
list(LENGTH SMOKE_MODULE_FILES smoke_count)
if(smoke_count LESS 1 OR smoke_count GREATER 128)
    message(FATAL_ERROR "Smoke manifest must contain 1..128 verified module ELFs")
endif()
set(payload_header "${CMAKE_CURRENT_BINARY_DIR}/smoke_payloads.h")
file(WRITE "${payload_header}" "/* Generated aligned ELF payload declarations. */\n#pragma once\n#include <stdint.h>\n")
set(index 0)
foreach(module_file IN LISTS SMOKE_MODULE_FILES)
    if(NOT EXISTS "${module_file}" OR IS_DIRECTORY "${module_file}")
        message(FATAL_ERROR "Missing smoke module ELF: ${module_file}")
    endif()
    set(payload "${CMAKE_CURRENT_BINARY_DIR}/smoke_${index}.bin")
    configure_file("${module_file}" "${payload}" COPYONLY)
    elf_embed_aligned_binary(${COMPONENT_LIB} "${payload}" BINARY)
    file(APPEND "${payload_header}"
        "extern const uint8_t smoke_payload_${index}_start[] asm(\"_binary_smoke_${index}_bin_start\");\n"
        "extern const uint8_t smoke_payload_${index}_end[] asm(\"_binary_smoke_${index}_bin_end\");\n")
    math(EXPR index "${index}+1")
endforeach()
target_compile_definitions(${COMPONENT_LIB} PRIVATE SMOKE_EMBEDDED_MODULE_COUNT=${smoke_count})
target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -fno-fast-math -ffp-contract=off -fno-strict-aliasing)
