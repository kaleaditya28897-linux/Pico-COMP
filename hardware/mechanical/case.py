"""Detailed parametric Pico-COMP assembly. Run: FreeCADCmd hardware/mechanical/case.py

Frame: X right, Y front(0) -> rear/hinge(D), Z up. Units mm. Board placement: ../placement.py.
Every physical part is its own object, grouped in the tree (Case, Display, Battery, Mainboard,
Keyboard, Keycaps, Fasteners, Cables); each board component comes from its KiCad 3D model via
../kicad/<board>_parts.json (python3 hardware/kicad/export_parts.py).

Writes pico-comp.FCStd, pico-comp.step, print/*.step|stl (printable case parts), keycaps/*
(one file per keycap + legend inlay), assembly.json (for build_viewer.py) and
../../docs/case-dimensions.md. Prints an interference report and fails on real collisions.
"""
import json
import os
import sys

import FreeCAD as App
import Mesh
import MeshPart
import Part

here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
for p in (here, os.path.join(here, ".."), os.path.join(here, "..", "keyboard")):
    sys.path.insert(0, p)
import keycaps  # noqa: E402
import layout  # noqa: E402
import pcb3d  # noqa: E402
import placement as PL  # noqa: E402

V = App.Vector
EX, EY, EZ = V(1, 0, 0), V(0, 1, 0), V(0, 0, 1)
KICAD = os.path.join(here, "..", "kicad")

# ---------------------------------------------------------------- parameters
W, D, WALL = PL.CASE_W, PL.CASE_D, PL.WALL
R_CORNER = 6.0                      # vertical corner radius
R_EDGE = 1.5                        # bottom / top edge softening
BASE_H = 37.0                       # rim; the lid's screen face rests on it when closed
PLATE_T = 1.2                       # Kailh CPG135001D01: plate clip zone 1.3 mm, 1.2 mm plate
PLATE_TOP = 29.0                    # plate recessed 8 mm below the rim so the keycaps clear the closed lid
KB_PCB_T = 1.6
PCB_TO_PLATE = 2.2                  # Kailh CPG135001D01 drawing: PCB top to plate underside
KB_PCB_Z = PLATE_TOP - PLATE_T - PCB_TO_PLATE - KB_PCB_T
STEM_TOP = KB_PCB_Z + KB_PCB_T + 8.0   # Choc V1 stem top at rest, 8 mm above the PCB (matches the STEP)
LID_H = 14.0
PANEL = (164.9, 124.27, 10.0)       # 7" 1024x600 panel + driver board; thickness is a guess, measure it
ACTIVE = (154.08, 85.92)            # visible area
CELL_D, CELL_L = 18.6, 65.2         # 18650 with wrap
M2_PILOT, M25_PILOT = 1.7, 2.1      # self-tapping pilots
MB_Z = WALL + 4.0                   # main PCB underside on 4 mm standoffs
FEET = [(22, 22), (W - 22, 22), (22, D - 22), (W - 22, D - 22)]
PALM_T = 1.5                        # palm rest deck, flush with the plate top

mb = json.load(open(os.path.join(KICAD, "mainboard.json")))
MB_W, MB_H = mb["board"]
assert (MB_W, MB_H) == (PL.MB_W, PL.MB_H), "placement.py and the mainboard disagree"
PCB_TOP = MB_Z + 1.6

doc = App.newDocument("PicoComp")
lz = BASE_H                         # lid is modelled flat (screen face up) starting at this height
LID_D = D
groups = {}


def group(name):
    if name not in groups:
        groups[name] = doc.addObject("App::DocumentObjectGroup", name)
    return groups[name]


def add(name, shape, grp, label=None):
    o = doc.addObject("Part::Feature", name)
    o.Label = label or name
    o.Shape = shape
    group(grp).addObject(o)
    return o


def box(x, y, z, dx, dy, dz):
    return Part.makeBox(dx, dy, dz, V(x, y, z))


