get_filename_component(repo_root "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
idf_component_register(SRCS "${repo_root}/runtime/pcm_capture.c" INCLUDE_DIRS "${repo_root}/runtime")
