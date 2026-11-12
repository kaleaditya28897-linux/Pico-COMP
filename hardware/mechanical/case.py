"""Parametric Pico-COMP case. Run: FreeCADCmd hardware/mechanical/case.py

Writes pico-comp.FCStd and pico-comp.step next to this file. Units are mm.
Display module dimensions are typical 10.1" 1280x800 values and MUST be verified
against the real kit before manufacturing (see docs/hardware-plan.md).
"""
import os
import sys

import FreeCAD as App
import Part

here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
sys.path.insert(0, os.path.join(here, "..", "keyboard"))
import layout  # noqa: E402

V = App.Vector

# Overall footprint (display module ~230 wide + bezels; keyboard plate 244 wide)
W, D = 250.0, 140.0
WALL = 2.5
BASE_H = 26.0
PLATE_T = 1.5
PLATE_TOP = 26.0            # plate top flush with the base rim; Choc keycaps rise ~6 mm above
LID_H = 14.0
LID_D = D       # lid matches the base footprint; bezels grow around the smaller 7" panel
PANEL = (164.9, 124.27, 10.0)       # 7" 1024x600 HDMI LCD incl. driver board (vendor spec); thickness is a guess, measure it
ACTIVE = (154.08, 85.92)            # visible area from the listing
ANT = (30.0, 8.0, 1.0)              # 2.4 GHz stick-on flex antenna (assumed size), long axis along Y
ANT_POCKET = (34.0, 12.0, 4.0)      # rib-bounded pocket for it in the right bezel, flush under the top skin
CELL_D, CELL_L = 18.6, 65.2         # 18650 with wrap

doc = App.newDocument("PicoComp")


def add(name, shape, color=None):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    return obj


# Base shell: open top, battery bay + electronics space inside
outer = Part.makeBox(W, D, BASE_H)
inner = Part.makeBox(W - 2 * WALL, D - 2 * WALL, BASE_H - WALL, V(WALL, WALL, WALL))
base = outer.cut(inner)
# USB-C / SD cutouts on the left and right walls (placeholders)
base = base.cut(Part.makeBox(WALL + 1, 10, 4, V(-0.5, 40, 8)))   # USB-C
base = base.cut(Part.makeBox(WALL + 1, 14, 3, V(W - WALL - 0.5, 40, 8)))  # SD card
add("Base", base)

# Key plate with Choc cutouts from the layout generator
keys = layout.build()
margin = layout.MARGIN
pw = layout.ROW_U * layout.PITCH + 2 * margin
ph = len(layout.ROWS) * layout.PITCH + 2 * margin
px0 = (W - pw) / 2
py_top = D - WALL - 1.0               # plate rear edge, near the hinge side
plate = Part.makeBox(pw, ph, PLATE_T, V(px0, py_top - ph, PLATE_TOP - PLATE_T))
h = layout.CUTOUT / 2
for k in keys:
    cx = px0 + margin + k["x"]
    cy = py_top - margin - k["y"]
    plate = plate.cut(Part.makeBox(layout.CUTOUT, layout.CUTOUT, PLATE_T + 2, V(cx - h, cy - h, PLATE_TOP - PLATE_T - 1)))
add("KeyPlate", plate)

# 4x 18650 in a row under the left side of the keyboard
cells = None
for i in range(4):
    c = Part.makeCylinder(CELL_D / 2, CELL_L, V(WALL + 6 + CELL_D / 2 + i * (CELL_D + 0.4), WALL + 6, WALL + CELL_D / 2), V(0, 1, 0))
    cells = c if cells is None else cells.fuse(c)
add("Cells18650", cells)

# Lid, placed above the base (closed clamshell stack)
lz = PLATE_TOP + 7.0   # clearance for keycaps
lid_outer = Part.makeBox(W, LID_D, LID_H, V(0, 0, lz))
lid_inner = Part.makeBox(W - 2 * WALL, LID_D - 2 * WALL, LID_H - WALL, V(WALL, WALL, lz + WALL))
lid = lid_outer.cut(lid_inner)
# display window through the lid top; panel sits just behind it
wx = (W - ACTIVE[0]) / 2
wy = (LID_D - ACTIVE[1]) / 2
lid = lid.cut(Part.makeBox(ACTIVE[0], ACTIVE[1], WALL + 1, V(wx, wy, lz + LID_H - WALL - 0.5)))

# Antenna pocket in the right bezel, beside the panel (never behind it): the
# metal panel frame would detune/shield it. Ribs hold the antenna against the
# underside of the top skin; a channel through the rear wall takes the U.FL coax.
bezel_x0 = (W + PANEL[0]) / 2                     # panel right edge
bezel_mid = (bezel_x0 + W - WALL) / 2
top_z = lz + LID_H - WALL                          # underside of the top skin
RIB = 1.2
py0 = LID_D - WALL - 6.0 - ANT_POCKET[0]           # pocket close to the hinge (rear) edge
pocket_o = Part.makeBox(ANT_POCKET[1] + 2 * RIB, ANT_POCKET[0] + 2 * RIB, ANT_POCKET[2],
                        V(bezel_mid - ANT_POCKET[1] / 2 - RIB, py0 - RIB, top_z - ANT_POCKET[2]))
