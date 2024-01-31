cmake_minimum_required(VERSION 3.23) # file_set needs at least 3.23
project(libsigrokdecode LANGUAGES C
    VERSION 0.6.0
    HOMEPAGE_URL "http://www.sigrok.org"
)

set(CMAKE_C_STANDARD 99)

set(PROJECT_BUG_URL "sigrok-devel@lists.sourceforge.net")
set(PROJECT_PACKAGE_STRING "${PROJECT_NAME} ${PROJECT_VERSION}")

set(SR_LIB_VERSION_MAJOR 4)
set(SR_LIB_VERSION_MINOR 0)
set(SR_LIB_VERSION_PATCH 0)
set(CONF_HOST "${CMAKE_SYSTEM_PROCESSOR}-${CMAKE_SYSTEM_NAME}-${CMAKE_SYSTEM_VERSION}")

execute_process(
        COMMAND git log -1 --format=%h
        WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
        OUTPUT_VARIABLE GIT_HASH
        OUTPUT_STRIP_TRAILING_WHITESPACE
        )

include(CheckIncludeFile)
# Check for the existence of the header files
check_include_file("inttypes.h" HAVE_INTTYPES_H)
check_include_file("stdint.h" HAVE_STDINT_H)
check_include_file("stdio.h" HAVE_STDIO_H)
check_include_file("stdlib.h" HAVE_STDLIB_H)
check_include_file("strings.h" HAVE_STRINGS_H)
check_include_file("string.h" HAVE_STRING_H)
check_include_file("sys/stat.h" HAVE_SYS_STAT_H)
check_include_file("sys/types.h" HAVE_SYS_TYPES_H)
check_include_file("unistd.h" HAVE_UNISTD_H)
check_include_file("dlfcn.h" HAVE_DLFCN_H)

configure_file(cmake/config.h.in config.h)
configure_file(cmake/version.h.in version.h)

# Source files
set(LIBSIGROKDECODE_SOURCES
    srd.c
    session.c
    decoder.c
    instance.c
    log.c
    util.c
    exception.c
    module_sigrokdecode.c
    type_decoder.c
    error.c
    version.c
)

# Additional headers
set(LIBSIGROKDECODE_HEADERS
    libsigrokdecode-internal.h
)

# Check for Python
find_package(Python3 COMPONENTS Interpreter Development REQUIRED)

# Check for glib-2.0
find_package(PkgConfig REQUIRED)
pkg_check_modules(GLIB REQUIRED glib-2.0>=2.3.4)

# Check for Check (optional)
option(ENABLE_TESTS "Build with tests" ON)
if(ENABLE_TESTS)
    enable_testing(true) # must be in the root file!
    add_subdirectory(tests)
endif()

# Check for IRMP (optional)
option(WITH_IRMP "Enable IRMP support" ON)
if(WITH_IRMP)
    pkg_check_modules(LIBIRMP REQUIRED)
endif()

# Set compiler flags
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall -Wextra -Wmissing-prototypes -Wshadow -Wformat=2 -Wno-format-nonliteral -Wfloat-equal")
if(WITH_IRMP)
    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -DWITH_IRMP")
endif()

# Build the library
add_library(sigrokdecode SHARED ${LIBSIGROKDECODE_SOURCES} ${LIBSIGROKDECODE_HEADERS})
target_link_libraries(sigrokdecode ${GLIB_LIBRARIES} ${LIBIRMP_LIBRARIES} ${Python3_LIBRARIES})
target_include_directories(sigrokdecode PRIVATE ${PROJECT_BINARY_DIR} ${GLIB_INCLUDE_DIRS} ${LIBIRMP_INCLUDE_DIRS}) # for config.h
target_include_directories(sigrokdecode PUBLIC ${Python3_INCLUDE_DIRS}) # TODO: why this must be PUBLIC?
target_include_directories(sigrokdecode PUBLIC ${PROJECT_SOURCE_DIR})
target_sources(sigrokdecode PUBLIC
    FILE_SET HEADERS
    BASE_DIRS ${PROJECT_BINARY_DIR} ${PROJECT_SOURCE_DIR}
    TYPE HEADERS
    FILES ${PROJECT_BINARY_DIR}/version.h libsigrokdecode.h)

# Install rules
install(TARGETS sigrokdecode DESTINATION lib)
install(TARGETS sigrokdecode FILE_SET HEADERS)

# Autotools-like configuration summary
message(STATUS "libsigrokdecode configuration summary:")
message(STATUS " - Package version................. ${PROJECT_VERSION}")
message(STATUS " - Library ABI version............. ${SR_LIB_VERSION_MAJOR}:${SR_LIB_VERSION_MINOR}:${SR_LIB_VERSION_PATCH}")
message(STATUS " - Prefix.......................... ${CMAKE_INSTALL_PREFIX}")
message(STATUS " - Building as..................... ${CMAKE_BUILD_TYPE}")
message(STATUS " - Building for.................... ${CONF_HOST}")
#message(STATUS " - Building shared / static........ ON / OFF")

# Display additional configuration information
message(STATUS "Compile configuration:")
message(STATUS " - C compiler...................... ${CMAKE_C_COMPILER}")
message(STATUS " - C compiler version.............. ${CMAKE_C_COMPILER_VERSION}")
message(STATUS " - C compiler flags................ ${CMAKE_C_FLAGS}")
message(STATUS "Detected libraries (required):")
message(STATUS " - glib-2.0........................ ${GLIB_VERSION}")
if(WITH_IRMP)
    message(STATUS " - IRMP support library............ ${LIBIRMP_VERSION}")
endif()

if(WITH_CHECK)
    message(STATUS "Optional features:")
    message(STATUS "  - Check unit testing framework... ENABLED")
endif()

