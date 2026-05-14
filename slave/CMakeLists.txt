cmake_minimum_required(VERSION 3.14)

include(cmake/prelude.cmake)

project(
    slave
    VERSION 0.1.0
    DESCRIPTION "Short description"
    HOMEPAGE_URL "https://example.com/"
    LANGUAGES C
)

include(cmake/project-is-top-level.cmake)
include(cmake/variables.cmake)

# ---- Declare library ----

add_library(
    slave_slave
    source/slave.c
)
add_library(slave::slave ALIAS slave_slave)

include(GenerateExportHeader)
generate_export_header(
    slave_slave
    BASE_NAME slave
    EXPORT_FILE_NAME export/slave/slave_export.h
)

if(NOT BUILD_SHARED_LIBS)
  target_compile_definitions(slave_slave PUBLIC SLAVE_STATIC_DEFINE)
endif()

set_target_properties(
    slave_slave PROPERTIES
    C_VISIBILITY_PRESET hidden
    VERSION "${PROJECT_VERSION}"
    SOVERSION "${PROJECT_VERSION_MAJOR}"
    EXPORT_NAME slave
    OUTPUT_NAME slave
)

target_include_directories(
    slave_slave ${warning_guard}
    PUBLIC
    "\$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
)

target_include_directories(
    slave_slave SYSTEM
    PUBLIC
    "\$<BUILD_INTERFACE:${PROJECT_BINARY_DIR}/export>"
)

target_compile_features(slave_slave PUBLIC c_std_11)

# ---- Install rules ----

if(NOT CMAKE_SKIP_INSTALL_RULES)
  include(cmake/install-rules.cmake)
endif()

# ---- Developer mode ----

if(NOT slave_DEVELOPER_MODE)
  return()
elseif(NOT PROJECT_IS_TOP_LEVEL)
  message(
      AUTHOR_WARNING
      "Developer mode is intended for developers of slave"
  )
endif()

include(cmake/dev-mode.cmake)
