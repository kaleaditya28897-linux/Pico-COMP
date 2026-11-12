"""Detailed parametric Pico-COMP case. Run: FreeCADCmd hardware/mechanical/case.py

Frame: X right, Y front(0) -> rear/hinge(D), Z up. Units mm.
Writes pico-comp.FCStd, pico-comp.step, print/*.step + print/*.stl (per printable part),
assembly.json (for build_viewer.py) and ../../docs/case-dimensions.md.
The PCBs come from ../kicad/*.step when present (kicad-cli pcb export step).
"""
import json
import math
import os
import sys

import FreeCAD as App
import Mesh
import MeshPart
import Part

here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
sys.path.insert(0, os.path.join(here, "..", "keyboard"))
import layout  # noqa: E402

V = App.Vector
EX, EY, EZ = V(1, 0, 0), V(0, 1, 0), V(0, 0, 1)

# ---------------------------------------------------------------- parameters
W, D = 250.0, 140.0                 # footprint
WALL = 2.5
R_CORNER = 6.0                      # vertical corner radius
R_EDGE = 1.5                        # bottom / top edge softening
BASE_H = 37.0                       # rim; the lid's screen face rests on it when closed
PLATE_T = 1.5
PLATE_TOP = 30.0                    # plate recessed 7 mm below the rim so the keycaps clear the closed lid
KB_PCB_T = 1.6
KB_PCB_Z = PLATE_TOP - PLATE_T - 3.0 - KB_PCB_T   # Choc: PCB ~3 mm below the plate
LID_H = 14.0
PANEL = (164.9, 124.27, 10.0)       # 7" 1024x600 panel + driver board; thickness is a guess, measure it
ACTIVE = (154.08, 85.92)            # visible area
ANT = (30.0, 8.0, 1.0)
ANT_POCKET = (34.0, 12.0, 4.0)
CELL_D, CELL_L = 18.6, 65.2         # 18650 with wrap
RIB = 1.2
M2_PILOT, M25_HOLE = 1.7, 2.7       # self-tapping pilot / clearance
MB_W, MB_H = 152.0, 68.0            # main PCB
MB_Z = WALL + 4.0                   # PCB underside on 4 mm standoffs
FEET = [(22, 22), (W - 22, 22), (22, D - 22), (W - 22, D - 22)]

doc = App.newDocument("PicoComp")
lz = BASE_H                         # lid is modelled flat (screen face up) starting at this height
LID_D = D


def add(name, shape):
    o = doc.addObject("Part::Feature", name)
    o.Shape = shape
    return o


def box(x, y, z, dx, dy, dz):
    return Part.makeBox(dx, dy, dz, V(x, y, z))


def cyl(r, h, x, y, z, axis=EZ):
    return Part.makeCylinder(r, h, V(x, y, z), axis)


def lid_pose(shape, deg):
    """Rotate a flat lid-frame shape (screen up) about the hinge: 180 = closed on the base, 80 = open."""
    sh = shape.copy()
    sh.translate(V(0, 0, -(lz + LID_H)))
    sh.rotate(V(0, 0, 0), EX, deg)
    sh.translate(V(0, HINGE_Y, HINGE_Z))
    return sh


def rounded_box(x, y, z, dx, dy, dz, r, bottom=0.0, top=0.0):
    """Box with vertical corner radius r and optional bottom/top edge fillets."""
    s = box(x, y, z, dx, dy, dz)
    s = s.makeFillet(r, [e for e in s.Edges if abs(e.tangentAt(e.FirstParameter).z) > 0.99])
    for zc, rr in ((z, bottom), (z + dz, top)):
        if rr:
            s = s.makeFillet(rr, [e for e in s.Edges if abs(e.BoundBox.ZMin - zc) < 1e-6 and abs(e.BoundBox.ZMax - zc) < 1e-6])
    return s


