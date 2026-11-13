# Main board: order sheet (robu.in)

Board: **Pico COMP main board v1.0**. KiCad ERC 0, DRC 0 (errors and warnings, schematic parity) and the
power-copper audit pass (`reports/`, `hardware/mainboard/check_power.py`).

## 1. PCB fabrication

Upload **`hardware/fab/mainboard-gerbers.zip`**: all six copper layers, mask, silk, paste, edge cuts, PTH +
NPTH drill files and the IPC-356 netlist. ODB++ (`mainboard-odb.zip`) and IPC-2581 are in this folder too.

| Option | Choose |
|---|---|
| Layers | **6** |
| Stack-up | F.Cu signal / In1 GND plane / In2 signal / In3 signal / In4 3.3 V plane / B.Cu signal + GND |
| Dimensions | **152.1 x 84.1 mm** (single board) |
| Quantity | 5 (usual minimum) |
| Material | FR-4, TG 150-170 |
| Thickness | **1.6 mm** |
| Copper | **1 oz outer, 0.5 oz inner** (standard) |
| Min track / spacing | **0.127 / 0.127 mm** (5 / 5 mil) |
| Vias | 0.45 / 0.2 mm (442), 0.6 / 0.3 mm (16), 0.6 / 0.25 mm (8), **0.35 / 0.15 mm (31, see below)** |
| Min annular ring | 0.1 mm |
| **Via in pad** | **Yes: resin-filled and capped (POFV / VIPPO).** 30 vias sit in the pads of the 0.5 mm-pitch eMMC BGA (U12); the QFN thermal pads (U1, U2) also have via grids. Without filling, solder wicks into the vias. |
| Surface finish | **ENIG** (fine-pitch BGA/QFN; HASL is not flat enough) |
| Solder mask | any colour; mask between the 0.4 mm-pitch QFN pads (mask dams) |
| Silkscreen | white |
| Impedance control | optional: USB 90 ohm diff (0.162 / 0.2 mm), TMDS 100 ohm diff (0.132 / 0.2 mm) on F.Cu over In1 |
| Electrical test | yes |

## 2. Assembly (turnkey, single sided: all parts on the top)

- BOM: `assembly/mainboard-bom.csv` (71 lines, 167 parts; MPN or full spec on every line).
- Pick-and-place: `assembly/mainboard-cpl.csv` (SMD) and `assembly/mainboard-cpl-incl-tht.csv` (with THT).
- Drawings: `assembly/mainboard-assembly-top.pdf`, schematic `mainboard-schematic.pdf`.
- THT parts (selective / hand soldering): J1, J14 (USB-C shell legs), J2 (XT30 battery), J5, J7, J8 (JST-PH),
  J6 (HDMI shell legs), J11 (1x20 keyboard header, right angle), J13 (1x10 expansion header).

Notes for the assembler:
- **L1, L2 (Abracon AOTA-B201610S3R3-101-T): polarity matters.** The reel is aligned; the part's dot goes
  to **pad 1, marked by the silkscreen dot** (the 1V1 side). This is the RP2350 core-regulator inductor;
  Raspberry Pi's layout only behaves with this orientation.
- U12 (64 GB eMMC, LFBGA-153) needs X-ray inspection after reflow.
- C120/C121/C220/C221/C125/C225: 4.7 uF 0402, Murata GRM155R60J475ME47D (the RP2350 reference part).
- Q50 (CSD17581Q3A) is the battery ship FET: pins 1-3 source, 4 gate, the large tab is the drain.

## 3. Battery and other parts

See `hardware/fab/ORDER-CHECKLIST.md` (2S2P 18650 pack with XT30, display, keyboard, case printing).
