cmake_minimum_required(VERSION 3.22)
project(rnbo_patch_preview C)
set(CMAKE_C_STANDARD 11)
set(CMAKE_BUILD_TYPE Release)
set(LV_CONF_PATH "${CMAKE_CURRENT_LIST_DIR}/lv_conf.h" CACHE STRING "" FORCE)
add_subdirectory("${RNBO_ROOT}/build/vendor-amoled/lvgl" lvgl)
set(ui "${RNBO_ROOT}/firmware/components/board_display")
add_executable(patch_preview preview.c "${ui}/board_display.c" "${ui}/patch_view.c"
    "${ui}/fonts/rnbo_barlow_12.c" "${ui}/fonts/rnbo_barlow_14.c" "${ui}/fonts/rnbo_barlow_16.c" "${ui}/fonts/rnbo_barlow_22.c"
    "${VISUAL_DIR}/patch_layout.c")
target_include_directories(patch_preview PRIVATE "." "${ui}/include" "${VISUAL_DIR}")
target_link_libraries(patch_preview PRIVATE lvgl)
target_compile_options(patch_preview PRIVATE -UNDEBUG)
