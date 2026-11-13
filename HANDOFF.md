# Status: hardware production pass (2026-11-13, 08:00, on this laptop)

Nothing is committed yet: all of the work is uncommitted changes on `master`. Read `CLAUDE.md` and
`docs/hardware-plan.md` first.

## Main board routing status (2026-11-13, 16:20)
Design is final: RP2350B UI MCU + 64 GB eMMC, dual-role USB-C (TUSB320) + NET USB-C, reset pinhole,
UI->NET SWD reflash. ERC 0; DRC clean except unrouted. **Not routed yet.**

Routing pipeline (all in `hardware/mainboard/`):
1. `python3 fanout.py ../kicad/<board>.kicad_pcb`: GND/3V3 plane fan-out, BGA via-in-pad (0.35/0.15),
   and dog-bone fan-out of signal pins on U1/U2/U5/U10 (fine-pitch escape). All locked.
2. `python3 maze_route.py ../kicad/<board>.kicad_pcb`: own A* grid router with line-of-sight smoothing;
   routes DRC-unconnected pairs shortest-first and saves progress. Clean (0 clearance errors), but greedy:
   it stalls when early routes block later ones.
3. `python3 route.py ../kicad/<board>.kicad_pcb 40 [--keep]`: Freerouting (rip-up and reroute); `--keep`
   starts from the maze-routed copper. It only saves at 0 unrouted, so run several in parallel.
4. `python3 tidy_tracks.py`, `route.py --cleanup`, then DRC (`kicad-cli pcb drc --schematic-parity
   --refill-zones`) to 0/0, copy over `mainboard.kicad_pcb`, `sh ../kicad/fab.sh mainboard`.

Results so far: Freerouting alone stalls at ~31-46 unrouted; maze alone at 85; maze then Freerouting at
~46. **With the signal dog-bone fan-out (step 1), Freerouting reached 8-9 unrouted in ~15 min (16:26)**,
so that is the way forward. Next session: run 3-4 Freerouting copies on a fresh `fanout.py` board. If they
stall at a handful, use `maze_route.py` on the saved result, or route those few by hand in KiCad. Leftovers cluster at the BQ25798 charger, the NET MCU / 5 V buck and the UI flash (fine-pitch
escape), which is why step 1 now fans out signal pins too. Runs on that board started 16:10 (logs in
`/tmp/claude-1000/route/`, boards `hardware/kicad/fr1/fr2/mz3.kicad_pcb`).
If it still stalls: relieve the charger area (move R50-R59/C5x further out), or route the last few by
hand in KiCad (`docs/mainboard-routing.md`).

## Done
- **Keyboard PCB: finished.** Routed, KiCad DRC 0 (warnings included), 0 unconnected, schematic parity 0,
  ERC 0. Fab package in `hardware/fab/keyboard/` + `hardware/fab/keyboard-gerbers.zip`.
- **Main board: schematic and placement final, not routed.** ERC 0, parity 0. Circuit fixes vs the last
  commit:
  - BQ25798: PROG 8.2k, ACDRV to GND, SDRV 1 nF, BATP 100R.
  - HDMI pin 18 = +5 V.
  - Printer moved to UART1 (UART0 is the MCU link).
  - Piezo beeper on GPIO26.
  - TPS22917 panel 5 V switch on GPIO27.
  - Raspberry Pi RM2 Wi-Fi with RF keep-outs.
  - RP2350 inductor is the AOTA part.
  - Fiducials, MPN/Spec fields, "Pico COMP / © 2026 Aditya Kale" silk.
- **Main board is now 6 layers:** F sig / In1 GND plane / In2 sig / In3 sig / In4 3V3 plane / B sig + GND pour.
  4 layers could only be autorouted by running signals through the planes, which left 37 real opens.
- **FreeCAD:** `hardware/mechanical/case.py` builds the assembly with ~470 separate grouped objects. Keycaps
  are in `hardware/mechanical/keycaps/` (75 caps, legends + inlays). Print parts are in `print/`. The
  assembly was last built before the routing work: rebuild it (step 4 below).