def cyl(r, h, x, y, z, axis=EZ):
    return Part.makeCylinder(r, h, V(x, y, z), axis)


def rounded_box(x, y, z, dx, dy, dz, r, bottom=0.0, top=0.0):
    """Box with vertical corner radius r and optional bottom/top edge fillets."""
    s = box(x, y, z, dx, dy, dz)
    s = s.makeFillet(r, [e for e in s.Edges if abs(e.tangentAt(e.FirstParameter).z) > 0.99])
    for zc, rr in ((z, bottom), (z + dz, top)):
        if rr:
            s = s.makeFillet(rr, [e for e in s.Edges if abs(e.BoundBox.ZMin - zc) < 1e-6 and abs(e.BoundBox.ZMax - zc) < 1e-6])
    return s


def mb_bbox_case(ref):
    """Case-frame (x0, y0, x1, y1) of a mainboard connector from mainboard.json."""
    x0, y0, x1, y1 = mb["connectors"][ref]["bbox"]
    ax, ay = PL.mb_to_case(x0, y1)
    bx, by = PL.mb_to_case(x1, y0)
    return ax, ay, bx, by


HINGE_Y, HINGE_Z, HK_R, PIN_R = D, BASE_H, 4.0, 1.5   # pin on the rim plane, rear edge
base_knuckles = [(20, 50), (110, 140), (200, 230)]
lid_knuckles = [(55, 105), (145, 195)]


def lid_pose(shape, deg):
    """Rotate a flat lid-frame shape (screen up) about the hinge: 180 = closed on the base, 80 = open."""
    sh = shape.copy()
    sh.translate(V(0, 0, -(lz + LID_H)))
    sh.rotate(V(0, 0, 0), EX, deg)
    sh.translate(V(0, HINGE_Y, HINGE_Z))
    return sh


# ---------------------------------------------------------------- keyboard geometry
keys = layout.build()
margin = layout.MARGIN
pw = layout.ROW_U * layout.PITCH + 2 * margin
ph = len(layout.ROWS) * layout.PITCH + 2 * margin
px0, py_top = PL.KB_X0, PL.KB_YTOP                     # plate and keyboard PCB share the rear-left corner
plate_front = py_top - ph
kb_holes = [PL.kb_to_case(x, y) for x, y in PL.KB_HOLES]
mb_holes = [PL.mb_to_case(x, y) for x, y in mb["holes"]]

# ---------------------------------------------------------------- base
base = rounded_box(0, 0, 0, W, D, BASE_H, R_CORNER, bottom=R_EDGE)
base = base.cut(rounded_box(WALL, WALL, WALL, W - 2 * WALL, D - 2 * WALL, BASE_H, R_CORNER - WALL))

# keyboard PCB posts (M2 pilot) under the front-strip holes, and the rear rail the rear edge rests on
for hx, hy in kb_holes:
    base = base.fuse(cyl(3.0, KB_PCB_Z - WALL, hx, hy, WALL)).cut(cyl(M2_PILOT / 2, 8.0, hx, hy, KB_PCB_Z - 8.0))
base = base.fuse(box(px0, D - WALL - 2.5, WALL, PL.KB_W, 2.5, KB_PCB_Z - WALL))
for rx in (WALL, W - WALL - 3.5):                      # corner reliefs for the square PCB at the rounded corners
    base = base.cut(box(rx, D - WALL - 4.0, KB_PCB_Z - 0.2, 3.5, 4.0, KB_PCB_T + 0.6))

# main PCB standoffs at the board's mounting holes (M2.5)
for cx0, cy0 in mb_holes:
    base = base.fuse(cyl(3.5, MB_Z - WALL, cx0, cy0, WALL)).cut(cyl(M25_PILOT / 2, 6.0, cx0, cy0, MB_Z - 6.0))

