cmake_minimum_required(VERSION 3.14)

include(cmake/prelude.cmake)

project(
    tethys
    VERSION 0.1.0
    DESCRIPTION "Tethys slave - portable C11 XCP slave library (marine + space profiles)"
    HOMEPAGE_URL "https://github.com/goldr0g3r/tethys"
    LANGUAGES C
)

include(cmake/project-is-top-level.cmake)
include(cmake/variables.cmake)

# ---- Declare library ----
#
# Source files live under src/{core,transport,platform}/ per parent plan §14.
# At Phase-0 only src/core/tethys.c exists; later phases add modules without
# touching this top-level CMakeLists.txt (each subdir gets its own CMake glob
# via target_sources(... PRIVATE ...)).
add_library(
    tethys_slave
    src/core/tethys.c
)
add_library(tethys::slave ALIAS tethys_slave)

include(GenerateExportHeader)
generate_export_header(
    tethys_slave
    BASE_NAME tethys
    EXPORT_FILE_NAME export/tethys/tethys_export.h
)

if(NOT BUILD_SHARED_LIBS)
  target_compile_definitions(tethys_slave PUBLIC TETHYS_STATIC_DEFINE)
endif()

set_target_properties(
    tethys_slave PROPERTIES
    C_VISIBILITY_PRESET hidden
    VERSION "${PROJECT_VERSION}"
    SOVERSION "${PROJECT_VERSION_MAJOR}"
    EXPORT_NAME slave
    OUTPUT_NAME tethys_slave
)

target_include_directories(
    tethys_slave ${warning_guard}
    PUBLIC
    "\$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
)

target_include_directories(
    tethys_slave SYSTEM
    PUBLIC
    "\$<BUILD_INTERFACE:${PROJECT_BINARY_DIR}/export>"
)

target_compile_features(tethys_slave PUBLIC c_std_11)

# ---- Install rules ----

if(NOT CMAKE_SKIP_INSTALL_RULES)
  include(cmake/install-rules.cmake)
endif()

# ---- Developer mode ----

if(NOT tethys_DEVELOPER_MODE)
  return()
elseif(NOT PROJECT_IS_TOP_LEVEL)
  message(
      AUTHOR_WARNING
      "Developer mode is intended for developers of tethys"
  )
endif()

include(cmake/dev-mode.cmake)