# ---------------------------------------------------------------- keyboard geometry
keys = layout.build()
margin = layout.MARGIN
pw = layout.ROW_U * layout.PITCH + 2 * margin
ph = len(layout.ROWS) * layout.PITCH + 2 * margin
px0 = (W - pw) / 2
py_top = D - WALL - 1.0             # plate rear edge (hinge side)
KB_PCB_W, KB_PCB_H = 244.0, 120.0   # hardware/keyboard/gen_pcb.py
MBX0, MBYTOP = W - WALL - 3.0 - MB_W, D - WALL - 6.0   # main PCB top-left corner (case frame)


def pcb_to_case(x, y):              # main-PCB frame (y down, top edge toward hinge) -> case frame
    return MBX0 + x, MBYTOP - y


# ---------------------------------------------------------------- base
base = rounded_box(0, 0, 0, W, D, BASE_H, R_CORNER, bottom=R_EDGE)
cavity = rounded_box(WALL, WALL, WALL, W - 2 * WALL, D - 2 * WALL, BASE_H, R_CORNER - WALL)
base = base.cut(cavity)

# keyboard PCB support: 3 front posts + rear-left post (M2 pilot) and a rear rail
kb_holes = [(px0 + 3.5, py_top - 120 + 3.5), (px0 + KB_PCB_W / 2, py_top - 120 + 3.5),
            (px0 + KB_PCB_W - 3.5, py_top - 120 + 3.5), (px0 + 3.5, py_top - 3.5)]
for hx, hy in kb_holes:
    post = cyl(3.0, KB_PCB_Z - WALL, hx, hy, WALL)
    base = base.fuse(post).cut(cyl(M2_PILOT / 2, 8.0, hx, hy, KB_PCB_Z - 8.0))
base = base.fuse(box(px0, D - WALL - 2.5, WALL, KB_PCB_W, 2.5, KB_PCB_Z - WALL))      # rear rail

# corner reliefs so the square keyboard PCB clears the rounded rear corners
for rx in (WALL, W - WALL - 3.5):
    base = base.cut(box(rx, D - WALL - 4.0, KB_PCB_Z - 0.2, 3.5, 4.0, KB_PCB_T + 0.6))

# main PCB standoffs (M2.5 holes at the PCB corners 3.5 mm in)
for mx, my in [(3.5, 3.5), (MB_W - 3.5, 3.5), (3.5, MB_H - 3.5), (MB_W - 3.5, MB_H - 3.5)]:
    cx0, cy0 = pcb_to_case(mx, my)
    base = base.fuse(cyl(3.5, MB_Z - WALL, cx0, cy0, WALL)).cut(cyl(M2_PILOT / 2 + 0.1, 6.0, cx0, cy0, MB_Z - 6.0))

# 18650 cradle: 4 cells along Y, separators and end stops
CELL_X0, CELL_Y0, CELL_GAP = WALL + 9.0, WALL + 6.0, 1.4
cell_cx = [CELL_X0 + CELL_D / 2 + i * (CELL_D + CELL_GAP) for i in range(4)]
CELL_Z = WALL + CELL_D / 2
bay_w = 4 * CELL_D + 3 * CELL_GAP
for i in range(5):
    xs = CELL_X0 - CELL_GAP / 2 - 0.5 + i * (CELL_D + CELL_GAP)       # 1.0 mm rib centred in each gap / at each end
    for ys in (CELL_Y0 + 2.0, CELL_Y0 + CELL_L - 12.0):
        base = base.fuse(box(xs, ys, WALL, 1.0, 10.0, CELL_Z - 1.0))                  # saddle ribs
base = base.fuse(box(CELL_X0 - 1.2, CELL_Y0 + CELL_L, WALL, bay_w + 2.4, 1.5, CELL_D * 0.8))   # rear end stop (holder contacts)
base = base.fuse(box(CELL_X0 - 1.2, CELL_Y0 - 1.5, WALL, bay_w + 2.4, 1.5, CELL_D * 0.8))      # front end stop

