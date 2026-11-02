# SPDX-License-Identifier: MIT
get_filename_component(repo_root "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
set(prepared "$ENV{RNBO_TEST_SINE_EXPORT}")
if(NOT EXISTS "${prepared}/rnbo_source.h" OR NOT EXISTS "${prepared}/patch_config.h")
    message(FATAL_ERROR "Supply the exact prepared sine export used to build the dynamic module")
endif()
idf_component_register(SRCS "${repo_root}/module-sdk/wrapper/rnbo_s3_static.cpp"
    INCLUDE_DIRS "${repo_root}/module-sdk/include"
    PRIV_INCLUDE_DIRS "${prepared}" "${prepared}/common"
    REQUIRES heap esp_psram)
target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -fno-fast-math -ffp-contract=off -fno-strict-aliasing -fno-exceptions -fno-rtti)
