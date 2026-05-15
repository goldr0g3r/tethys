include(cmake/folders.cmake)

# Tethys note: tests are owned by Ceedling under slave/tests/ (Phase-1+).
# Tethys keeps CTest enabled in case future integration tests want it (e.g.
# Phase 9 HIL bench harness) but does not auto-add the legacy cmake-init
# CTest stub which has been removed in chore(scaffold-tests).
include(CTest)

option(BUILD_MCSS_DOCS "Build documentation using Doxygen and m.css" OFF)
if(BUILD_MCSS_DOCS)
  include(cmake/docs.cmake)
endif()

option(ENABLE_COVERAGE "Enable coverage support separate from CTest's" OFF)
if(ENABLE_COVERAGE)
  include(cmake/coverage.cmake)
endif()

include(cmake/lint-targets.cmake)
include(cmake/spell-targets.cmake)

add_folders(Project)
