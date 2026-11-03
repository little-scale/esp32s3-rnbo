# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.22)
if(NOT DEFINED SMOKE_DEPENDENCIES_DIR)
    message(FATAL_ERROR "SMOKE_DEPENDENCIES_DIR must name the pinned loader dependencies")
endif()
set(COMPONENTS main elf_loader cmake_utilities lwip)
set(EXTRA_COMPONENT_DIRS "${SMOKE_DEPENDENCIES_DIR}/elf_loader" "${SMOKE_DEPENDENCIES_DIR}/cmake_utilities")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(rnbo_hardware_smoke VERSION 0.1.0)
idf_component_get_property(loader_library elf_loader COMPONENT_LIB)
# The pinned loader includes socket headers; this does not start networking.
target_link_libraries(${loader_library} PRIVATE idf::lwip)
