cmake_minimum_required(VERSION 3.21)
project(WorkshopDeploymentPreview LANGUAGES CXX)

if(NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 4)
    message(FATAL_ERROR "WorkshopDeploymentPreview requires MSVC targeting x86.")
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

option(H5_PREVIEW_MANAGED_SDK "Build the predictor with the managed xkit plugin contract" ON)

if(H5_PREVIEW_MANAGED_SDK)
    # Use the same player integration as xkit release, rather than installing
    # the raw HMR payload. Exclude unrelated SDK install rules and test targets.
    add_subdirectory(devkit/native sdk-runtime EXCLUDE_FROM_ALL)
    set(SDK_INCLUDE_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/devkit/native")
    set(SDK_PLUGIN_SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/src/preview_sdk.cpp")
    include("${SDK_INCLUDE_DIRECTORY}/player_plugin.cmake")
    set_target_properties(heroes5_plugin_release PROPERTIES OUTPUT_NAME "WorkshopDeploymentPreview")
    add_custom_target(workshop_deployment_preview ALL
        DEPENDS heroes5_plugin_release heroes5_mod_loader xkit_graphics_proxy)
    install(TARGETS heroes5_plugin_release RUNTIME DESTINATION bin/Heroes5Mods/Plugins)
    install(TARGETS heroes5_mod_loader xkit_graphics_proxy RUNTIME DESTINATION bin)
else()
    add_library(workshop_deployment_preview SHARED src/preview_plugin.cpp)
    target_link_libraries(workshop_deployment_preview PRIVATE user32)
    set_target_properties(workshop_deployment_preview PROPERTIES OUTPUT_NAME "WorkshopDeploymentPreview")

add_executable(workshop_preview_loader src/preview_loader.cpp)
target_include_directories(workshop_preview_loader PRIVATE devkit/native)
target_link_libraries(workshop_preview_loader PRIVATE bcrypt comdlg32 user32)
target_compile_definitions(workshop_preview_loader PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX)

install(TARGETS workshop_deployment_preview RUNTIME DESTINATION bin/Heroes5Mods)
install(TARGETS workshop_preview_loader RUNTIME DESTINATION tools
        COMPONENT Diagnostics EXCLUDE_FROM_ALL)
endif()