# 18650 cradle: 4 cells along Y, saddle ribs and end stops
CELL_X0, CELL_Y0, CELL_GAP = WALL + 9.0, WALL + 6.0, 1.4
cell_cx = [CELL_X0 + CELL_D / 2 + i * (CELL_D + CELL_GAP) for i in range(4)]
CELL_Z = WALL + CELL_D / 2
bay_w = 4 * CELL_D + 3 * CELL_GAP
for i in range(5):
    xs = CELL_X0 - CELL_GAP / 2 - 0.5 + i * (CELL_D + CELL_GAP)
    for ys in (CELL_Y0 + 2.0, CELL_Y0 + CELL_L - 12.0):
        base = base.fuse(box(xs, ys, WALL, 1.0, 10.0, CELL_Z - 1.0))
base = base.fuse(box(CELL_X0 - 1.2, CELL_Y0 + CELL_L, WALL, bay_w + 2.4, 1.5, CELL_D * 0.8))
base = base.fuse(box(CELL_X0 - 1.2, CELL_Y0 - 1.5, WALL, bay_w + 2.4, 1.5, CELL_D * 0.8))

# right-wall port openings, positioned from the real connectors (USB-C J1, microSD J9)
ux0, uy0, ux1, uy1 = mb_bbox_case("J1")
sx0, sy0, sx1, sy1 = mb_bbox_case("J9")
uyc, syc = (uy0 + uy1) / 2, (sy0 + sy1) / 2
base = base.cut(rounded_box(W - WALL - 1.5, uyc - 4.9, PCB_TOP + 1.63 - 1.9, WALL + 4, 9.8, 3.8, 1.5))  # USB-C 8.94 x 3.26
base = base.cut(box(W - WALL - 1.5, syc - 6.5, PCB_TOP + 0.1, WALL + 4, 13.0, 2.2))                     # microSD
base = base.cut(box(W - 0.8, syc - 5.0, PCB_TOP - 2.0, 1.0, 10.0, 6.0))                                   # finger scoop
# HDMI (J6) is internal: the panel cable leaves J6 rearward and rises through this slot to the lid
hx0, hy0, hx1, hy1 = mb_bbox_case("J6")
hx_ = (hx0 + hx1) / 2
base = base.cut(box(hx_ - 12.0, D - WALL - 1.5, BASE_H - 8.0, 24.0, WALL + 4, 8.5))

# underside: rubber feet pockets, vents under the main board, label recess
for fx, fy in FEET:
    base = base.cut(cyl(6.0, 1.2, fx, fy, 0.0))
for i in range(8):
    base = base.cut(rounded_box(PL.MB_X0 + 20 + i * 14, PL.MB_YTOP - 50.0, -0.1, 3.0, 36.0, WALL + 0.2, 1.4))
base = base.cut(box(W / 2 - 22, D / 2 - 15, -0.1, 44, 30, 0.6))
base = base.cut(box(W / 2 - 20, -0.1, BASE_H - 2.5, 40, WALL + 0.2, 2.6))          # front finger notch
# ledge along the front wall that the palm rest's front edge sits on
base = base.fuse(box(WALL, WALL, PLATE_TOP - PALM_T - 1.5, W - 2 * WALL, 1.5, 1.5))

# hinge: three base knuckles on the rear wall (pin axis along X)
for x0, x1 in base_knuckles:
    base = base.fuse(cyl(HK_R, x1 - x0, x0, HINGE_Y, HINGE_Z, EX).fuse(
        box(x0, D - WALL + 0.5, HINGE_Z - HK_R, x1 - x0, HINGE_Y - (D - WALL + 0.5), 2 * HK_R)))
base = base.cut(cyl(PIN_R, W, 0, HINGE_Y, HINGE_Z, EX))
for x0, x1 in lid_knuckles:
    base = base.cut(box(x0 - 0.5, D - WALL - 0.1, HINGE_Z - HK_R - 0.5, x1 - x0 + 1.0, WALL + 0.2, HK_R + 0.6))
