#!/usr/bin/env python3
"""Generate the keyboard PCB (hardware/kicad/keyboard.kicad_pcb) from layout.py.

One Kailh Choc V1 (top, through-hole) + one 1N4148W diode per key on the BOTTOM side (the switch
housing sits flat on the top surface, so nothing may be under it on top), ROWn/COLn nets, a 1x20
matrix header, fiducials, an RF keep-out above the mainboard's RM2 antenna and the board outline.
Matrix: COL -> switch -> diode anode, cathode -> ROW (drive rows low, read columns with pull-ups).

Run: python3 hardware/keyboard/gen_pcb.py      (needs KiCad's pcbnew python module)
Then: python3 hardware/keyboard/gen_sch.py
      python3 hardware/mainboard/route.py hardware/kicad/keyboard.kicad_pcb
"""
import json
import os
import sys

import pcbnew
from pcbnew import FromMM, VECTOR2I

import layout

here = os.path.dirname(os.path.abspath(__file__))
KICAD = os.path.join(here, "..", "kicad")
sys.path.insert(0, os.path.join(here, ".."))
sys.path.insert(0, KICAD)
import fplib  # noqa: E402
import placement  # noqa: E402

out = os.path.join(KICAD, "keyboard.kicad_pcb")
FP_LIB = "/usr/share/kicad/footprints"
HEADER_STRIP = 12.0   # extra board depth below the keys for the matrix header
board = pcbnew.NewBoard(out)
nets = {}


def net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        nets[name] = n
    return nets[name]


def mm(x, y):
    return VECTOR2I(FromMM(x), FromMM(y))


