# SPDX-License-Identifier: MIT
idf_component_register(SRCS "phase.c" INCLUDE_DIRS "../../runtime" REQUIRES esp_timer esp_app_format)
target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -fno-fast-math -ffp-contract=off)