base = base.removeSplitter()
add("Base", base, "Case")

# ---------------------------------------------------------------- key plate
plate = rounded_box(px0, plate_front, PLATE_TOP - PLATE_T, pw, ph, PLATE_T, PL.PLATE_R)
hcut = layout.CUTOUT / 2
cuts = []
for k in keys:
    cx, cy = px0 + margin + k["x"], py_top - margin - k["y"]
    cuts.append(box(cx - hcut, cy - hcut, PLATE_TOP - PLATE_T - 1, layout.CUTOUT, layout.CUTOUT, PLATE_T + 2))
sw_, sh_ = layout.STAB_CUTOUT
for _, x, y in layout.stabs(keys):                     # Kailh PG1350 plate-mount stabilizer openings
    cx, cy = px0 + margin + x, py_top - margin - y
    cuts.append(box(cx - sw_ / 2, cy - sh_ / 2, PLATE_TOP - PLATE_T - 1, sw_, sh_, PLATE_T + 2))
plate = plate.cut(Part.makeCompound(cuts))
add("KeyPlate", plate, "Case", "Key plate (laser cut, see plate.dxf)")

# ---------------------------------------------------------------- palm rest (separate printed part)
pr_y0, pr_y1 = WALL + 0.3, plate_front - 0.3
palm = rounded_box(WALL + 0.3, pr_y0, PLATE_TOP - PALM_T, W - 2 * WALL - 0.6, pr_y1 - pr_y0, PALM_T, R_CORNER - WALL - 0.3)
kb_top = KB_PCB_Z + KB_PCB_T
for hx, hy in kb_holes:                                  # bosses clamp the keyboard PCB onto its posts
    palm = palm.fuse(cyl(3.0, PLATE_TOP - PALM_T - kb_top, hx, hy, kb_top))
    palm = palm.cut(cyl(1.1, 20, hx, hy, kb_top - 1)).cut(
        Part.makeCone(1.1, 2.1, 1.0, V(hx, hy, PLATE_TOP - 1.0)))          # M2 countersunk
palm = palm.removeSplitter()
palm_obj = add("PalmRest", palm, "Case", "Palm rest (printed, plastic over the RM2 antenna)")

# ---------------------------------------------------------------- lid
lid = rounded_box(0, 0, lz, W, LID_D, LID_H, R_CORNER, bottom=R_EDGE, top=R_EDGE)
lid = lid.cut(rounded_box(WALL, WALL, lz - 0.1, W - 2 * WALL, LID_D - 2 * WALL, LID_H - WALL + 0.1, R_CORNER - WALL))
top_z = lz + LID_H - WALL
px, py = (W - PANEL[0]) / 2, (LID_D - PANEL[1]) / 2
wx, wy = (W - ACTIVE[0]) / 2, (LID_D - ACTIVE[1]) / 2 + 8.0
lid = lid.cut(rounded_box(wx, wy, top_z - 0.5, ACTIVE[0], ACTIVE[1], WALL + 1, 1.0))
for cxp, cyp in [(px - 1.2, py + 10), (px + PANEL[0], py + 10), (px - 1.2, py + PANEL[1] - 20), (px + PANEL[0], py + PANEL[1] - 20)]:
    lid = lid.fuse(box(cxp, cyp, top_z - PANEL[2] - 0.5, 1.2, 10, PANEL[2] + 0.5))
LID_BOSSES = [(10, 10), (W - 10, 10), (10, LID_D - 10), (W - 10, LID_D - 10)]
for bx, by in LID_BOSSES:
    lid = lid.fuse(cyl(3.2, LID_H - WALL, bx, by, lz)).cut(cyl(M2_PILOT / 2, 7.0, bx, by, lz))
