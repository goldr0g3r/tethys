cmake_minimum_required(VERSION 3.14)

project(slaveTests LANGUAGES C)

include(../cmake/project-is-top-level.cmake)
include(../cmake/folders.cmake)

# ---- Dependencies ----

if(PROJECT_IS_TOP_LEVEL)
  find_package(slave REQUIRED)
  enable_testing()
endif()

# ---- Tests ----

add_executable(slave_test source/slave_test.c)
target_link_libraries(slave_test PRIVATE slave::slave)
target_compile_features(slave_test PRIVATE c_std_11)

add_test(NAME slave_test COMMAND slave_test)

# ---- End-of-file commands ----

add_folders(Test)
