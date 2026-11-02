if("$ENV{RNBO_S3_BOARD}" STREQUAL "xiao")
    idf_component_register(SRCS "board_audio_i2s.c" INCLUDE_DIRS "include"
        REQUIRES esp_driver_i2s esp_driver_gpio esp_psram esp_hw_support)
else()
    idf_component_register(SRCS "board_audio.c" INCLUDE_DIRS "include"
        REQUIRES waveshare__esp32_s3_touch_amoled_1_8 esp_codec_dev
                 esp_driver_i2s esp_driver_gpio)
endif()