# connector cutouts (right wall: USB-C J1 + microSD J9; rear wall: HDMI J6)
ux, uy = pcb_to_case(MB_W, 16.0)
sx, sy = pcb_to_case(MB_W, 53.0)
hx_, hy_ = pcb_to_case(122.0, 0.0)
PCB_TOP = MB_Z + 1.6
base = base.cut(rounded_box(W - WALL - 1.5, uy - 5.0, PCB_TOP + 0.3, WALL + 4, 10.0, 3.6, 1.2))          # USB-C 9x3.3
base = base.cut(box(W - WALL - 1.5, sy - 7.0, PCB_TOP + 0.2, WALL + 4, 14.0, 2.4))                         # microSD slot
base = base.cut(box(hx_ - 8.5, D - WALL - 1.5, PCB_TOP + 0.2, 17.0, WALL + 4, 6.6))                        # HDMI-A 15x5.5
# cable slot for panel HDMI + power leads at the hinge
base = base.cut(box(hx_ - 12.0, D - WALL - 1.5, BASE_H - 8.0, 24.0, WALL + 4, 8.5))

# underside: rubber feet pockets, ventilation slots, M2 screw counterbores
for fx, fy in FEET:
    base = base.cut(cyl(6.0, 1.2, fx, fy, 0.0))
for i in range(8):
    base = base.cut(rounded_box(MBX0 + 20 + i * 14, MBYTOP - 45.0, -0.1, 3.0, 36.0, WALL + 0.2, 1.4))
base = base.cut(box(W / 2 - 22, D / 2 - 15, 0.6, 44, 30, 0.5))                                             # label recess
# front finger notch to open the lid
base = base.cut(box(W / 2 - 20, -0.1, BASE_H - 2.5, 40, WALL + 0.2, 2.6))

# hinge: three base knuckles on the rear wall (pin axis along X)
HINGE_Y, HINGE_Z, HK_R, PIN_R = D, BASE_H, 4.0, 1.5   # pin on the rim plane, rear edge
base_knuckles = [(20, 50), (110, 140), (200, 230)]
lid_knuckles = [(55, 105), (145, 195)]
for x0, x1 in base_knuckles:
    k = cyl(HK_R, x1 - x0, x0, HINGE_Y, HINGE_Z, EX).fuse(box(x0, D - WALL + 0.5, HINGE_Z - HK_R, x1 - x0, HINGE_Y - (D - WALL + 0.5), 2 * HK_R))
    base = base.fuse(k)
base = base.cut(cyl(PIN_R, W, 0, HINGE_Y, HINGE_Z, EX))
for x0, x1 in lid_knuckles:                                  # rear-wall notch for the lid knuckles
    base = base.cut(box(x0 - 0.5, D - WALL - 0.1, HINGE_Z - HK_R - 0.5, x1 - x0 + 1.0, WALL + 0.2, HK_R + 0.6))
base = base.removeSplitter()
add("Base", base)

# ---------------------------------------------------------------- key plate (with screw ears)
plate = box(px0, py_top - ph, PLATE_TOP - PLATE_T, pw, ph, PLATE_T)
hcut = layout.CUTOUT / 2
for k in keys:
    cx, cy = px0 + margin + k["x"], py_top - margin - k["y"]
    plate = plate.cut(box(cx - hcut, cy - hcut, PLATE_TOP - PLATE_T - 1, layout.CUTOUT, layout.CUTOUT, PLATE_T + 2))
for hx, hy in kb_holes[:3]:
    plate = plate.cut(cyl(M2_PILOT / 2 + 0.3, PLATE_T + 2, hx, py_top - ph + 1.8, PLATE_TOP - PLATE_T - 1)) if False else plate
add("KeyPlate", plate)

