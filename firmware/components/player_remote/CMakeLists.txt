idf_component_register(SRCS "player_remote.c" "player_remote_core.c"
    INCLUDE_DIRS "include" "../../../module-sdk/include"
    REQUIRES esp_http_server esp_timer esp_hw_support esp_netif lwip json heap)
# Keep control-rate web code small enough for paired application slots.
# Generated RNBO DSP and the audio owner retain their performance settings.
target_compile_options(${COMPONENT_LIB} PRIVATE -Os -fno-inline-small-functions)
idf_component_get_property(remote_http_lib esp_http_server COMPONENT_LIB)
idf_component_get_property(remote_parser_lib http_parser COMPONENT_LIB)
target_compile_options(${remote_http_lib} PRIVATE -Os)
target_compile_options(${remote_parser_lib} PRIVATE -Os)
# HTTP errors are returned to clients; avoid per-request server logging.
target_compile_definitions(${remote_http_lib} PRIVATE LOG_LOCAL_LEVEL=ESP_LOG_NONE)