def load(lib, name, ref, value, x, y, rot=0, back=False, mpn="", spec=""):
    if fplib.needs_copy(name):
        lib = fplib.copy(lib, name)
    path = os.path.join(KICAD, "pico-comp.pretty") if lib == "pico-comp" else os.path.join(FP_LIB, f"{lib}.pretty")
    fp = pcbnew.FootprintLoad(path, name)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetReference(ref)
    fp.SetValue(value)
    for k, v in (("MPN", mpn), ("Spec", spec)):
        if v:
            fp.SetField(k, v)
            fp.GetField(k).SetVisible(False)
    board.Add(fp)
    if rot:
        fp.SetOrientationDegrees(rot)
    fp.SetPosition(mm(x, y))
    if back:
        fp.Flip(mm(x, y), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
    return fp


keys = layout.build()
m = layout.MARGIN
width = layout.ROW_U * layout.PITCH + 2 * m
height = len(layout.ROWS) * layout.PITCH + 2 * m + HEADER_STRIP
assert (width, height) == (placement.KB_W, placement.KB_H), "placement.py is out of date"
ncols = max(len(r) for r in layout.ROWS)
nrows = len(layout.ROWS)

for i, k in enumerate(keys):
    x, y = m + k["x"], m + k["y"]
    sw = load("pico-comp", "Kailh_Choc_V1", f"SW{i + 1}", "Choc_V1", x, y, mpn="CPG135001D01")
    # diode on the bottom, between the pegs and below the centre post
    d = load("Diode_SMD", "D_SOD-123", f"D{i + 1}", "1N4148W", x, y + 3.6, back=True, mpn="1N4148W-7-F")
    d.Reference().SetVisible(False)
    mid = net(f"K{i + 1}")
    sw_pads = {p.GetNumber(): p for p in sw.Pads()}
    sw_pads["1"].SetNet(net(f"COL{k['col']}"))
    sw_pads["2"].SetNet(mid)
    for p in d.Pads():
        p.SetNet(mid if p.GetNumber() == "2" else net(f"ROW{k['row']}"))  # pad 2 = anode on SOD-123

# Kailh PG1350 plate-mount stabilizers (2u Shift, 6u Space): footprints carry the PCB clearance cut-outs
STAB_FP = {2: ("Kailh_Choc_Stabilizer_2u", "Kailh PG1350 stabilizer 2U kit (wire BWPG1350-07003)"),
           6: ("Kailh_Choc_Stabilizer_6u", "Kailh PG1350 stabilizer 6.25U kit (wire BWPG1350-07002)")}
for n, k in enumerate([k for k in keys if int(k["w"]) in STAB_FP], 1):
    fpname, spec = STAB_FP[int(k["w"])]
    st = load("pico-comp", fpname, f"ST{n}", f"Stabilizer {k['w']:g}u", m + k["x"], m + k["y"], spec=spec)
    st.Reference().SetVisible(False)

# 1x20 header: ROW0-5 then COL0-13 (matches the mainboard's J11). Right-angle pins stick out past
# the front edge, pin 1 at the right end.
hdr = load("Connector_PinHeader_2.54mm", "PinHeader_1x20_P2.54mm_Horizontal", "J1", "KB_MATRIX", 62, height - 4.5, 270,
           spec="1x20 2.54 mm right-angle header")
hdr.Reference().SetVisible(False)
names = [f"ROW{r}" for r in range(nrows)] + [f"COL{c}" for c in range(ncols)]
for p, n in zip(sorted(hdr.Pads(), key=lambda q: int(q.GetNumber())), names):
    p.SetNet(net(n))

# M2.5 mounting holes in the corners (case.py posts match these)
for n, (hx, hy) in enumerate(placement.KB_HOLES, 1):
    mh = load("MountingHole", "MountingHole_2.7mm_M2.5", f"H{n}", "M2.5", hx, hy)
    mh.Reference().SetVisible(False)

# fiducials on the bottom (the SMD side)
for n, (fx, fy) in enumerate([(70, height - 2.5), (width - 12, height - 2.5), (width - 2.5, 30)], 1):
    load("Fiducial", "Fiducial_1mm_Mask2mm", f"FID{n}", "Fiducial", fx, fy, back=True).Reference().SetVisible(False)
    fplib.keepout_circle(board, fx, fy, 1.8)

# RF keep-out above the mainboard RM2 antenna (no copper so the antenna can radiate upward)
mb = json.load(open(os.path.join(KICAD, "mainboard.json")))
x0, y0, x1, y1 = mb["rf_keepout"]                      # mainboard frame
cx0, cy0 = placement.mb_to_case(x0, y0)
cx1, cy1 = placement.mb_to_case(x1, y1)
kx0, ky0 = placement.case_to_kb(min(cx0, cx1), max(cy0, cy1))
kx1, ky1 = placement.case_to_kb(max(cx0, cx1), min(cy0, cy1))
ky1 = min(ky1, height - 0.3)
ko = pcbnew.ZONE(board)
ko.SetIsRuleArea(True)
ko.SetLayerSet(pcbnew.LSET.AllCuMask())
ko.SetDoNotAllowTracks(True)
ko.SetDoNotAllowVias(True)
ko.SetDoNotAllowZoneFills(True)
ko.SetDoNotAllowPads(False)
ko.SetDoNotAllowFootprints(False)
ko.SetZoneName("RM2_ANTENNA_KEEPOUT")
ol = ko.Outline()
ol.NewOutline()
for px, py in [(kx0, ky0), (kx1, ky0), (kx1, ky1), (kx0, ky1)]:
    ol.Append(FromMM(px), FromMM(py))
board.Add(ko)


def silk_text(text, x, y, size, thick, layer=pcbnew.F_SilkS):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetLayer(layer)
    t.SetPosition(mm(x, y))
    t.SetTextSize(mm(size, size))
    t.SetTextThickness(FromMM(thick))
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    board.Add(t)


silk_text("Pico COMP", 125, height - 7.5, 2.0, 0.3)
silk_text("keyboard v1.0   © 2026 Aditya Kale", 125, height - 3.5, 1.2, 0.18)
silk_text("Pico COMP keyboard v1.0   © 2026 Aditya Kale", 125, height - 5, 1.2, 0.18, pcbnew.B_SilkS)

# Board outline
pts = [(0, 0), (width, 0), (width, height), (0, height)]
for a, b in zip(pts, pts[1:] + pts[:1]):
    seg = pcbnew.PCB_SHAPE(board)
    seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
    seg.SetLayer(pcbnew.Edge_Cuts)
    seg.SetStart(mm(*a))
    seg.SetEnd(mm(*b))
    seg.SetWidth(FromMM(0.1))
    board.Add(seg)

ds = board.GetDesignSettings()
ds.m_TrackMinWidth = FromMM(0.15)
ds.m_MinClearance = FromMM(0.15)
ds.m_CopperEdgeClearance = FromMM(0.3)
nc = ds.m_NetSettings.GetDefaultNetclass()
nc.SetClearance(FromMM(0.2))
nc.SetTrackWidth(FromMM(0.25))
nc.SetViaDiameter(FromMM(0.6))
nc.SetViaDrill(FromMM(0.3))

board.Save(out)
print(f"{len(keys)} switches, {len(nets)} nets, board {width:.0f} x {height:.0f} mm -> {out}")
