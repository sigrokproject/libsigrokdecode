find_package(Check REQUIRED)

add_executable(MainTest main.c
    core.c
    decoder.c
    inst.c
    session.c
)
target_link_libraries(MainTest sigrokdecode check)
target_link_libraries(MainTest ${GLIB_LIBRARIES})
target_include_directories(MainTest PRIVATE ${GLIB_INCLUDE_DIRS})
target_include_directories(MainTest PRIVATE ${CMAKE_BINARY_DIR}) # config.h / version.h

target_compile_definitions(MainTest PRIVATE "-DDECODERS_TESTDIR=\"${CMAKE_SOURCE_DIR}/decoders\"")

add_test(NAME MainTest COMMAND MainTest)


