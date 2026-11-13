# Routing the main board by hand (KiCad 10)

Open `hardware/kicad/mainboard.kicad_pro`, then the PCB editor. Placement, netlist, stack-up, rules and
pours are done; only tracks are missing (~360 connections). The schematic is linked, so **Inspect >
Design Rules Checker** with "Test for parity" stays meaningful.

Once the board has tracks, `hardware/mainboard/gen_pcb.py` refuses to overwrite it (`--force` would
wipe your routing). From here on, make netlist changes in KiCad: edit the schematic, then **Tools >
Update PCB from Schematic**. Don't rerun the generators.

## Stack-up and rules (already set)
| Layer | Use |
|---|---|
| F.Cu | parts, short signals, power pours (`POUR_*`, filled by B) |
| In1 (GND) | solid GND plane. **Never route on it** |
| In2, In3 | signals |
| In4 (PWR) | solid 3V3 plane. **Never route on it** |
| B.Cu | signals + GND pour (`POUR_GND_B`) |

| Net class | Track / clearance | Via | Notes |
|---|---|---|---|
| Default | 0.127 / 0.127 | 0.45 / 0.2 | |
| Power (VBUS, PMID, VSYS, VBAT, V5, V5_PANEL, SW*) | 0.25 / 0.15 | 0.6 / 0.3 | the F.Cu pours carry the current; the traces only guarantee connection |
| HDMI_TMDS (TMDS_*, HD_*) | diff pair 0.15 / gap 0.15 | 0.45 / 0.2 | ~100 ohm starting value |
| USB (USB_P/N, UI_USB_P/N) | diff pair 0.2 / gap 0.15 | 0.45 / 0.2 | ~90 ohm starting value |

Before routing the pairs, get the fab's 6-layer stack-up (prepreg thickness under F.Cu) and set the
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
