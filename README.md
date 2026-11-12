# Pico-COMP

A modern analog of the TRS-80 Model 100. See `intent.md` for goals, `docs/architecture.md` and `docs/hardware-plan.md` for design.

## Firmware build
Run `./build.sh` (both MCUs use the RP2350 RISC-V Hazard3 cores). Needs the Pico SDK (`PICO_SDK_PATH`, default `~/pico-sdk`) and the RISC-V toolchain (`RISCV_TC`, default `~/toolchains/riscv`).
Outputs `build/firmware/ui/comp_ui.uf2` and `build/firmware/net/comp_net.uf2`.

## Status
- Firmware: both MCUs build (RISC-V). UI MCU has an HSTX DVI text driver (untested on hardware); NET MCU is a stub.
- Hardware: keyboard PCB generated (unrouted), 7" display, 2S2P Li-ion pack, Wi-Fi antenna in the lid bezel. Fab/assembly via robu.in (see `docs/hardware-plan.md`).
- Case: `hardware/mechanical/case.py` -> STEP + `pico-comp-viewer.html` (open in a browser).
- Not done: main-board schematic, keyboard routing, key scanner, UART link, apps, hinge design.
