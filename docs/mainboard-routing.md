# Routing the main board

The main board is generated and routed by scripts; the full pipeline is in `CLAUDE.md` ("Main board
pipeline"): `gen_pcb.py` (placement + recipe copper + power pours + VBUS trunk) -> `fanout.py` ->
`route.py` race -> `maze_route.py` / `route_from.py` for leftovers -> `merge_vias.py`, `route.py --prune`
-> `gen_sch.py` -> `fab.sh`, with `check_power.py` as a release gate next to ERC/DRC.

Hand edits in KiCad are still possible for small fixes; keep the schematic linked (DRC with "Test for
parity" must stay at 0) and remember that `gen_pcb.py` refuses to overwrite a routed board. For netlist
changes prefer the generator + `eco.py` route (see `CLAUDE.md`).

## Stack-up and rules (already set)
| Layer | Use |
|---|---|
| F.Cu | parts, short signals, power pours (`PWR_*`) and RP2350 regulator pours (`VREG_*`) |
| In1 (GND) | solid GND plane. **Never route on it** |
| In2, In3 | signals |
| In4 (PWR) | solid 3V3 plane. **Never route on it** |
| B.Cu | signals + GND pour (`POUR_GND_B`) |

| Net class | Track / clearance | Via | Notes |
|---|---|---|---|
| Default | 0.127 / 0.127 | 0.45 / 0.2 | |
| Power (VBUS, PMID, VSYS, VBAT, V5, V5_PANEL, SW*) | 0.25 / 0.15 | 0.6 / 0.3 | the F.Cu pours carry the current; the traces only guarantee connection |
| HDMI_TMDS (TMDS_*, HD_*) | diff pair 0.132 / gap 0.20 | 0.45 / 0.2 | ~100 ohm for ~0.1 mm L1-L2 prepreg |
| USB (USB_P/N, UI_USB_P/N) | diff pair 0.162 / gap 0.20 | 0.45 / 0.2 | ~90 ohm for ~0.1 mm L1-L2 prepreg |

Board: **1.6 mm** (robu.in offers 0.8/1.0/1.2/1.6/2.0; the case and 3D model assume 1.6). The pair values
above assume a ~0.1 mm prepreg between F.Cu and In1 (typical 1.6 mm 6-layer); with ~0.2 mm prepreg use
0.19/0.15 (100 ohm) and 0.24/0.15 (90 ohm). Easiest: order with impedance control ("100 ohm diff on L1
ref L2, 90 ohm diff USB") and let the fab tune widths. Otherwise get the fab's 6-layer stack-up (prepreg thickness under F.Cu) and set the
pair width/gap with **Inspect > Calculator Tools > Transmission Lines** (coupled microstrip), in
**Board Setup > Net Classes**.

Useful keys: `X` route, `6` route a differential pair, `V` drop a via while routing (changes layer),
`D` drag, `B` refill zones. Use the **Shove** router mode (Route > Interactive Router Settings).

## Order
1. **Plane connections first.** Every GND / 3V3 pin gets a short stub and a 0.45 mm via right next to the
   pad into In1 / In4. For the QFN-60s, fan out from the pad ends straight away from the body. The
   exposed pads (GND) get a grid of vias.
2. **Power stage (U5 BQ25798, L5):** SW1/SW2 to L5 as short and wide as the pads allow, on F.Cu. VBUS/PMID
   input caps (C50-C53), BTST caps (C54, C55) and REGN cap tight to their pins. GND returns by vias next
   to each cap. BATP (R59) is a sense line: thin, away from SW nodes. Press `B` and check that the
   POUR_* zones connect every power pad.
3. **Buck converters:** U6 (TPS62933) and U7 (AP63203): input cap, IC and GND as one tight loop; SW node to
   the inductor short; feedback (FB5, R60/R61) away from the SW node. Then U9 (panel switch).
4. **RP2350 core supply:** VREG_LX to L1/L2 (AOTA, dot to VREG_LX) and back to DVDD/1V1 short; 1V1 caps on
   the pins.
5. **Crystals:** XIN/XOUT on F.Cu, no vias, as short as possible, GND around them.
6. **QSPI flash:** the 6 lines to F1/F2 short and on one layer.
7. **HSTX to HDMI (J6):** four pairs with `6`, on F.Cu or In2 (In2 sits between the GND and 3V3
   planes). 270R resistors (R80-R87) near the MCU, then pairs to J6. Match each pair's length (skew tuning)
   and keep the four pairs within a few mm of each other.
8. **USB:** J1 -> U3 (ESD) -> RUD1/RUD2 (27R, near U1) -> U1, as one diff pair. The BQ25798 D+/D- tap
   off the same nets: keep that stub short.
9. **RM2 gSPI** (WL_*): short, and never inside the RF keep-out at the board's front edge.
10. **Everything else** (keyboard header, SD, printer, expansion, LEDs, buttons, SWD): In2/In3 for the
    long runs.
11. Refill (`B`), run DRC with parity, and fix to **0 violations, 0 unconnected**.

## Then
```
sh hardware/kicad/fab.sh mainboard        # ERC/DRC gate + Gerbers, BOM, CPL, PDFs -> hardware/fab/
python3 hardware/kicad/export_parts.py mainboard && FreeCADCmd hardware/mechanical/case.py
```