lid = lid.cut(box(hx_ - 12.0, -0.1, lz - 0.1, 24.0, WALL + 0.2, 6.0))   # cable notch at the hinge
for x0, x1 in base_knuckles:
    lid = lid.cut(box(x0 - 0.5, -0.1, lz + LID_H - HK_R - 0.5, x1 - x0 + 1.0, HK_R + 0.3, HK_R + 0.6))
for x0, x1 in lid_knuckles:
    lid = lid.fuse(cyl(HK_R, x1 - x0, x0, 0, lz + LID_H, EX).fuse(box(x0, 0, lz + LID_H - HK_R, x1 - x0, HK_R, HK_R)))
lid = lid.cut(cyl(PIN_R, W, 0, 0, lz + LID_H, EX)).removeSplitter()
# engraved "Pico COMP" badge on the lid back (outer face, z = lz when modelled flat)
badge = keycaps._centred("Pico COMP", 9.0, W / 2, LID_D / 2, 0)
if badge is not None:
    badge = badge.extrude(V(0, 0, 0.5))
    badge.translate(V(0, 0, lz - 0.01))
    lid = lid.cut(badge)
add("Lid", lid_pose(lid, 180), "Case")
# hotkey legend sticker on the bezel at the base of the screen (lid y = 0 is the hinge side)
sticker = box(wx, 6.0, lz + LID_H - 0.01, ACTIVE[0], wy - 10.0, 0.12)
add("HotkeySticker", lid_pose(sticker, 180), "Case", "Hotkey legend sticker (print from the central hotkey table)")
pin = cyl(PIN_R, W - 20, 10, HINGE_Y, HINGE_Z, EX)
add("HingePin", pin, "Case", "Hinge pin 3 mm steel rod")

# ---------------------------------------------------------------- display
panel = box(px, py, top_z - PANEL[2], PANEL[0], PANEL[1], PANEL[2])
active = box(wx, wy, top_z - 0.05, ACTIVE[0], ACTIVE[1], 0.05)
add("DisplayPanel", lid_pose(panel, 180), "Display", "7in 1024x600 HDMI panel module (envelope)")
add("DisplayActiveArea", lid_pose(active, 180), "Display", "Display active area")

# ---------------------------------------------------------------- battery
cells = []
for i, cx in enumerate(cell_cx):
    c = cyl(CELL_D / 2, CELL_L, cx, CELL_Y0, CELL_Z, EY)
    cells.append(c)
    add(f"Cell{i + 1}", c, "Battery", f"18650 cell {i + 1} (2S2P pack)")
bms = box(CELL_X0, CELL_Y0 + CELL_L + 2.0, WALL, 50.0, 14.0, 3.0)
add("BMS", bms, "Battery", "2S BMS board (pack maker supplied, envelope)")
cells_all = Part.makeCompound(cells)

# ---------------------------------------------------------------- PCBs, one object per component
mpcb, mparts, mworst = pcb3d.build(doc, os.path.join(KICAD, "mainboard_parts.json"), PL.MB_X0, PL.MB_YTOP, MB_Z,
                                   group("Mainboard"), "MainPCB", skip_npth_below=2.0)
kpcb, kparts, kworst = pcb3d.build(doc, os.path.join(KICAD, "keyboard_parts.json"), PL.KB_X0, PL.KB_YTOP, KB_PCB_Z,
                                   group("Keyboard"), "KeyboardPCB")
print("model-to-footprint offsets (largest):", mworst, kworst)
# pocket under the palm rest for the keyboard header J1 and the jumper plugs on its pins (0.6 mm skin left)
jb = kparts["J1"].BoundBox
palm = palm.cut(box(jb.XMin - 1.0, WALL + 0.2, kb_top, jb.XLength + 2.0, jb.YMax + 1.0 - WALL - 0.2,
                    PLATE_TOP - 0.6 - kb_top)).removeSplitter()
palm_obj.Shape = palm

