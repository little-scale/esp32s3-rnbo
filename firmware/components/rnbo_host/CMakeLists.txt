if("$ENV{RNBO_S3_EXPORT_DIR}" STREQUAL "")
    idf_component_register()
else()
    get_filename_component(repo_root "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
    set(prepared "$ENV{RNBO_S3_EXPORT_DIR}")
    foreach(required rnbo_source.h patch_config.h description.json provenance.json manifest.json)
        if(NOT EXISTS "${prepared}/${required}")
            message(FATAL_ERROR "Incomplete prepared RNBO export: ${required}")
        endif()
    endforeach()
    idf_component_register(SRCS "${repo_root}/module-sdk/wrapper/rnbo_s3_static.cpp"
        INCLUDE_DIRS "${repo_root}/module-sdk/include"
        PRIV_INCLUDE_DIRS "${prepared}" "${prepared}/common"
        REQUIRES heap esp_psram)
    target_compile_options(${COMPONENT_LIB} PRIVATE -O2 -fno-fast-math -ffp-contract=off -fno-exceptions -fno-rtti -fno-strict-aliasing)
    # RNBO 1.4.4 emits null checks on fixed signal arrays. Retain the warning,
    # but allow that generated form under GCC 14 without rewriting DSP code.
    set_source_files_properties("${repo_root}/module-sdk/wrapper/rnbo_s3_static.cpp"
        PROPERTIES COMPILE_OPTIONS "-Wno-error=address")
endif()
