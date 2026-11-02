# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.22)
set(COMPONENTS main elf_loader cmake_utilities lwip)
set(EXTRA_COMPONENT_DIRS "${SPIKE_DEPENDENCIES_DIR}/elf_loader" "${SPIKE_DEPENDENCIES_DIR}/cmake_utilities")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(rnbo_loader_spike)
# The pinned loader includes sys/socket.h even with libc/IDF exports disabled.
# Declare its private header dependency for IDF's minimal component build.
# This enables no symbol exports and does not initialize the network stack.
idf_component_get_property(loader_library elf_loader COMPONENT_LIB)
target_link_libraries(${loader_library} PRIVATE idf::lwip)
