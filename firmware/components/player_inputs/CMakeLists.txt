idf_component_register(SRCS "player_inputs.c" "player_inputs_core.c" "player_touchscreen.c" INCLUDE_DIRS "include"
    REQUIRES json esp_adc esp_driver_gpio esp_driver_touch_sens esp_timer)
target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -fno-fast-math -ffp-contract=off)
