if("$ENV{RNBO_S3_BOARD}" STREQUAL "xiao")
    idf_component_register()
else()
    set(display_layout "$ENV{RNBO_S3_VISUAL_DIR}/patch_layout.c")
    set(display_player_requires "")
    if("$ENV{RNBO_S3_PLAYER}" STREQUAL "ON")
        set(display_layout "player_layout.c")
        set(display_player_requires json heap player_inputs)
    elseif(NOT EXISTS "$ENV{RNBO_S3_VISUAL_DIR}/patch_layout.c")
        message(FATAL_ERROR "Build with tools/build_firmware.py to compile the patch view")
    endif()
    idf_component_register(SRCS "touch_display.c" "board_display.c" "patch_view.c"
        "fonts/rnbo_barlow_12.c" "fonts/rnbo_barlow_14.c" "fonts/rnbo_barlow_16.c" "fonts/rnbo_barlow_22.c"
        "${display_layout}" INCLUDE_DIRS "include"
        REQUIRES waveshare__esp32_s3_touch_amoled_1_8 esp_lvgl_port lvgl esp_lcd_touch esp_lcd esp_psram ${display_player_requires})
    if("$ENV{RNBO_S3_PLAYER}" STREQUAL "ON")
        target_compile_definitions(${COMPONENT_LIB} PUBLIC RNBO_S3_PLAYER=1)
    endif()
endif()
