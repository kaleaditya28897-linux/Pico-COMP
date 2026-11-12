#!/bin/sh
# Builds comp_ui and comp_net for the RP2350 RISC-V (Hazard3) cores.
set -e
export PICO_SDK_PATH="${PICO_SDK_PATH:-$HOME/pico-sdk}"
export PICO_TOOLCHAIN_PATH="${RISCV_TC:-$HOME/toolchains/riscv}"

cmake -S . -B build -DPICO_PLATFORM=rp2350-riscv -DPICO_COMPILER=pico_riscv_gcc
cmake --build build -j"$(nproc)"
