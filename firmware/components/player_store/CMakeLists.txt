idf_component_register(SRCS "player_store.c" INCLUDE_DIRS "include" "../../../module-sdk/include"
                       REQUIRES json mbedtls spiffs nvs_flash heap esp_partition)
