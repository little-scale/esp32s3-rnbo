idf_component_register(SRCS "player_network.c" "player_network_protocol.c" "player_network_scan.c" "player_network_handoff.c"
                       INCLUDE_DIRS "include" REQUIRES esp_wifi esp_event esp_netif lwip mbedtls nvs_flash esp_timer esp_hw_support json heap)
