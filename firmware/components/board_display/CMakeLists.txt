if("$ENV{RNBO_S3_BOARD}" STREQUAL "xiao")
    idf_component_register()
else()
    if(NOT EXISTS "$ENV{RNBO_S3_VISUAL_DIR}/patch_layout.c")
        message(FATAL_ERROR "Build with tools/build_firmware.py to compile the patch view")
    endif()
    idf_component_register(SRCS "touch_display.c" "board_display.c" "patch_view.c"
        "fonts/rnbo_barlow_12.c" "fonts/rnbo_barlow_14.c" "fonts/rnbo_barlow_16.c" "fonts/rnbo_barlow_22.c"
        "$ENV{RNBO_S3_VISUAL_DIR}/patch_layout.c" INCLUDE_DIRS "include"
        REQUIRES waveshare__esp32_s3_touch_amoled_1_8 esp_lvgl_port lvgl esp_lcd_touch esp_lcd esp_psram)
endif()
