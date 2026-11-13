#!/usr/bin/env python3
"""Generate hardware/kicad/keyboard.kicad_sch from keyboard.kicad_pcb and link the PCB to it.

Run after gen_pcb.py:  python3 hardware/keyboard/gen_sch.py
Switch + diode pairs are drawn in the physical row/column grid, connected through net labels.
"""
import datetime
import os
import sys

import pcbnew

here = os.path.dirname(os.path.abspath(__file__))
KICAD = os.path.join(here, "..", "kicad")
sys.path.insert(0, KICAD)
sys.path.insert(0, here)
import kisch  # noqa: E402
import layout  # noqa: E402

PCB = os.path.join(KICAD, "keyboard.kicad_pcb")
SCH = os.path.join(KICAD, "keyboard.kicad_sch")
board = pcbnew.LoadBoard(PCB)
fps = {f.GetReference(): f for f in board.GetFootprints()}
sch = kisch.Schematic("keyboard", "Pico-COMP keyboard matrix (6 x 14)", paper="A1", extra_dirs=[KICAD])


def put(ref, lib, name, x, y):
    fp = fps[ref]
    nets = {p.GetNumber(): p.GetNetname() for p in fp.Pads() if p.GetNumber() and p.GetNetname()
                and not p.GetNetname().startswith("unconnected-(")}   # NC pads get these nets from link_pcb
    fields = [(k, fp.GetFieldText(k)) for k in ("MPN", "Spec") if fp.HasField(k)]
    footprint = f"{fp.GetFPID().GetLibNickname()}:{fp.GetFPID().GetLibItemName()}"
    sch.place(ref, lib, name, kisch.snap(x), kisch.snap(y), fp.GetValue(), footprint, nets, fields)


sch.text("Key matrix: COL -> switch -> diode (anode) -> ROW. Scan: drive one ROW low, read COLs with pull-ups.",
         20, 20, 2.5)
DX, DY, X0, Y0 = 55.88, 45.72, 30.48, 40.64
for i, k in enumerate(layout.build()):
    x, y = X0 + k["col"] * DX, Y0 + k["row"] * DY
    sch.text(k["name"], x - 5, y - 8, 1.8)
    put(f"SW{i + 1}", "Switch", "SW_Push", x, y)
    put(f"D{i + 1}", "Device", "D", x, y + 15.24)
yb = Y0 + len(layout.ROWS) * DY + 10
sch.text("Matrix connector (to mainboard J11) and mechanical", 20, yb, 2.5)
put("J1", "Connector_Generic", "Conn_01x20", 50, yb + 40)
for n, r in enumerate(sorted(r for r in fps if r.startswith(("H", "FID", "ST")))):
    sym = "MountingHole" if r.startswith("H") else "Fiducial" if r.startswith("FID") else "Housing"
    put(r, "Mechanical", sym, 120 + n * 20, yb + 15)
sch.save(SCH, datetime.date.today().isoformat())
kisch.link_pcb(board, sch, "keyboard.kicad_sch")
board.Save(PCB)
print(f"{len(sch.links)} symbols -> {SCH}; PCB linked")
