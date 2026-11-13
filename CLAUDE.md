# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Pico-COMP is a text-only, battery-powered portable inspired by the TRS-80 Model 100, built on two RP2350 microcontrollers. Goals are in `intent.md`; design in `docs/architecture.md` and `docs/hardware-plan.md`. `.github/copilot-instructions.md` holds the full planned feature list and conventions.

## Firmware

- Build both targets: `./build.sh` (outputs `build/firmware/ui/comp_ui.uf2` and `build/firmware/net/comp_net.uf2`).
- Single target after the first configure: `cmake --build build --target comp_ui` (or `comp_net`).
- Needs the Pico SDK (`PICO_SDK_PATH`, default `~/pico-sdk`) and the RISC-V toolchain (`RISCV_TC`, default `~/toolchains/riscv`).
- Platform is always `rp2350-riscv` (Hazard3 cores); the ARM cores are not used.
- There are no tests or linter yet.

Rules:
- **C only (C11, Pico SDK + CMake).** Don't introduce C++, MicroPython or other languages in firmware. The root `CMakeLists.txt` enables CXX/ASM only because the SDK requires them.
- Memory and power are tight: avoid heavy dependencies and dynamic allocation where practical; favour sleep, minimal redraws, and Wi-Fi only when needed.
- UI is text-mode and keyboard-only (arrow keys + hotkeys, no pointer/touch). Keep hotkey assignments centrally defined so the printed hotkey sticker can stay in sync.

Architecture (two-MCU split):
- **UI MCU** (`firmware/ui`): DVI display over HSTX, all apps, SD, printer/USB host, beeper.
- **NET MCU** (`firmware/net`, currently a stub): Wi-Fi (Raspberry Pi RM2 / CYW43439 over PIO gSPI, clock on GPIO26 rather than the Pico 2 W's 29), BQ25798 charger over I2C, keyboard matrix scan. It forwards key events to UI. The UI MCU switches the panel's 5 V (TPS22917, GPIO27) for standby.
- The MCUs talk over UART with framed packets `[0xA5][type][len][payload][crc8]` defined in `firmware/common/link.h` (`comp_common` is a header-only INTERFACE library).
- GPIO map for both MCUs: `firmware/common/pins.h` (must match `hardware/mainboard/gen_pcb.py`). UART0 is the MCU link on GPIO28/29, so the UI's printer port is UART1 on GPIO4-7.

Display driver (`firmware/ui/dvi_text.{c,h}`): 640x480@60, 80x30 cells, 8x16 font. Scanlines are rendered from a cell buffer inside the DMA IRQ (no framebuffer); colour schemes (amber/green/white) use a 16-step intensity ramp. Untested on hardware. 720x400 (80x25, 9x16 font) is the planned primary mode and needs PLL/sys-clock changes. The panel is a 7" 1024x600 HDMI LCD whose scaler fills the screen (HSTX can't drive 1024x600 directly).

`firmware/ui/font8x16.c` is generated from Terminus (CP437 order) by `tools/psf2c.py <font.psf.gz> <out.c>`. Don't hand-edit it.

## Hardware (generated: edit the Python, then regenerate)

Nothing under `hardware/` is drawn by hand. Each board is a KiCad 10 project in `hardware/kicad/` with a **generated schematic** and PCB; the case, plate and keycaps come from FreeCAD scripts. Don't hand-edit any generated file (`*.kicad_pcb`, `*.kicad_sch`, `pico-comp.pretty/`, `pico-comp.kicad_sym`, `*.json`, `plate.dxf`, `matrix.csv`, STEP/STL, `print/`, `keycaps/`, `hardware/fab/`, `pico-comp-viewer.html`, `docs/case-dimensions.md`). The full regeneration order is at the end of `docs/hardware-plan.md`.

How it fits together:
- `hardware/keyboard/layout.py` is the single source for key positions (plate, keyboard PCB, case, keycaps).
- `hardware/placement.py` says where both boards sit in the case. It's shared by `keyboard/gen_pcb.py` (RF keep-out above the RM2 antenna) and `mechanical/case.py`.
- `mainboard/gen_pcb.py` holds the whole mainboard netlist and placement. IC pins are mapped by symbol pin name (`symlib.py` reads the KiCad symbol libs). It also writes `kicad/mainboard.json` (connector boxes, holes, RF keep-out, symbol choices), which `gen_sch.py`, the keyboard generator and `case.py` read.
- `gen_sch.py` (one per board) builds the schematic from the generated PCB with `kicad/kisch.py`: a library symbol per footprint, global labels at the pin tips, no-connect flags, PWR_FLAGs. It then links the footprints to their symbols, so ERC and schematic-parity DRC must stay at 0. After any netlist change, rerun `gen_pcb.py`, then `gen_sch.py`, then `route.py`.
- `kicad/fplib.py` makes project copies of library footprints that need our STEP model (`kicad/make_3d.py`, FreeCAD) or trimmed silk. `kicad/make_footprints.py` writes the RM2 and Choc footprints.
- `mainboard/route.py <board> [passes]` runs Freerouting 2.1 (Java 21, `JAVA21`, `FREEROUTING_JAR`), imports the session with `ses_import.py` (pcbnew's importer rejects Freerouting 2.x), removes dangling stubs and refills zones. Mainboard power nets are 0.25 mm traces plus F.Cu pours, because the BQ25798's 0.2 mm pads at 0.4 mm pitch can't take wider traces.
- `sh hardware/kicad/fab.sh`: gate (ERC errors, DRC incl. parity) and then Gerbers, drill, pick-and-place, BOM (MPN/Spec fields), IPC-356, ODB++, schematic and assembly PDFs and STEP, written to `hardware/fab/`.
- `python3 hardware/kicad/export_parts.py`, then `FreeCADCmd hardware/mechanical/case.py`: the full assembly, with every component as its own grouped object (`pcb3d.py` places each KiCad model). It writes `print/`, `keycaps/` (`keycaps.py`: Choc V1 stems, debossed legends + inlays), `assembly.json` and `docs/case-dimensions.md`, and prints an interference report. `FreeCAD hardware/mechanical/open_gui.py` opens it; `build_viewer.py` makes the offline HTML viewer.
- Run DRC/ERC yourself with `kicad-cli pcb drc --schematic-parity --refill-zones` and `kicad-cli sch erc` from `hardware/kicad`.

**Main board is hand-routed in KiCad** (`docs/mainboard-routing.md`): Freerouting couldn't finish it with
intact planes. `mainboard/gen_pcb.py` refuses to overwrite a board that has tracks, so make main-board
netlist changes in KiCad (schematic, then Update PCB from Schematic). The keyboard is still fully
script-generated and auto-routed.

Design constraints worth knowing: the RM2 antenna end must stay flush with the mainboard's front edge, under plastic (palm rest), with no copper in either keep-out. The switch stack-up (plate 1.2 mm, 2.2 mm above the PCB) and the Kailh PG1350 stabilizers come from Kailh's drawings (sources in `docs/hardware-plan.md`). Panel thickness and the HDMI cable are still unmeasured.