# ---------------------------------------------------------------- keycaps
caps = []
for k in keys:
    cx, cy = px0 + margin + k["x"], py_top - margin - k["y"]
    cap, inlay = keycaps.make(k["name"], k["w"], layout.PITCH, cx, cy, STEM_TOP)
    tag = f"Keycap_r{k['row']}c{k['col']:02d}"
    add(tag, cap, "Keycaps", f"Keycap {k['name']} ({k['w']:g}u)")
    if inlay is not None:
        add(tag + "_legend", inlay, "Keycaps", f"Legend {k['name']}")
    caps.append(cap)
caps_all = Part.makeCompound(caps)

# ---------------------------------------------------------------- fasteners, feet, cables
for i, (hx, hy) in enumerate(mb_holes):        # M2.5 x 6 pan head into the standoffs
    sc = cyl(2.25, 1.8, hx, hy, PCB_TOP).fuse(cyl(1.25, 6.0, hx, hy, PCB_TOP - 6.0))
    add(f"ScrewMB{i + 1}", sc, "Fasteners", "M2.5x6 pan head (main board)")
for i, (hx, hy) in enumerate(kb_holes):        # M2 x 10 countersunk through palm rest + keyboard PCB
    sc = Part.makeCone(1.0, 1.9, 0.9, V(hx, hy, PLATE_TOP - 0.9)).fuse(cyl(1.0, 10.0, hx, hy, PLATE_TOP - 10.0))
    add(f"ScrewKB{i + 1}", sc, "Fasteners", "M2x10 countersunk (palm rest / keyboard)")
for i, (bx, by) in enumerate(LID_BOSSES):
    add(f"ScrewLid{i + 1}", lid_pose(cyl(1.0, 6.0, bx, by, lz + 0.5), 180), "Fasteners", "M2x6 (lid back)")
for i, (fx, fy) in enumerate(FEET):
    add(f"Foot{i + 1}", cyl(5.8, 2.0, fx, fy, -0.8), "Fasteners", "Rubber foot 12 x 2 mm")

jx0, jy0, jx1, jy1 = mb_bbox_case("J6")         # HDMI plug + flat cable rising to the slot
plug = box(hx_ - 7.5, jy1 + 0.5, PCB_TOP + 0.3, 15.0, 22.0, 6.0)
cable = box(hx_ - 7.0, jy1 + 22.5, PCB_TOP + 2.0, 14.0, D - WALL - 3.0 - (jy1 + 22.5), 1.0)
riser = box(hx_ - 7.0, D - WALL - 3.0, PCB_TOP + 2.0, 14.0, 1.0, BASE_H - PCB_TOP - 2.0)
add("HDMIPlug", plug, "Cables", "Slim HDMI-A plug (envelope)")
add("HDMICable", cable.fuse(riser), "Cables", "HDMI FPC/flat cable to the panel (routing envelope)")
kx0, ky0, kx1, ky1 = mb_bbox_case("J11")
ribbon = box(kx0, 6.0, PCB_TOP + 0.5, kx1 - kx0, ky0 - 6.0, 2.5)
add("KeyboardCable", ribbon, "Cables", "20-way 2.54 mm F-F jumper bundle, J11 <-> keyboard J1 (envelope)")
doc.recompute()

# ---------------------------------------------------------------- checks
assert pw <= W - 2 * WALL, "key plate wider than base interior"
assert PANEL[0] <= W - 2 * WALL and PANEL[1] <= LID_D - 2 * WALL, "panel does not fit the lid"
assert max(c.BoundBox.ZMax for c in cells) < KB_PCB_Z - 1.0, "cells collide with the keyboard"
assert max(c.BoundBox.XMax for c in cells) < PL.MB_X0 - 1.0, "cells collide with the main PCB"
cap_top = caps_all.BoundBox.ZMax
assert cap_top < BASE_H - 0.5, f"keycaps ({cap_top:.1f}) hit the closed lid (rim {BASE_H})"

