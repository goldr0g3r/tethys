if(PROJECT_IS_TOP_LEVEL)
  set(
      CMAKE_INSTALL_INCLUDEDIR "include/slave-${PROJECT_VERSION}"
      CACHE STRING ""
  )
  set_property(CACHE CMAKE_INSTALL_INCLUDEDIR PROPERTY TYPE PATH)
endif()

include(CMakePackageConfigHelpers)
include(GNUInstallDirs)

# find_package(<package>) call for consumers to find this project
set(package slave)

install(
    DIRECTORY
    include/
    "${PROJECT_BINARY_DIR}/export/"
    DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
    COMPONENT slave_Development
)

install(
    TARGETS slave_slave
    EXPORT slaveTargets
    RUNTIME #
    COMPONENT slave_Runtime
    LIBRARY #
    COMPONENT slave_Runtime
    NAMELINK_COMPONENT slave_Development
    ARCHIVE #
    COMPONENT slave_Development
    INCLUDES #
    DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
)

write_basic_package_version_file(
    "${package}ConfigVersion.cmake"
    COMPATIBILITY SameMajorVersion
)

# Allow package maintainers to freely override the path for the configs
set(
    slave_INSTALL_CMAKEDIR "${CMAKE_INSTALL_LIBDIR}/cmake/${package}"
    CACHE STRING "CMake package config location relative to the install prefix"
)
set_property(CACHE slave_INSTALL_CMAKEDIR PROPERTY TYPE PATH)
mark_as_advanced(slave_INSTALL_CMAKEDIR)

install(
    FILES cmake/install-config.cmake
    DESTINATION "${slave_INSTALL_CMAKEDIR}"
    RENAME "${package}Config.cmake"
    COMPONENT slave_Development
)

install(
    FILES "${PROJECT_BINARY_DIR}/${package}ConfigVersion.cmake"
    DESTINATION "${slave_INSTALL_CMAKEDIR}"
    COMPONENT slave_Development
)

install(
    EXPORT slaveTargets
    NAMESPACE slave::
    DESTINATION "${slave_INSTALL_CMAKEDIR}"
    COMPONENT slave_Development
)

if(PROJECT_IS_TOP_LEVEL)
  include(CPack)
endif()
