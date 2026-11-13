#!/usr/bin/env python3
"""Generate hardware/kicad/mainboard.kicad_sch from the generated board, then link the PCB to it.

Run after gen_pcb.py:  python3 hardware/mainboard/gen_sch.py
Symbols come from the KiCad library (ICs as chosen in gen_pcb.py, passives/connectors by type)
plus hardware/kicad/pico-comp.kicad_sym (RM2). Pins connect through net labels at their tips.
"""
import datetime
import json
import os
import sys

import pcbnew

here = os.path.dirname(os.path.abspath(__file__))
KICAD = os.path.join(here, "..", "kicad")
sys.path.insert(0, KICAD)
import kisch  # noqa: E402
import projsyms  # noqa: E402

PCB = os.path.join(KICAD, "mainboard.kicad_pcb")
SCH = os.path.join(KICAD, "mainboard.kicad_sch")

projsyms.write()
board = pcbnew.LoadBoard(PCB)
meta = json.load(open(os.path.join(KICAD, "mainboard.json")))
symmap = {r: tuple(v) for r, v in meta["symbols"].items()}

GENERIC = {  # footprint name prefix -> symbol
    "R_": ("Device", "R"), "C_": ("Device", "C"), "L_": ("Device", "L"), "LED_": ("Device", "LED"),
    "Buzzer_": ("Device", "Buzzer"), "Crystal_SMD_3225-4Pin": ("Device", "Crystal_GND24"), "SW_SPST": ("Switch", "SW_Push"),
    "MountingHole": ("Mechanical", "MountingHole"), "Fiducial": ("Mechanical", "Fiducial"),
    "USB_C_Receptacle": ("Connector", "USB_C_Receptacle_USB2.0_16P"),
    "HDMI_A": ("Connector", "HDMI_A"), "microSD_HC_Hirose": ("Connector", "Micro_SD_Card_Det_Hirose_DM3AT"),
    "JST_SH_SM06B": ("Connector_Generic_MountingPin", "Conn_01x06_MountingPin"),
}


def symbol_for(fp):
    ref, name = fp.GetReference(), str(fp.GetFPID().GetLibItemName())
    if ref in symmap:
        return symmap[ref]
    for k, v in GENERIC.items():
        if name.startswith(k):
            return v
    nums = {p.GetNumber() for p in fp.Pads() if p.GetNumber()}
    if "MP" in nums:                                   # connectors with mounting pads
        return ("Connector_Generic_MountingPin", f"Conn_01x{len(nums) - 1:02d}_MountingPin")
    return ("Connector_Generic", f"Conn_01x{len(nums):02d}")


GROUPS = [
    ("USB-C input, protection, BQ25798 2S charger, battery",
     lambda r: r in ("J1", "U3", "U10", "R100", "C100", "RUD1", "RUD2", "U5", "L5", "J2", "J5") or r.startswith(("C5", "R5"))),
    ("Rails: TPS62933 VSYS->5 V, AP63203 5 V->3.3 V, panel power",
     lambda r: r in ("U6", "L6", "U7", "L7", "D1", "J7", "J8", "U9", "R99") or r.startswith(("C6", "R6", "C7", "R7"))),
    ("UI MCU (U1): display (HSTX->HDMI), microSD, printer, expansion, USB",
     lambda r: r in ("U1", "L1", "F1", "Y1", "SW1", "SW2", "J3", "J6", "J9", "J12", "J13", "D2", "R95", "BZ1", "U12")
     or r.startswith(("C1", "R1", "R8", "R9", "C9")) and r not in ("R96", "R97")),
    ("NET MCU (U2): keyboard matrix, RM2 Wi-Fi, charger I2C",
     lambda r: r in ("U2", "L2", "F2", "Y2", "SW3", "SW4", "J4", "U8", "R96", "R97", "C80", "C81", "J11",
                     "J14", "RNU1", "RNU2", "RCC3", "RCC4", "U11")
     or r.startswith(("C2", "R2"))),
    ("Mechanical", lambda r: r.startswith(("H", "FID"))),
]

sch = kisch.Schematic("mainboard", "Pico-COMP main board", paper="A0", extra_dirs=[KICAD])
fps = sorted(board.GetFootprints(), key=lambda f: (f.GetReference().rstrip("0123456789ABCDEF"), f.GetReference()))
done = set()
X0, Y0, PAGE_W = 20.0, 30.0, 1150.0
y = Y0
for title, test in GROUPS:
    members = [f for f in fps if test(f.GetReference()) and f.GetReference() not in done]
    if not members:
        continue
    sch.text(title, X0, y, 3.0)
    y += 8
    x, row_h = X0, 0.0
    # big parts first so they lead each block
    members.sort(key=lambda f: -len(f.Pads()))
    for fp in members:
        ref = fp.GetReference()
        done.add(ref)
        lib, name = symbol_for(fp)
        nets = {p.GetNumber(): p.GetNetname() for p in fp.Pads() if p.GetNumber() and p.GetNetname()}
        fields = [(k, fp.GetFieldText(k)) for k in ("MPN", "Spec") if fp.HasField(k)]
        footprint = f"{fp.GetFPID().GetLibNickname()}:{fp.GetFPID().GetLibItemName()}"
        for unit in kisch.units_of(sch.symbol(lib, name)):
            w, h, ox, oy = sch.size(lib, name, unit, nets)
            if x + w > X0 + PAGE_W:
                x, y, row_h = X0, y + row_h + 4, 0.0
            sch.place(ref, lib, name, kisch.snap(x + ox), kisch.snap(y + oy), fp.GetValue(), footprint, nets,
                      fields, unit)
            x += w + 3
            row_h = max(row_h, h)
    y += row_h + 14
missing = [f.GetReference() for f in fps if f.GetReference() not in done]
assert not missing, f"footprints not in any schematic group: {missing}"
sch.text("Power flags (ERC)", X0, y, 3.0)
sch.power_flags(X0 + 10, y + 12)
sch.save(SCH, datetime.date.today().isoformat())

kisch.link_pcb(board, sch, "mainboard.kicad_sch")
board.Save(PCB)
print(f"{len(sch.links)} symbols -> {SCH}; PCB linked")