- Firmware pin map `firmware/common/pins.h` matches the board; the firmware builds.

## Decisions made by Aditya (2026-11-13)
- **6-layer main board: approved** (cost is fine).
- **Add stabilizers** for the 2u Shift (row 4, col 0) and the 6u Space (row 5, col 3).
  1. Pick a real Choc V1 stabilizer and find its datasheet or drawing: the Kailh Choc PCB/plate-mount
     2u and 6.25u stabilizer. One community source (the Alkene stabilizer project) gives stem spacing
     "A" = 24.0 mm for Choc 2u and 76.0 mm for Choc 6.25u. Verify that against a drawing; don't guess.
  2. Add the stabilizer cut-outs to the plate (`hardware/keyboard/layout.py` writes `plate.dxf`; the
     case plate in `mechanical/case.py`).
  3. Add the stabilizer mounting holes / keep-outs to the keyboard PCB (`hardware/keyboard/gen_pcb.py`).
     This changes the keyboard: rerun `gen_pcb.py`, `gen_sch.py`, then
     `route.py ../kicad/keyboard.kicad_pcb 15`, DRC to 0, then `fab.sh keyboard`.
  4. Add the stabilizer stems to the Shift and Space caps (`hardware/mechanical/keycaps.py`, `make()`),
     and update the keycaps README note.
  5. Record the chosen part (MPN) in `docs/hardware-plan.md` and drop it from "Open items".

## Remaining (in order)
1. **Route the main board.** From `hardware/mainboard`:
   `python3 route.py ../kicad/mainboard.kicad_pcb 40`
   (or race 3 copies `try1..3.kicad_pcb` + matching `.kicad_pro` in `hardware/kicad`, keep the first that
   prints `routed:`, then copy it over `mainboard.kicad_pcb`).
   - Freerouting 2.1 ignores the pass limit and only saves when it reaches 0 unrouted. If it stalls on a
     few nets, kill it, rerun with `--skip=NET1,NET2` (the DEBUG lines in `/tmp/freerouting/freerouting.log`
     name them as "net #N" = Nth `(net` in the DSN network section, 1-based), then add those nets to
     `hand_route.py` and run it.
   - The paths in `hand_route.py` were written for the old 4-layer routing, so redo them against the
     real copper.
   - On the laptop, three parallel 6-layer runs were at ~180 unrouted by pass ~5 after 10 min. They were
     stopped, so start fresh. The P53 has 4 cores: run 1-2 copies, not 3.
2. Check from `hardware/kicad`:
   `kicad-cli pcb drc --schematic-parity --refill-zones --severity-all mainboard.kicad_pcb`
   Must be 0 violations, 0 unconnected.
3. `sh hardware/kicad/fab.sh mainboard`. It gates on ERC/DRC, then writes `hardware/fab/mainboard/`.
4. `python3 hardware/kicad/export_parts.py && FreeCADCmd hardware/mechanical/case.py`, then
   `python3 hardware/mechanical/build_viewer.py`. `case.py` prints an interference report; it should
   say `none`.
5. Update `docs/hardware-plan.md` (it still says 4 layers / 152x68 "F.Cu / GND / 3V3 / B.Cu") and the
   README status.
6. Stabilizers (see above). They can be done while the main board routes.
7. Delete `hardware/kicad/try*.kicad_p*` and this file. Tell Aditya what is left.

## Gotchas found this session
- `route.py` must pass `--gui.enabled=false` (already does). Otherwise Freerouting never writes the session file.
- Freerouting treats copper pours on signal layers as solid obstacles. `route.py` hides zones named
  `POUR_*` during DSN export and refills them afterwards. Plane layers must be `LT_POWER` so it never
  routes on them.
- Clean-up deletes only what KiCad's own DRC calls dangling (`remove_dangling`). Use `board.Delete`,
  never `board.Remove`: Remove segfaults.

## Open decisions for Aditya
- Measure: panel thickness, Choc PCB-to-plate height (`PCB_TO_PLATE` in case.py), HDMI cable.
- Datasheet review of passive values before ordering.