solids = {"Base": base, "KeyPlate": plate, "PalmRest": palm, "Lid": lid_pose(lid, 180),
          "Display": lid_pose(panel, 180), "Cells": cells_all, "BMS": bms, "MainPCB": mpcb, "KeyboardPCB": kpcb,
          "Keycaps": caps_all, "HDMIPlug": plug}
solids.update({f"MB:{r}": s for r, s in mparts.items()})
solids.update({f"KB:{r}": s for r, s in kparts.items()})
# expected contact: switches pass through the plate cutouts and sit on their PCB, parts sit on their PCB
ALLOWED = {("KeyPlate", "KB:SW"), ("Keycaps", "KB:SW"), ("KeyPlate", "KB:ST"), ("Keycaps", "KB:ST"),
           ("KeyboardPCB", "KB:"), ("MainPCB", "MB:")}
names = list(solids)
bbs = {n: solids[n].BoundBox for n in names}
hits = []
for i, a in enumerate(names):
    for b in names[i + 1:]:
        if any((a.startswith(x) and b.startswith(y)) or (b.startswith(x) and a.startswith(y)) for x, y in ALLOWED):
            continue
        if a[:3] == b[:3] and a[:3] in ("MB:", "KB:"):
            continue                                    # parts on the same board: checked by KiCad courtyards
        if not bbs[a].intersect(bbs[b]):
            continue
        v = solids[a].common(solids[b]).Volume
        if v > 0.5:
            hits.append((round(v, 2), a, b))
hits.sort(reverse=True)
print("interference report (> 0.5 mm3):", hits if hits else "none")

bb = Part.makeCompound([o.Shape for o in doc.Objects if hasattr(o, "Shape") and not o.Shape.isNull()]).BoundBox
print(f"Bounding box {bb.XLength:.1f} x {bb.YLength:.1f} x {bb.ZLength:.1f} mm, {len(doc.Objects)} objects")

doc.saveAs(os.path.join(here, "pico-comp.FCStd"))
Part.export([o for o in doc.Objects if o.TypeId == "Part::Feature"], os.path.join(here, "pico-comp.step"))

# per-part manufacturing exports (printable case parts, base/lid flat)
os.makedirs(os.path.join(here, "print"), exist_ok=True)
lid_flat = lid.copy()
lid_flat.translate(V(0, 0, -lz))
palm_flat = palm.copy()
palm_flat.rotate(V(0, 0, PLATE_TOP), EX, 180)          # print deck-down
palm_flat.translate(V(0, 0, -palm_flat.BoundBox.ZMin))
for name, sh in (("base", base), ("lid", lid_flat), ("key_plate", plate), ("palm_rest", palm_flat)):
    sh.exportStep(os.path.join(here, "print", f"{name}.step"))
    Mesh.Mesh(MeshPart.meshFromShape(Shape=sh, LinearDeflection=0.05, AngularDeflection=0.3)).write(
        os.path.join(here, "print", f"{name}.stl"))
ncaps = keycaps.export_all(keys, layout.PITCH, os.path.join(here, "keycaps"))
print(f"wrote print/* and {ncaps} keycaps")