pocket_i = Part.makeBox(ANT_POCKET[1], ANT_POCKET[0], ANT_POCKET[2] + 1,
                        V(bezel_mid - ANT_POCKET[1] / 2, py0, top_z - ANT_POCKET[2] - 0.5))
lid = lid.fuse(pocket_o.cut(pocket_i))
coax = Part.makeCylinder(1.5, 12.0, V(bezel_mid, py0 + ANT_POCKET[0] - 2, top_z - 2.5), V(0, 1, 0))
lid = lid.cut(coax)
add("Lid", lid)

antenna = Part.makeBox(ANT[1], ANT[0], ANT[2],
                       V(bezel_mid - ANT[1] / 2, py0 + (ANT_POCKET[0] - ANT[0]) / 2, top_z - ANT[2]))
add("Antenna", antenna)

panel = Part.makeBox(PANEL[0], PANEL[1], PANEL[2], V((W - PANEL[0]) / 2, (LID_D - PANEL[1]) / 2, lz + LID_H - WALL - PANEL[2]))
add("DisplayPanel", panel)

doc.recompute()

# Sanity checks: plate fits inside the base, panel fits inside the lid
assert pw <= W - 2 * WALL, "key plate wider than base interior"
assert PANEL[0] <= W - 2 * WALL and PANEL[1] <= LID_D - 2 * WALL, "panel does not fit the lid"
assert bezel_x0 + ANT_POCKET[1] / 2 + RIB < W - WALL and bezel_mid - ANT_POCKET[1] / 2 - RIB > bezel_x0, "antenna pocket does not fit the bezel"
assert antenna.common(panel).Volume < 1e-6, "antenna overlaps the panel"
assert cells.BoundBox.ZMax < PLATE_TOP - PLATE_T - 1.6, "cells collide with the key PCB"
bb = Part.makeCompound([o.Shape for o in doc.Objects]).BoundBox
print(f"Assembly bounding box: {bb.XLength:.1f} x {bb.YLength:.1f} x {bb.ZLength:.1f} mm")
print(f"Plate {pw:.0f} x {ph:.0f} mm, plate-to-front palm rest {py_top - ph - WALL:.1f} mm")

doc.saveAs(os.path.join(here, "pico-comp.FCStd"))
Part.export(doc.Objects, os.path.join(here, "pico-comp.step"))
print("wrote pico-comp.FCStd and pico-comp.step")

# ---------------------------------------------------------------------------
# Viewable assembly: lid opened, keycaps, PCBs, battery. Exported as
# assembly.json (coloured meshes) for build_viewer.py; not used for manufacturing.
# ---------------------------------------------------------------------------
import json  # noqa: E402

OPEN_DEG = 80.0                      # lid angle: 90 = vertical, <90 leans back
CAP = 16.0                           # Choc keycap footprint (17 mm pitch)
CAP_H = 6.0
parts = []                           # (name, shape, rgb)


def lid_pose(shape):
    """Move a lid-frame shape (screen facing +Z, lying over the base) to the open pose."""
    sh = shape.copy()
    sh.translate(V(0, 0, -lz))
    sh.rotate(V(0, 0, 0), V(1, 0, 0), OPEN_DEG)
    sh.translate(V(0, D, PLATE_TOP - 4.0))
    return sh


caps = None
for k in keys:
    w = k["w"] * layout.PITCH - 1.0
    cx = px0 + margin + k["x"]
    cy = py_top - margin - k["y"]
    cap = Part.makeBox(w, CAP, CAP_H, V(cx - w / 2, cy - CAP / 2, PLATE_TOP))
    caps = cap if caps is None else caps.fuse(cap)
kb_pcb = Part.makeBox(pw, ph, 1.6, V(px0, py_top - ph, PLATE_TOP - PLATE_T - 5.0 - 1.6))
main_pcb = Part.makeBox(90, 60, 1.6, V(W - WALL - 6 - 90, WALL + 6, WALL + 3))
hinge = Part.makeCylinder(4.0, W - 40, V(20, D + 1, PLATE_TOP - 4.0), V(1, 0, 0))

parts += [
    ("Base", base, (0.15, 0.15, 0.17)),
    ("Key plate", plate, (0.75, 0.75, 0.78)),
    ("Keycaps", caps, (0.9, 0.9, 0.85)),
    ("Keyboard PCB", kb_pcb, (0.0, 0.45, 0.2)),
    ("Main PCB", main_pcb, (0.0, 0.35, 0.5)),
    ("18650 cells", cells, (0.2, 0.4, 0.8)),
    ("Hinge", hinge, (0.5, 0.5, 0.5)),
    ("Lid", lid_pose(lid), (0.15, 0.15, 0.17)),
    ("Display", lid_pose(panel), (0.02, 0.02, 0.05)),
    ("Antenna", lid_pose(antenna), (1.0, 0.7, 0.0)),
]
out = []
for name, shape, rgb in parts:
    verts, faces = shape.tessellate(0.3)
    out.append(dict(name=name, color=rgb,
                    v=[round(c, 2) for p in verts for c in (p.x, p.z, -p.y)],   # Y-up for three.js
                    f=[i for t in faces for i in t]))
with open(os.path.join(here, "assembly.json"), "w") as fh:
    json.dump(out, fh)
print("wrote assembly.json")