# ---------------------------------------------------------------- lid
lid = rounded_box(0, 0, lz, W, LID_D, LID_H, R_CORNER, bottom=R_EDGE, top=R_EDGE)
lid = lid.cut(rounded_box(WALL, WALL, lz - 0.1, W - 2 * WALL, LID_D - 2 * WALL, LID_H - WALL + 0.1, R_CORNER - WALL))
top_z = lz + LID_H - WALL                                 # underside of the top skin
px, py = (W - PANEL[0]) / 2, (LID_D - PANEL[1]) / 2       # panel footprint in the lid
wx, wy = (W - ACTIVE[0]) / 2, (LID_D - ACTIVE[1]) / 2 + 8.0
lid = lid.cut(rounded_box(wx, wy, top_z - 0.5, ACTIVE[0], ACTIVE[1], WALL + 1, 1.0))   # visible window
lid = lid.cut(box(wx - 1.0, wy - 1.0, lz + LID_H - 0.6, ACTIVE[0] + 2, ACTIVE[1] + 2, 0.7)) if False else lid
# panel retention: four corner clips pressing the panel against the top skin
for cxp, cyp in [(px - 1.2, py + 10), (px + PANEL[0], py + 10), (px - 1.2, py + PANEL[1] - 20), (px + PANEL[0], py + PANEL[1] - 20)]:
    lid = lid.fuse(box(cxp, cyp, top_z - PANEL[2] - 0.5, 1.2, 10, PANEL[2] + 0.5))
# lid screw bosses (4x M2.5) and rear cable notch toward the base cable slot
for bx, by in [(10, 10), (W - 10, 10), (10, LID_D - 10), (W - 10, LID_D - 10)]:
    lid = lid.fuse(cyl(3.2, LID_H - WALL, bx, by, lz)).cut(cyl(M2_PILOT / 2, 7.0, bx, by, lz))
lid = lid.cut(box(hx_ - 12.0, -0.1, lz - 0.1, 24.0, WALL + 0.2, 6.0))
# antenna pocket in the right bezel (beside, never behind, the metal panel frame)
bezel_x0 = (W + PANEL[0]) / 2
bezel_mid = (bezel_x0 + W - WALL) / 2
pocket_y0 = LID_D - WALL - 6.0 - ANT_POCKET[0]
po = box(bezel_mid - ANT_POCKET[1] / 2 - RIB, pocket_y0 - RIB, top_z - ANT_POCKET[2], ANT_POCKET[1] + 2 * RIB, ANT_POCKET[0] + 2 * RIB, ANT_POCKET[2])
pi = box(bezel_mid - ANT_POCKET[1] / 2, pocket_y0, top_z - ANT_POCKET[2] - 0.5, ANT_POCKET[1], ANT_POCKET[0], ANT_POCKET[2] + 1)
lid = lid.fuse(po.cut(pi))
lid = lid.cut(cyl(1.5, 12.0, bezel_mid, pocket_y0 + ANT_POCKET[0] - 2, top_z - 2.5, EY))
for x0, x1 in base_knuckles:                                 # lid-wall notch for the base knuckles
    lid = lid.cut(box(x0 - 0.5, -0.1, lz + LID_H - HK_R - 0.5, x1 - x0 + 1.0, HK_R + 0.3, HK_R + 0.6))
# lid hinge knuckles: pivot on the lid's y=0 screen-face edge
for x0, x1 in lid_knuckles:
    k = cyl(HK_R, x1 - x0, x0, 0, lz + LID_H, EX).fuse(box(x0, 0, lz + LID_H - HK_R, x1 - x0, HK_R, HK_R))
    lid = lid.fuse(k)
lid = lid.cut(cyl(PIN_R, W, 0, 0, lz + LID_H, EX)).removeSplitter()
add("Lid", lid_pose(lid, 180))

antenna = box(bezel_mid - ANT[1] / 2, pocket_y0 + (ANT_POCKET[0] - ANT[0]) / 2, top_z - ANT[2], ANT[1], ANT[0], ANT[2])
add("Antenna", lid_pose(antenna, 180))
panel = box(px, py, top_z - PANEL[2], PANEL[0], PANEL[1], PANEL[2])
add("DisplayPanel", lid_pose(panel, 180))

# ---------------------------------------------------------------- cells, pin, PCBs
cells = None
for cx in cell_cx:
    c = cyl(CELL_D / 2, CELL_L, cx, CELL_Y0, CELL_Z, EY)
    cells = c if cells is None else cells.fuse(c)
add("Cells18650", cells)
pin = cyl(PIN_R, W - 20, 10, HINGE_Y, HINGE_Z, EX)
add("HingePin", pin)


