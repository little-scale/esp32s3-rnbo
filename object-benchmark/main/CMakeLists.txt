# SPDX-License-Identifier: MIT
get_filename_component(repo_root "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
idf_component_register(SRCS "benchmark.c" "module_host.c" "allocation_probe.c" "stimulus.c" "average_oracle.c" "wave2_oracle.c" "wave4_oracle.c"
    INCLUDE_DIRS "." "${repo_root}/module-sdk/include" "${OBJECT_BENCH_CONFIG_DIR}"
    REQUIRES elf_loader esp_psram esp_timer mbedtls esp_app_format)
foreach(kind strict optimized)
    string(TOUPPER "${kind}" upper)
    if(NOT EXISTS "${OBJECT_BENCH_${upper}_ELF}")
        message(FATAL_ERROR "Missing verified ${kind} RNBO ELF")
    endif()
    configure_file("${OBJECT_BENCH_${upper}_ELF}" "${CMAKE_CURRENT_BINARY_DIR}/object_${kind}_payload.bin" COPYONLY)
    elf_embed_aligned_binary(${COMPONENT_LIB} "${CMAKE_CURRENT_BINARY_DIR}/object_${kind}_payload.bin" BINARY)
endforeach()
target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -fno-fast-math -ffp-contract=off -fno-strict-aliasing)
