#!/usr/bin/env python3
"""Import the RP2350 core-regulator layout from Raspberry Pi's minimal design boards.

    python3 hardware/kicad/import_rp2350_vreg.py <RPI-RP2350A-MINIMAL.kicad_pcb> <RPI-RP2350B-MINIMAL.kicad_pcb>

Source: Raspberry Pi "RP2350A/B Minimal KiCAD design" (RP-010328-CA / RP-010329-CA, R4), linked from
"Hardware design with RP2350" (RP-008280-DS). Raspberry Pi say the regulator only behaves with *their*
placement, parts and inductor orientation ("if you choose not to use our example, then you do so at your own
risk"), so this copies it exactly: parts (L1, C6, C7, C9, R3) and the regulator copper (local pours, tracks,
vias) in the RP2350's own frame. Writes hardware/mainboard/rp2350_vreg.py (data) and the inductor / wide
0402 footprints into pico-comp.pretty.

The minimal designs are MIT licensed: Copyright (c) 2026 Raspberry Pi Ltd (notice kept in the outputs).
"""
import os
import pprint
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kisch  # noqa: E402

here = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(here, "..", "mainboard", "rp2350_vreg.py")
NETS = {"+1V1": "1V1", "/VREG_LX": "LX", "/VREG_AVDD": "AVDD", "+3V3": "3V3", "GND": "GND"}
PARTS = {"L1": "L", "C6": "CIN", "C7": "COUT", "C9": "CAVDD", "R3": "RAVDD"}
WINDOW = (-0.5, -10.6, 7.0, -2.5)          # IC-frame box around the regulator (both packages)
MIT = ("MIT License, Copyright (c) 2026 Raspberry Pi Ltd. Permission is hereby granted, free of charge, to "
       "any person obtaining a copy of this software and associated documentation files, to deal in the "
       "Software without restriction, subject to the following conditions: the above copyright notice and "
       "this permission notice shall be included in all copies or substantial portions of the Software. "
       "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND.")


def grab(path):
    b = pcbnew.LoadBoard(path)
    u = b.FindFootprintByReference("U1")
    assert u.GetOrientationDegrees() == 0
    o = u.GetPosition()

    def L(p):
        return (round((p.x - o.x) / 1e6, 4), round((p.y - o.y) / 1e6, 4))

    def inside(p):
        x, y = L(p)
        return WINDOW[0] <= x <= WINDOW[2] and WINDOW[1] <= y <= WINDOW[3]
    d = {"parts": {}, "zones": [], "tracks": [], "vias": []}
    for ref, role in PARTS.items():
        f = b.FindFootprintByReference(ref)
        d["parts"][role] = {"at": L(f.GetPosition()), "rot": round(f.GetOrientationDegrees() % 360, 1),
                            "pads": {p.GetNumber(): NETS[p.GetNetname()] for p in f.Pads()}}
    for z in b.Zones():
        n = NETS.get(z.GetNetname())
        if not n or z.GetIsRuleArea() or not z.IsOnLayer(pcbnew.F_Cu):
            continue
        ol = z.Outline().Outline(0)
        pts = [L(ol.CPoint(i)) for i in range(ol.PointCount())]
        if all(WINDOW[0] <= x <= WINDOW[2] and WINDOW[1] <= y <= WINDOW[3] for x, y in pts):
            d["zones"].append({"net": n, "priority": z.GetAssignedPriority(), "pts": pts,
                               "clearance": z.GetLocalClearance() / 1e6})
    for t in b.GetTracks():
        n = NETS.get(t.GetNetname())
        if not n:
            continue
        if t.GetClass() == "PCB_VIA":
            if inside(t.GetPosition()):
                d["vias"].append({"net": n, "at": L(t.GetPosition()), "d": t.GetWidth(pcbnew.F_Cu) / 1e6,
                                  "drill": t.GetDrill() / 1e6})
        elif t.GetLayer() == pcbnew.F_Cu and inside(t.GetStart()) and inside(t.GetEnd()) and n != "3V3":
            # 3V3 tracks run into the reference footprint's under-chip ring; we feed VREG_VIN from the In4 plane
            d["tracks"].append({"net": n, "a": L(t.GetStart()), "b": L(t.GetEnd()), "w": t.GetWidth() / 1e6})
    pins = {}
    for p in u.Pads():
        n = p.GetNetname()
        if n in ("/VREG_LX", "/VREG_AVDD", "GND", "+3V3", "+1V1") and inside(p.GetPosition()):
            pins.setdefault(NETS[n], []).append(L(p.GetPosition()))
    d["pins"] = pins
    return d, b


def save_footprints(b):
    """L1 (AOTA, polarity dot at pad 1 = 1V1) and the wide 0402 used for C6/C7, as project footprints."""
    lib = os.path.join(here, "pico-comp.pretty")
    out = {}
    for ref, name, model in (("L1", "L_Abracon_AOTA-B201610S_RPi", "Inductor_SMD.3dshapes/L_Abracon_AOTA-B201610S.step"),
                             ("C6", "C_0402_1005Metric_RPi_Wide", "Capacitor_SMD.3dshapes/C_0402_1005Metric.step")):
        f = b.FindFootprintByReference(ref).Duplicate(False)
        f = pcbnew.Cast_to_FOOTPRINT(f) if not isinstance(f, pcbnew.FOOTPRINT) else f
        f.SetPosition(pcbnew.VECTOR2I(0, 0))
        f.SetOrientationDegrees(0)
        for p in f.Pads():
            p.SetNetCode(0)
        f.Models().clear()
        m = pcbnew.FP_3DMODEL()
        m.m_Filename = "${KICAD10_3DMODEL_DIR}/" + model
        f.Models().push_back(m)
        f.SetFPID(pcbnew.LIB_ID("pico-comp", name))
        f.SetReference("REF**")
        f.SetValue(name)
        f.SetLibDescription(f"From Raspberry Pi RP2350 minimal design ({ref}). {MIT}")
        pcbnew.FootprintSave(lib, f)
        # drop Raspberry Pi's internal part-database fields (and its C:\ datasheet path) from the saved copy
        fn = os.path.join(lib, name + ".kicad_mod")
        node = kisch.parse(open(fn).read())
        node = [e for e in node if not (isinstance(e, list) and e and e[0] == "property"
                                        and e[1].strip('"') not in ("Reference", "Value", "Footprint", "Description"))]
        open(fn, "w").write(kisch.dump(node) + "\n")
        out[ref] = name
    return out


if __name__ == "__main__":
    data = {}
    fps = None
    for path in sys.argv[1:3]:
        d, b = grab(path)
        data["RP2350A" if "RP2350A" in os.path.basename(path) else "RP2350B"] = d
        fps = fps or save_footprints(b)
    with open(OUT, "w") as fh:
        fh.write('"""RP2350 core-regulator layout, generated by hardware/kicad/import_rp2350_vreg.py from Raspberry Pi\'s\n'
                 'RP2350A/B minimal KiCad designs (RP-010328-CA / RP-010329-CA). Coordinates in mm in the RP2350\'s frame\n'
                 '(footprint origin, rotation 0); nets: LX, 1V1, AVDD, 3V3, GND. Do not edit: regenerate.\n\n'
                 + MIT + '\n"""\n')
        fh.write(f"FOOTPRINTS = {fps!r}\n")
        fh.write("LAYOUT = " + pprint.pformat(data, width=110, sort_dicts=False) + "\n")
    print("wrote", OUT, "and footprints", fps)
