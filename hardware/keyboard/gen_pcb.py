#!/usr/bin/env python3
"""Generate the keyboard PCB (hardware/kicad/keyboard.kicad_pcb) from layout.py.

Places one Kailh Choc V1 footprint + one SOD-123 diode per key, assigns ROWn/COLn nets,
adds a 1x20 matrix header and the board outline. Tracks are NOT routed (ratsnest only).
Run: python3 hardware/keyboard/gen_pcb.py   (needs KiCad's pcbnew python module)
"""
import os

import pcbnew
from pcbnew import FromMM, VECTOR2I

import layout

here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(here, "..", "kicad", "keyboard.kicad_pcb")
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


def pad(fp, number, x, y, drill, size, shape=pcbnew.PAD_SHAPE_CIRCLE, ptype=pcbnew.PAD_ATTRIB_PTH):
    p = pcbnew.PAD(fp)
    p.SetNumber(str(number))
    p.SetShape(shape)
    p.SetAttribute(ptype)
    p.SetSize(VECTOR2I(FromMM(size), FromMM(size)))
    p.SetDrillSize(VECTOR2I(FromMM(drill), FromMM(drill)))
    p.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
    p.SetLayerSet(p.PTHMask())
    fp.Add(p)
    return p


def choc_footprint():
    """Kailh Choc V1: 3.4 mm centre post, pin 1 at (0,-5.9), pin 2 at (5,-3.8), 1.9 mm side pegs."""
    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference("SW")
    fp.SetValue("Choc_V1")
    pad(fp, 1, 0, -5.9, 1.2, 2.2)
    pad(fp, 2, 5.0, -3.8, 1.2, 2.2)
    for x, y, d in ((0, 0, 3.4), (-5.5, 0, 1.9), (5.5, 0, 1.9)):
        p = pcbnew.PAD(fp)
        p.SetNumber("")
        p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
        p.SetSize(VECTOR2I(FromMM(d), FromMM(d)))
        p.SetDrillSize(VECTOR2I(FromMM(d), FromMM(d)))
        p.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
        p.SetLayerSet(p.PTHMask())
        fp.Add(p)
    return fp


def mm(x, y):
    return VECTOR2I(FromMM(x), FromMM(y))


keys = layout.build()
m = layout.MARGIN
width = layout.ROW_U * layout.PITCH + 2 * m
height = len(layout.ROWS) * layout.PITCH + 2 * m + HEADER_STRIP
ncols = max(len(r) for r in layout.ROWS)
nrows = len(layout.ROWS)

for i, k in enumerate(keys):
    sw = choc_footprint()
    sw.SetReference(f"SW{i + 1}")
    sw.SetValue(k["name"])
    sw.SetPosition(mm(m + k["x"], m + k["y"]))
    board.Add(sw)

    d = pcbnew.FootprintLoad(os.path.join(FP_LIB, "Diode_SMD.pretty"), "D_SOD-123")
    d.SetReference(f"D{i + 1}")
    d.SetValue("1N4148W")
    d.SetPosition(mm(m + k["x"] + 3.5, m + k["y"] + 5.0))
    d.Reference().SetVisible(False)
    board.Add(d)

    mid = net(f"K{i + 1}")
    sw_pads = {p.GetNumber(): p for p in sw.Pads()}
    sw_pads["1"].SetNet(net(f"COL{k['col']}"))
    sw_pads["2"].SetNet(mid)
    for p in d.Pads():
        p.SetNet(mid if p.GetNumber() == "2" else net(f"ROW{k['row']}"))  # anode=2 on SOD-123 lib

# 1x20 header: ROW0-5 then COL0-13
hdr = pcbnew.FootprintLoad(os.path.join(FP_LIB, "Connector_PinHeader_2.54mm.pretty"), "PinHeader_1x20_P2.54mm_Horizontal")
hdr.SetReference("J1")
hdr.SetValue("KB_MATRIX")
hdr.SetPosition(mm(10, height - 5))
hdr.SetOrientationDegrees(90)
board.Add(hdr)
names = [f"ROW{r}" for r in range(nrows)] + [f"COL{c}" for c in range(ncols)]
for p, n in zip(sorted(hdr.Pads(), key=lambda q: int(q.GetNumber())), names):
    p.SetNet(net(n))

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

board.Save(out)
print(f"{len(keys)} switches, {len(nets)} nets, board {width:.0f} x {height:.0f} mm -> {out}")
