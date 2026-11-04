set(midi_sources "midi_core.c" "player_midi.c")
if(CONFIG_RNBO_S3_USB_MIDI_HOST)
    list(APPEND midi_sources "usb_midi_host.c")
endif()
idf_component_register(SRCS ${midi_sources} INCLUDE_DIRS "include" "../../../module-sdk/include"
    REQUIRES json nvs_flash esp_timer esp_driver_uart esp_driver_gpio usb)
target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -fno-fast-math -ffp-contract=off)
