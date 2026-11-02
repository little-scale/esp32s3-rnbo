# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.22)
set(COMPONENTS main)
set(EXTRA_COMPONENT_DIRS "${SPIKE_DEPENDENCIES_DIR}/elf_loader" "${SPIKE_DEPENDENCIES_DIR}/cmake_utilities")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(rnbo_loader_fixture)
include("${SPIKE_DEPENDENCIES_DIR}/elf_loader/elf_loader.cmake")
project_elf(rnbo_loader_fixture)
