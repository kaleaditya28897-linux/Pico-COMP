# Hardware plan

## KiCad (`hardware/kicad/`)
Planned sheets, in order:
1. Power: USB-C (PD sink/CC), 18650 pack + protection/charger, 3.3 V and 5 V rails, fuel gauge.
2. MCU2 (NET): RP2350, Wi-Fi radio, keyboard matrix, power-gating for MCU1.
3. MCU1 (UI): RP2350, HSTX -> DVI/HDMI connector for the 10.1" 1024x600 Waveshare display, SD card, USB host (printer), expansion port, beeper, RTC.
4. Inter-MCU UART + shared SWD/boot access.

## FreeCAD (`hardware/mechanical/`)
Case for the 10" panel, 4x18650 holders, keyboard plate with arrow keys, and the hotkey sticker area at the base of the screen.

## Power (custom 2S2P pack)
- Pack: custom-made, 4x 18650 as 2S2P (7.4 V nominal, 6.0-8.4 V). The four cells lie side by side in a single flat layer, about 77 x 68 x 20 mm (a 2x2 stack would be 37 mm tall and does not fit the 26 mm base). Spec to the pack maker: balancing BMS with over/under-voltage, over-current, short-circuit and NTC temperature protection, matched branded cells, a keyed connector, and ideally an SMBus fuel gauge. The display is 5 V, so a 2S pack feeds an efficient buck converter; 4S is no longer needed.

### Pack order sheet
| Item | Value |
|------|-------|
| Configuration | 2S2P, 4x 18650 Li-ion (NMC), branded matched cells |
| Capacity | 6000 mAh (2x 3000 mAh cells; 5000 mAh if 2500 mAh cells) = 44.4 Wh |
| Nominal voltage | 7.4 V (full 8.4 V, cut-off 6.0 V) |
| Continuous discharge | 2 A |
| Peak discharge | 4 A (BMS over-current trip about 6 A) |
| Charge current | 2 A standard, 3 A max (charging is done by the mainboard) |
| Typical load | ~0.6 A at 7.4 V (about 4 W: display 3.1 W, MCUs/Wi-Fi/SD ~1 W) |
| Power connector | XT30 (pack leads female, mainboard XT30PW male) |
| Optional signal connector | JST-PH 2-pin for a 10k NTC (thermistor) |
| Size | cells 77 x 68 x 20 mm; with BMS about 77 x 78 x 20 mm max |
| Leads | 100 mm, 18 AWG, silicone insulated |
| Protection | over/under-voltage, over-current, short-circuit, temperature, cell balancing |
- Chemistry: Li-ion (NMC/NCA) 18650, not LiFePO4. LFP cells give ~30% less energy per cell, and a 2S LFP pack (5.0-7.3 V) sits right at the 5 V rail and would need a buck-boost; matching LFP voltage would take 3S (6 cells). Prefer protected-pack cells of 2500-3500 mAh instead of 1800 mAh: 4x3000 mAh is ~43 Wh, about 1.6x the battery life.
- Charger: 2S-capable USB-C buck charger with power path on the NET MCU (e.g. TI BQ25792/BQ25798 family, or a simpler 2S part). Candidate; verify availability in India.
- Rails from the pack: 5 V 3 A buck (display 0.62 A, USB host, SD), 3.3 V for the MCUs and CYW43439. Gate the 5 V display rail from the NET MCU for standby.

## Keyboard (`hardware/keyboard/`)
Mini-laptop form factor: the keyboard is as wide as the display module plus bezels, with the 4x18650 bay under the keys.
- Switches: Kailh Choc V1 low profile, 17 mm pitch both axes, 6 rows x 14u = 238 x 102 mm key area, 244 x 108 mm plate. Display: 7" 1024x600 HDMI LCD, 164.9 x 124.27 mm (vendor spec), instead of the 10.1" panel. The keyboard stays full size, so the base and lid keep the 250 x 140 mm footprint with larger bezels around the smaller screen.
- 75 keys: F-row, full number row, QWERTY, Ctrl/Fn/Alt/Space, and an inverted-T arrow cluster (Up in the Shift row above Down; Left/Down/Right in the bottom row) as the only navigation. Extra hotkeys use an Fn layer; labels go on the sticker under the screen.
- Matrix: 6 rows x 14 columns, diodes per key, scanned by the NET MCU. That is 20 GPIOs, plus CYW43 (4), UART link, I2C, so consider the RP2350B (48 GPIO) for NET or a shift-register/expander for the columns.
- `layout.py` generates `plate.dxf` (cutouts 13.8 mm) and `matrix.csv` (key positions, row/col). `gen_pcb.py` turns the layout into `hardware/kicad/keyboard.kicad_pcb` (75 Choc footprints + diodes + 1x20 header, nets assigned, **tracks not routed yet**; 0 DRC violations, ratsnest only). `hardware/mechanical/case.py` (run with `FreeCADCmd`) builds the parametric case (base, key plate, lid, panel and cell placeholders) to `pico-comp.FCStd`/`.step`; closed stack is about 250 x 140 x 47 mm. Panel size, thickness and visible area in `case.py` are guesses to measure.

