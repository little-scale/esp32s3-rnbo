# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.22)
set(COMPONENTS main elf_loader cmake_utilities lwip)
set(EXTRA_COMPONENT_DIRS "${OBJECT_BENCH_DEPENDENCIES_DIR}/elf_loader" "${OBJECT_BENCH_DEPENDENCIES_DIR}/cmake_utilities")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(rnbo_object_benchmark VERSION 0.1.0)
idf_component_get_property(loader_library elf_loader COMPONENT_LIB)
# Required by the pinned loader's socket-header inclusion even though no
# network stack or broad symbol registry is initialized in this application.
target_link_libraries(${loader_library} PRIVATE idf::lwip)
