"""Build STEP models for parts with no model in the KiCad library.

Run: FreeCADCmd hardware/kicad/make_3d.py
Writes hardware/kicad/pico-comp.3dshapes/*.step. KiCad model frame: origin = footprint origin,
X right, Y up (footprint Y is down, so footprint y -> model -y), Z up from the board surface.
Bodies are envelope models from the datasheet outlines, good for fit checks rather than renders.
"""
import os

import FreeCAD as App
import Import
import Part

V = App.Vector
here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
out_dir = os.path.join(here, "pico-comp.3dshapes")
os.makedirs(out_dir, exist_ok=True)


def box(x0, y0, x1, y1, z0, z1):
    """Box from footprint coordinates (y down) to model coordinates (y up)."""
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, -y1, z0))


def save(name, shapes):
    doc = App.newDocument(name.replace("-", "_").replace(".", "_"))
    objs = []
    for i, (label, sh) in enumerate(shapes):
        o = doc.addObject("Part::Feature", f"P{i}")
        o.Label = label
        o.Shape = sh
        objs.append(o)
    Import.export(objs, os.path.join(out_dir, name + ".step"))
    App.closeDocument(doc.Name)
    print("wrote", name + ".step")


def qfn(name, size, h, ep):
    s = size / 2
    body = box(-s, -s, s, s, 0.0, h)
    dot = Part.makeCylinder(0.3, 0.02, V(-s + 0.6, s - 0.6, h))
    save(name, [("body", body.cut(dot)), ("pin1", dot)])


qfn("QFN-60-1EP_7x7mm_P0.4mm_EP3.4x3.4mm", 7.0, 0.85, 3.4)
qfn("Texas_RQM0029A_VQFN-29_4x4mm_P0.4mm", 4.0, 0.9, 0)

# Bourns SRP7028A: 7.3 x 6.6 x 2.8 mm shielded power inductor
save("L_Bourns_SRP7028A_7.3x6.6mm", [("body", box(-3.65, -3.3, 3.65, 3.3, 0, 2.8))])

# HRO TYPE-C-31-M-12: 8.94 x 7.3 shell, 3.26 tall, mouth at footprint -Y
shell = Part.makeBox(8.94, 7.3, 3.26, V(-4.47, -3.65, 0))
shell = shell.makeFillet(1.2, [e for e in shell.Edges if abs(e.tangentAt(e.FirstParameter).y) > 0.99])
mouth = Part.makeBox(8.34 - 0.8, 6.0, 2.56 - 0.6, V(-3.77, 3.65 - 6.0 + 0.01, 0.6))
save("USB_C_Receptacle_HRO_TYPE-C-31-M-12", [("shell", shell.cut(mouth)), ("tongue", box(-3.3, -3.65, 3.3, 1.0, 1.4, 2.0))])

# AMASS XT30PW-M horizontal: body -7.56..2.56 x -13.21..-3.99 (footprint), 5.2 tall; ears to -8.15/3.15
xt = box(-7.56, -13.21, 2.56, -3.99, 0, 5.2).fuse(box(-8.15, -11.11, 3.15, -8.89, 0, 5.2))
pins = box(-6.2, -3.99, 1.2, 0.6, 0.6, 2.6)
save("AMASS_XT30PW-M_1x02_P2.50mm_Horizontal", [("body", xt), ("pins", pins)])

# Raspberry Pi RM2: 14.5 x 16.5 x 0.8 PCB, shield can over the lower 12 mm, 2.55 mm total
pcb = box(-7.25, -8.25, 7.25, 8.25, 0, 0.8)
can = box(-6.6, -3.5, 6.6, 7.5, 0.8, 2.55)
save("RaspberryPi_RM2", [("pcb", pcb), ("can", can)])

# Kailh Choc V1 (CPG135001D01 drawing): 13.8 mm lower housing up to the plate top (PCB->plate 2.2 mm +
# 1.2 mm plate), 15 x 15 upper housing to 5.0 mm, stem to 8.0 mm (3.0 mm travel), 3.0 mm pins below.
lower = box(-6.9, -6.9, 6.9, 6.9, 0, 3.4)
upper = box(-7.5, -7.5, 7.5, 7.5, 3.4, 5.0)
stem = box(-4.0, -2.0, 4.0, 2.0, 5.0, 8.0)
for sx in (-2.85, 2.85):                       # the two 1.20 x 3.00 keycap slots, 5.70 apart
    stem = stem.cut(box(sx - 0.6, -1.5, sx + 0.6, 1.5, 5.5, 8.1))
post = Part.makeCylinder(1.6, 2.65, V(0, 0, -2.65))
pins = Part.makeCylinder(0.35, 3.0, V(0, 5.9, -3.0)).fuse(Part.makeCylinder(0.35, 3.0, V(5.0, 3.8, -3.0)))
save("Kailh_Choc_V1", [("housing", lower.fuse(upper)), ("stem", stem), ("post", post), ("pins", pins)])


def stabilizer(name, spacing):
    """Kailh PG1350 plate-mount stabilizer: two housings (WD003, 7.30 x 7.60 x 4.30 from the PCB top),
    stems (WD002, cross socket 1.00 mm, top at 8.0 mm like the switch stem) and the 1.0 mm wire."""
    parts = []
    for sx in (-spacing / 2, spacing / 2):
        hs = box(sx - 3.65, -3.8, sx + 3.65, 3.8, 0, 4.3).cut(box(sx - 1.6, -1.5, sx + 1.6, 1.5, -0.1, 4.4))
        parts.append((f"housing{len(parts)}", hs))
        st = box(sx - 1.3, -2.0, sx + 1.3, 2.0, 3.7, 8.0)
        st = st.cut(box(sx - 0.5, -1.3, sx + 0.5, 1.3, 6.0, 8.1)).cut(box(sx - 1.25, -0.5, sx + 1.25, 0.5, 6.0, 8.1))
        parts.append((f"stem{len(parts)}", st))
    wire = Part.makeCylinder(0.5, spacing, V(-spacing / 2, 5.0, 4.0), V(1, 0, 0))
    for sx in (-spacing / 2, spacing / 2):
        wire = wire.fuse(Part.makeCylinder(0.5, 10.0, V(sx, 5.0, 4.0), V(0, -1, 0)))
    parts.append(("wire", wire))
    save(name, parts)


stabilizer("Kailh_Choc_Stabilizer_2u", 24.0)
stabilizer("Kailh_Choc_Stabilizer_6u", 76.0)
