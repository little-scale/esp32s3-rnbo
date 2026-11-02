# Registry-manifest dependency edges, locked to the versions in dependencies.amoled.json.
# IDF dependencies already declared by each component's CMakeLists remain intact.
target_link_libraries(__idf_waveshare__esp32_s3_touch_amoled_1_8 PUBLIC
    idf::esp_codec_dev idf::esp_io_expander_tca9554
    idf::esp_lvgl_port idf::lvgl
    PRIVATE idf::esp_lcd_panel_io_additions idf::esp_lcd_co5300
            idf::esp_lcd_touch_cst816s idf::esp_lcd_touch_ft5x06)
target_link_libraries(__idf_esp_io_expander_tca9554 PUBLIC idf::esp_io_expander)
target_link_libraries(__idf_esp_lcd_panel_io_additions PRIVATE idf::esp_io_expander)
target_link_libraries(__idf_esp_lcd_touch_cst816s PUBLIC idf::esp_lcd_touch)
target_link_libraries(__idf_esp_lcd_touch_ft5x06 PUBLIC idf::esp_lcd_touch)
target_link_libraries(__idf_esp_lvgl_port INTERFACE idf::lvgl)
