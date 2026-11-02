# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.22)
set(COMPONENTS main static_reference elf_loader cmake_utilities lwip)
set(EXTRA_COMPONENT_DIRS "${RNBO_TEST_DEPENDENCIES_DIR}/elf_loader" "${RNBO_TEST_DEPENDENCIES_DIR}/cmake_utilities")
set(ENV{RNBO_TEST_SINE_EXPORT} "${RNBO_TEST_SINE_EXPORT}")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(rnbo_dynamic_qualification VERSION 0.1.0)
# Pinned loader needs socket headers even with every broad export table disabled.
# No network stack is initialized by this qualification application.
idf_component_get_property(loader_library elf_loader COMPONENT_LIB)
target_link_libraries(${loader_library} PRIVATE idf::lwip)