def kicad_pcb(name, x0, ytop, z, fallback):
    path = os.path.join(here, "..", "kicad", name)
    if not os.path.exists(path):
        return fallback
    sh = Part.read(path)
    bb = sh.BoundBox
    sh.translate(V(x0 - bb.XMin, ytop - bb.YMax, z - bb.ZMin))
    return sh


kb_pcb = kicad_pcb("keyboard.step", px0, py_top, KB_PCB_Z, box(px0, py_top - KB_PCB_H, KB_PCB_Z, KB_PCB_W, KB_PCB_H, KB_PCB_T))
main_pcb = kicad_pcb("mainboard.step", MBX0, MBYTOP, MB_Z, box(MBX0, MBYTOP - MB_H, MB_Z, MB_W, MB_H, 1.6))
add("KeyboardPCB", kb_pcb)
add("MainPCB", main_pcb)

doc.recompute()

# ---------------------------------------------------------------- checks
assert pw <= W - 2 * WALL, "key plate wider than base interior"
assert PANEL[0] <= W - 2 * WALL and PANEL[1] <= LID_D - 2 * WALL, "panel does not fit the lid"
assert bezel_x0 + ANT_POCKET[1] / 2 + RIB < W - WALL and bezel_mid - ANT_POCKET[1] / 2 - RIB > bezel_x0, "antenna pocket does not fit the bezel"
assert antenna.common(panel).Volume < 1e-6, "antenna overlaps the panel"
assert cells.BoundBox.ZMax < KB_PCB_Z, "cells collide with the keyboard PCB"
assert cells.BoundBox.XMax < MBX0 - 1.0, "cells collide with the main PCB"
assert cells.common(main_pcb).Volume < 1e-6 and cells.common(kb_pcb).Volume < 1e-6, "cell / PCB interference"
for nm, a, b in (("base/kb PCB", base, kb_pcb), ("base/main PCB", base, main_pcb), ("plate/kb PCB", plate, kb_pcb),
                 ("base/cells", base, cells), ("lid/panel", lid, panel)):
    v = a.common(b).Volume
    print(f"interference {nm}: {v:.2f} mm3")
bb = Part.makeCompound([o.Shape for o in doc.Objects]).BoundBox
print(f"Bounding box {bb.XLength:.1f} x {bb.YLength:.1f} x {bb.ZLength:.1f} mm")

doc.saveAs(os.path.join(here, "pico-comp.FCStd"))
Part.export(doc.Objects, os.path.join(here, "pico-comp.step"))

# per-part manufacturing exports (case parts only, base/lid re-oriented flat for printing)
os.makedirs(os.path.join(here, "print"), exist_ok=True)
lid_flat = lid.copy()
lid_flat.translate(V(0, 0, -lz))
for name, sh in (("base", base), ("lid", lid_flat), ("key_plate", plate)):
    sh.exportStep(os.path.join(here, "print", f"{name}.step"))
    Mesh.Mesh(MeshPart.meshFromShape(Shape=sh, LinearDeflection=0.05, AngularDeflection=0.3)).write(os.path.join(here, "print", f"{name}.stl"))

