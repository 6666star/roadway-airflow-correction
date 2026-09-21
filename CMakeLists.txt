cmake_minimum_required(VERSION 3.20)
project(airflow_correction_backend VERSION 2.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(airflow_core
    src/geometry.cpp
    src/radial.cpp
    src/repository.cpp
    src/models.cpp
    src/service.cpp
)

target_include_directories(airflow_core PUBLIC include)

if(MSVC)
    target_compile_options(airflow_core PRIVATE /W4 /permissive-)
else()
    target_compile_options(airflow_core PRIVATE -Wall -Wextra -Wpedantic)
endif()

add_executable(airflow_cli src/main.cpp)
target_link_libraries(airflow_cli PRIVATE airflow_core)

# Keep the MinGW release executable portable when launched from a regular
# Windows terminal that does not have the MSYS2 runtime directories on PATH.
if(MINGW)
    target_link_options(airflow_cli PRIVATE -static -static-libgcc -static-libstdc++)
endif()

enable_testing()
add_executable(radial_geometry_tests tests/test_radial.cpp)
target_link_libraries(radial_geometry_tests PRIVATE airflow_core)
if(MINGW)
    target_link_options(radial_geometry_tests PRIVATE -static -static-libgcc -static-libstdc++)
endif()
add_test(NAME radial_geometry_validation COMMAND radial_geometry_tests)
find_package(Python3 COMPONENTS Interpreter)
if(Python3_Interpreter_FOUND)
    add_test(NAME radial_rpc_validation
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/tests/test_radial_rpc.py
                --exe $<TARGET_FILE:airflow_cli>)
    add_test(
        NAME python_model_validation
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/tests/test_models.py
                --exe $<TARGET_FILE:airflow_cli>
    )
    add_test(
        NAME grpc_end_to_end_validation
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/tests/test_grpc_integration.py
                --exe $<TARGET_FILE:airflow_cli>
    )
endif()
