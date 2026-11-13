# Keyboard PCB: order sheet (robu.in)

Board: **Pico COMP keyboard v1.0**. KiCad DRC 0 errors, ERC 0, schematic parity OK (`reports/`).

## 1. PCB fabrication

Upload **`hardware/fab/keyboard-gerbers.zip`** (74 KB; robu.in accepts .zip/.rar up to 100 MB). It holds
all copper, mask, silk and paste layers, the edge cuts, PTH + NPTH drill files and the IPC-356 netlist.

| Option | Choose |
|---|---|
| Layers | **2** |
| Dimensions | **244.1 x 120.1 mm** (single board, no panel) |
| Quantity | 5 (usual minimum; you need 1) |
| Material | FR-4, TG 130-150 (standard) |
| Thickness | **1.6 mm** |
| Copper weight | **1 oz** outer |
| Surface finish | **HASL lead-free** (ENIG is fine too, slightly dearer) |
| Solder mask | any colour (black looks best under cream keycaps; green is cheapest) |
| Silkscreen | white |
| Min track / spacing | **0.25 mm / 0.2 mm** (10 / 8 mil): standard capability |
| Min hole | **0.3 mm** (vias 0.6 / 0.3 mm); largest 3.4 mm |
| Via covering | tented |
| Internal cut-outs | **yes**: two 7.8 x 8.0 mm rectangular cut-outs per stabilizer (4 in total), routed by the fab |
| Castellated holes / impedance / gold fingers | no |
| Electrical test | yes (if offered) |

## 2. SMT assembly: diodes only, bottom side

Ask for **single-sided SMT assembly, BOTTOM side**, with these files:
- BOM: `assembly/keyboard-bom.csv`: assemble **only D1-D75** (75 x 1N4148W-7-F, SOD-123).
- Pick-and-place: `assembly/keyboard-cpl.csv` (78 rows: 75 diodes + 3 fiducials, all `bottom`).
- Drawings: `assembly/keyboard-assembly-bottom.pdf`.

**Do NOT let them fit the switches, stabilizers or header (mark them DNP / "do not assemble").**
Choc switches are plate-mounted: the switches clip into the plate first, then the plate + switches
are soldered to the PCB together. Factory-soldered switches can't take the plate afterwards.

## 3. Switch plate (laser cut)

Upload **`keyboard-plate.dxf`**: 244 x 108 mm, R4 corners, 75 switch cut-outs 13.8 x 13.8 mm, 4
stabilizer cut-outs 6.30 x 6.60 mm. Units mm.

| Option | Choose |
|---|---|
| Material | aluminium 5052 or stainless steel, or FR-4 (plates are also commonly ordered as a blank PCB) |
| Thickness | **1.2 mm** (Kailh spec; anything 1.2-1.3 mm works) |
| Finish | anodised / powder-coated black (optional) |

## 4. Parts to buy separately (you fit these)

| Qty | Part |
|---|---|
| 75 (+5 spare) | Kailh Choc V1 switches, CPG135001D01 (red, linear) or any PG1350 Choc V1 |
| 1 | Kailh PG1350 (Choc) plate-mount stabilizer **2U** kit (Shift) |
| 1 | Kailh PG1350 (Choc) plate-mount stabilizer **6.25U** kit (76 mm wire, used on the 6u Space) |
| 1 | 1x20 pin header, 2.54 mm, right-angle |
| 1 | 20-way 2.54 mm female-female jumper bundle, ~10 cm (keyboard J1 to main board J11) |
| 3 | M2 x 30 pan-head screws (case: post, PCB, deck) |

## 5. Assembly at home (after the boards arrive)
1. Clip the two stabilizers into the plate (wire side down, toward the PCB).
2. Clip all 75 switches into the plate from the top, pins pointing down.
3. Lower the plate + switches onto the PCB (diodes underneath), so every switch pin goes through its hole.
4. Solder the 150 switch pins and the 20 header pins from the bottom.
5. Test each key before fitting the keycaps (`hardware/mechanical/keycaps/`).