# ---------------------------------------------------------------- dimensions sheet
dim_rows = [
    ("Overall closed footprint", f"{W:.0f} x {D:.0f} mm"),
    ("Base height (rim) / plate top / wall / floor", f"{BASE_H:.0f} / {PLATE_TOP:.0f} / {WALL} / {WALL} mm"),
    ("Lid height (flat, screen up)", f"{LID_H:.0f} mm"),
    ("Corner radius / edge fillet", f"{R_CORNER} / {R_EDGE} mm"),
    ("Closed height (base rim + lid)", f"{BASE_H + LID_H:.0f} mm"),
    ("Keyboard plate / key pitch", f"{pw:.0f} x {ph:.0f} x {PLATE_T} mm, {layout.PITCH:.0f} mm pitch, {layout.CUTOUT} mm cutouts"),
    ("Keyboard PCB", f"{KB_PCB_W:.0f} x {KB_PCB_H:.0f} x {KB_PCB_T} mm, underside z={KB_PCB_Z:.1f}"),
    ("Main PCB", f"{MB_W:.0f} x {MB_H:.0f} mm, underside z={MB_Z:.1f}, 4x M2.5 standoffs"),
    ("18650 cells", f"4x {CELL_D} x {CELL_L} mm, 2S2P, axis along Y, top z={cells.BoundBox.ZMax:.1f}"),
    ("Display module", f"{PANEL[0]} x {PANEL[1]} x {PANEL[2]} mm (thickness assumed)"),
    ("Visible window", f"{ACTIVE[0]} x {ACTIVE[1]} mm"),
    ("Bezel L/R (panel to lid edge)", f"{(W - PANEL[0]) / 2:.1f} mm each side"),
    ("Hinge", f"pin dia {2 * PIN_R:.0f} mm, knuckle dia {2 * HK_R:.0f} mm, axis at y={HINGE_Y:.0f}, z={HINGE_Z:.0f}"),
    ("Antenna / pocket", f"{ANT[0]} x {ANT[1]} x {ANT[2]} mm in {ANT_POCKET[0]} x {ANT_POCKET[1]} x {ANT_POCKET[2]} mm pocket"),
    ("Ports", "USB-C + microSD on right wall, HDMI cable slot at rear/hinge"),
    ("Feet / vents", "4x dia 12 x 1.2 mm feet pockets, 8 bottom vent slots 3 x 36 mm"),
]
with open(os.path.join(here, "..", "..", "docs", "case-dimensions.md"), "w") as fh:
    fh.write("# Case dimensions (generated by hardware/mechanical/case.py)\n\n| Item | Value |\n|---|---|\n")
    fh.writelines(f"| {a} | {b} |\n" for a, b in dim_rows)
    fh.write("\nPrintable parts are in `hardware/mechanical/print/` (base, lid flat, key plate; STEP + STL).\n")
print("wrote FCStd, STEP, print/*, docs/case-dimensions.md")

# ---------------------------------------------------------------- viewer assembly
OPEN_DEG = 80.0
CAP, CAP_H = 16.0, 6.0


caps = []
for k in keys:
    w = k["w"] * layout.PITCH - 1.0
    cx, cy = px0 + margin + k["x"], py_top - margin - k["y"]
    z0 = PLATE_TOP + 0.5
    cap = box(cx - w / 2, cy - CAP / 2, z0, w, CAP, CAP_H)
    cap = cap.makeChamfer(1.2, [e for e in cap.Edges if abs(e.BoundBox.ZMin - (z0 + CAP_H)) < 1e-6 and abs(e.BoundBox.ZMax - (z0 + CAP_H)) < 1e-6])
    caps.append(cap)
caps = Part.makeCompound(caps)

parts = [
    ("Base", base, (0.15, 0.15, 0.17)),
    ("Key plate", plate, (0.75, 0.75, 0.78)),
    ("Keycaps", caps, (0.9, 0.9, 0.85)),
    ("Keyboard PCB", kb_pcb, (0.0, 0.45, 0.2)),
    ("Main PCB", main_pcb, (0.0, 0.35, 0.5)),
    ("18650 cells", cells, (0.2, 0.4, 0.8)),
    ("Hinge", pin, (0.5, 0.5, 0.5)),
    ("Lid", lid_pose(lid, OPEN_DEG), (0.15, 0.15, 0.17)),
    ("Display", lid_pose(panel, OPEN_DEG), (0.02, 0.02, 0.05)),
    ("Antenna", lid_pose(antenna, OPEN_DEG), (1.0, 0.7, 0.0)),
]
out = []
for name, shape, rgb in parts:
    verts, faces = shape.tessellate(0.3)
    out.append(dict(name=name, color=rgb,
                    v=[round(c, 2) for p in verts for c in (p.x, p.z, -p.y)],
                    f=[i for t in faces for i in t]))
with open(os.path.join(here, "assembly.json"), "w") as fh:
    json.dump(out, fh)
print("wrote assembly.json")