## Next steps
- Verify the display kit's exact outline, mounting holes, connector and input timing, then size the case around it.
- Import `hardware/keyboard/plate.dxf` into FreeCAD for the plate/case; place switches in KiCad from `matrix.csv`.
- Create the KiCad project `hardware/kicad/pico-comp.kicad_pro` and start with the power sheet.

## Manufacturing (robu.in)
Confirmed by phone with robu.in: they can fabricate PCBs, do SMT assembly with parts sourced by them (turnkey), and also offer 3D printing, CNC/laser cutting and custom Li-ion packs.

Plan:
- Keyboard PCB (`hardware/kicad/keyboard.kicad_pcb`) and main board: fab + turnkey assembly. Provide Gerbers, BOM and pick-and-place from KiCad; they source the chips (RP2350, CYW43439/RM2, charger, regulators).
- Switch plate (`hardware/keyboard/plate.dxf`): laser/CNC cut.
- Case (`hardware/mechanical/pico-comp.step`): 3D print or CNC.
- Battery: 2S2P 18650 pack per the order sheet above.
- Max board size: up to E-ATX (about 305 x 330 mm), so the 244x120 mm keyboard PCB fits as a single board, with room to put the main board on the same PCB.
- Still to ask: min trace/space, stock/lead time for RP2350 and the wireless module, hotswap socket availability.

## Wi-Fi antenna
Use a Wi-Fi module with a U.FL connector and a 2.4 GHz stick-on flex antenna in the lid's right bezel, beside (never behind) the metal-framed panel. `case.py` models a 34x12x4 mm rib pocket under the top skin with a 3 mm coax channel through the rear wall toward the hinge; the 30x8x1 mm antenna size is an assumption, so match it to the real part. Keep it away from the HDMI/DVI cable and the panel driver board.

## Viewing the assembly
`FreeCADCmd hardware/mechanical/case.py && python3 hardware/mechanical/build_viewer.py`, then open `hardware/mechanical/pico-comp-viewer.html` in a browser (offline, orbit/zoom, per-part toggles). It shows the lid open at 80 degrees with keycaps, plate, keyboard PCB, main PCB placeholder, cells, hinge, display and antenna. Placeholder parts are for visualisation only.

## PCBs (KiCad 10, generated)

There is **no schematic**: both boards are generated from Python (`hardware/mainboard/gen_pcb.py`, `hardware/keyboard/gen_pcb.py`) and autorouted with Freerouting 2.1 (needs Java 21) via `hardware/mainboard/route.py`; `ses_import.py` loads its result because pcbnew's own SES importer rejects it.

- **Keyboard PCB** (244x120 mm, 2 layers, 75 Choc + diodes, 4 mounting holes): fully routed, DRC clean.
- **Main PCB** (152x68 mm, 4 layers): 2x RP2350A + flash, BQ25798 charger, 5 V / 3.3 V bucks, USB-C, microSD, HDMI, keyboard/printer/expansion headers. Routed except **38 unconnected items** (mostly V3V3/VBUS/VSYS/VBAT power connections) that must be finished by hand in KiCad. Courtyard DRC is clean.
- **Not verified**: the Wi-Fi module footprint is a placeholder (replace with the real Murata footprint); BQ25798/TPS62933 passive values need datasheet review; robu.in's min trace/space and 4-layer rules are unconfirmed.
- GPIO plan: NET MCU ROW0-5 = GPIO0-5, COL0-13 = GPIO6-19, I2C 20/21, CHG_INT 22, Wi-Fi 23-26, CHG_STAT 27, UART 28/29. UI MCU printer UART 0-3, EXP 4-11, HSTX TMDS 12-19, SD SPI 20-23, SD_DET 24, LED 25, buzzer 26, UART 28/29.
- Regenerate 3D: `kicad-cli pcb export step --subst-models --force -o X.step X.kicad_pcb` in `hardware/kicad`, then `FreeCADCmd hardware/mechanical/case.py` (imports both STEPs) and `build_viewer.py`.
