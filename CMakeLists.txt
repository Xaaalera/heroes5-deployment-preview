cmake_minimum_required(VERSION 3.21)
project(WorkshopDeploymentPreview LANGUAGES CXX)

if(NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 4)
    message(FATAL_ERROR "WorkshopDeploymentPreview requires MSVC targeting x86.")
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

add_library(workshop_deployment_preview SHARED src/preview_plugin.cpp)
target_link_libraries(workshop_deployment_preview PRIVATE user32)
set_target_properties(workshop_deployment_preview PROPERTIES OUTPUT_NAME "WorkshopDeploymentPreview")

add_executable(workshop_preview_loader src/preview_loader.cpp)
target_include_directories(workshop_preview_loader PRIVATE devkit/native)
target_link_libraries(workshop_preview_loader PRIVATE bcrypt comdlg32 user32)
target_compile_definitions(workshop_preview_loader PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX)

install(TARGETS workshop_deployment_preview workshop_preview_loader
        RUNTIME DESTINATION . LIBRARY DESTINATION .)
