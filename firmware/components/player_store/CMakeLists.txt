idf_component_register(SRCS "player_store.c" INCLUDE_DIRS "include"
                       REQUIRES json mbedtls spiffs nvs_flash heap esp_partition)