# ---------------------------------------------------------------- dimensions sheet
dim_rows = [
    ("Overall closed footprint", f"{W:.0f} x {D:.0f} mm"),
    ("Base height (rim) / plate top / wall / floor", f"{BASE_H:.0f} / {PLATE_TOP:.0f} / {WALL} / {WALL} mm"),
    ("Lid height (flat, screen up)", f"{LID_H:.0f} mm"),
    ("Closed height (base rim + lid)", f"{BASE_H + LID_H:.0f} mm"),
    ("Keyboard plate / key pitch", f"{pw:.0f} x {ph:.0f} x {PLATE_T} mm, {layout.PITCH:.0f} mm pitch, {layout.CUTOUT} mm cutouts"),
    ("Keyboard PCB", f"{PL.KB_W:.0f} x {PL.KB_H:.0f} x {KB_PCB_T} mm, underside z={KB_PCB_Z:.1f}, 3x M2 (front strip)"),
    ("Keycaps", f"Choc V1, {layout.PITCH - keycaps.GAP:.0f} mm per 1u, {keycaps.CAP_T} mm tall, top z={cap_top:.1f} "
                f"({BASE_H - cap_top:.1f} mm under the closed lid)"),
    ("Main PCB", f"{MB_W:.0f} x {MB_H:.0f} mm at x={PL.MB_X0:.1f}, front edge y={PL.MB_YTOP - MB_H:.1f}, "
                 f"underside z={MB_Z:.1f}, 4x M2.5"),
    ("Palm rest", f"{W - 2 * WALL - 0.6:.0f} x {pr_y1 - pr_y0:.1f} x {PALM_T} mm deck, separate print, covers the RM2 antenna"),
    ("18650 cells", f"4x {CELL_D} x {CELL_L} mm, 2S2P, axis along Y"),
    ("Display module", f"{PANEL[0]} x {PANEL[1]} x {PANEL[2]} mm (thickness assumed)"),
    ("Visible window", f"{ACTIVE[0]} x {ACTIVE[1]} mm"),
    ("Hinge", f"pin dia {2 * PIN_R:.0f} mm, knuckle dia {2 * HK_R:.0f} mm, axis at y={HINGE_Y:.0f}, z={HINGE_Z:.0f}"),
    ("Ports", "USB-C + microSD on the right wall (from the board), HDMI internal via the hinge cable slot"),
    ("Wi-Fi", "RM2 onboard antenna at the main board's front edge, under the plastic palm rest"),
    ("Feet / vents", "4x dia 12 x 1.2 mm feet pockets, 8 bottom vent slots 3 x 36 mm"),
]
with open(os.path.join(here, "..", "..", "docs", "case-dimensions.md"), "w") as fh:
    fh.write("# Case dimensions (generated by hardware/mechanical/case.py)\n\n| Item | Value |\n|---|---|\n")
    fh.writelines(f"| {a} | {b} |\n" for a, b in dim_rows)
    fh.write("\nPrintable parts: `hardware/mechanical/print/` (base, lid, palm rest, key plate). "
             "Keycaps: `hardware/mechanical/keycaps/`.\n")

# ---------------------------------------------------------------- viewer assembly
OPEN_DEG = 80.0
parts = [
    ("Base", base, (0.15, 0.15, 0.17)), ("Palm rest", palm, (0.2, 0.2, 0.22)),
    ("Key plate", plate, (0.75, 0.75, 0.78)), ("Keycaps", caps_all, (0.9, 0.9, 0.85)),
    ("Keyboard PCB", kpcb, (0.0, 0.45, 0.2)), ("Keyboard parts", Part.makeCompound(list(kparts.values())), (0.8, 0.5, 0.2)),
    ("Main PCB", mpcb, (0.0, 0.35, 0.5)), ("Main board parts", Part.makeCompound(list(mparts.values())), (0.6, 0.6, 0.6)),
    ("18650 cells", cells_all, (0.2, 0.4, 0.8)), ("Hinge", pin, (0.5, 0.5, 0.5)),
    ("Lid", lid_pose(lid, OPEN_DEG), (0.15, 0.15, 0.17)), ("Display", lid_pose(panel, OPEN_DEG), (0.02, 0.02, 0.05)),
]
out = []
for name, shape, rgb in parts:
    verts, faces = shape.tessellate(0.3)
    out.append(dict(name=name, color=rgb, v=[round(c, 2) for p in verts for c in (p.x, p.z, -p.y)],
                    f=[i for t in faces for i in t]))
with open(os.path.join(here, "assembly.json"), "w") as fh:
    json.dump(out, fh)
print("wrote FCStd, STEP, assembly.json, docs/case-dimensions.md")
