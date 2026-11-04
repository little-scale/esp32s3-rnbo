# SPDX-License-Identifier: MIT
get_filename_component(repo_root "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
idf_component_register(SRCS "player_loader.c"
    INCLUDE_DIRS "include" "${repo_root}/module-sdk/include"
    REQUIRES elf_loader esp_psram)
target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -fno-fast-math -ffp-contract=off -fno-strict-aliasing)
