cmake_minimum_required(VERSION 3.13)

# All firmware targets the RP2350 RISC-V (Hazard3) cores; ARM is not used.
if(NOT PICO_PLATFORM)
    set(PICO_PLATFORM rp2350-riscv)
endif()

include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)

# CXX/ASM are enabled only because the Pico SDK requires them; project code is C.
project(pico_comp C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

pico_sdk_init()

add_subdirectory(firmware/common)
add_subdirectory(firmware/ui)
add_subdirectory(firmware/net)
