# SPDX-License-Identifier: MIT
idf_component_register(SRCS "fixture.cpp" INCLUDE_DIRS "../../include")
target_compile_options(${COMPONENT_LIB} PRIVATE -fno-fast-math -ffp-contract=off -fno-exceptions -fno-rtti -fno-devirtualize)
if(SPIKE_BAD_IMPORT)
  target_compile_definitions(${COMPONENT_LIB} PRIVATE SPIKE_BAD_IMPORT=1)
endif()
