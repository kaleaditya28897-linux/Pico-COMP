"""Kailh Choc V1 keycaps with legends, for the assembly and for fabrication.

Used by case.py. Each cap is a hollow shell (1.2 mm top, 1.0 mm skirt) with two Choc V1 stem legs
(1.2 x 3.0 mm, 5.7 mm apart; KeyV2 choc stem) and the legend debossed into the top. The legend is
also returned as its own solid, the exact inlay for two-colour / multi-material printing.
Cap size = pitch x units - GAP. Legends are DejaVu Sans Bold.
"""
import os

import FreeCAD as App
import Part

V = App.Vector
FONT = "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"

GAP = 1.0                 # between neighbouring caps
CAP_T = 2.4               # skirt bottom to top surface
TOP_T = 1.2               # top plate
WALL_T = 1.0              # skirt
R_CORNER = 1.2            # plan-view corner radius
R_TOP = 0.6               # top edge round-over
LEG = (1.2 - 0.1, 3.0 - 0.1)   # Choc V1 leg cross-section minus 0.1 mm print clearance
LEG_SEP = 5.7
LEG_LEN = 3.0             # below the skirt bottom
DEBOSS = 0.5
# Kailh PG1350 stabilizer stem (drawing BSPG1350-WD002): cross socket with 1.00 (+0.03/0) mm slots, arms
# about 2.6 x 2.3 mm. The cap gets a male cross: arm thickness 0.95, lengths 2.5 (x) and 2.2 (y).
# Same spacing as hardware/keyboard/layout.py STAB_SPACING. Test-print one Shift cap for fit first.
STAB_CROSS = (2.5, 2.2, 0.95)
STAB_SPACING = {2: 24.0, 6: 76.0}

SHIFTED = {"`": "~", "1": "!", "2": "@", "3": "#", "4": "$", "5": "%", "6": "^", "7": "&", "8": "*", "9": "(",
           "0": ")", "-": "_", "=": "+", "[": "{", "]": "}", ";": ":", "'": "\"", ",": "<", ".": ">", "/": "?"}
GLYPH = {"Up": "↑", "Down": "↓", "Left": "←", "Right": "→", "Space": ""}


def _text(s, size):
    faces = [Part.makeFace(ch, "Part::FaceMakerBullseye") for ch in Part.makeWireString(s, FONT, size, 0) if ch]
    return Part.makeCompound(faces) if faces else None


def _centred(s, size, cx, cy, z):
    t = _text(s, size)
    if t is None:
        return None
    bb = t.BoundBox
    t.translate(V(cx - (bb.XMin + bb.XMax) / 2, cy - (bb.YMin + bb.YMax) / 2, z))
    return t


def legend_faces(name, w, cy_top=0.0):
    """Legend outline faces centred on (0, 0) at z = 0."""
    label = GLYPH.get(name, name)
    if not label:
        return None
    if name in SHIFTED:                       # two-level legend: shifted symbol above the base one
        parts = [_centred(SHIFTED[name], 3.2, 0, 2.6, 0), _centred(label, 3.2, 0, -2.6, 0)]
    elif len(label) == 1:
        parts = [_centred(label, 5.0 if name not in GLYPH else 6.0, 0, 0, 0)]
    else:
        parts = [_centred(label, 2.8 if len(label) <= 4 else 2.4, 0, 0, 0)]
    parts = [p for p in parts if p]
    return Part.makeCompound(parts)


def make(name, units, pitch, cx, cy, z_bottom):
    """Return (cap solid with debossed legend, legend inlay solid or None), placed at (cx, cy, z_bottom)."""
    w, d = units * pitch - GAP, pitch - GAP
    outer = Part.makeBox(w, d, CAP_T, V(-w / 2, -d / 2, 0))
    outer = outer.makeFillet(R_CORNER, [e for e in outer.Edges if abs(e.tangentAt(e.FirstParameter).z) > 0.99])
    outer = outer.makeFillet(R_TOP, [e for e in outer.Edges if abs(e.BoundBox.ZMin - CAP_T) < 1e-6 and abs(e.BoundBox.ZMax - CAP_T) < 1e-6])
    inner = Part.makeBox(w - 2 * WALL_T, d - 2 * WALL_T, CAP_T - TOP_T + 0.01, V(-w / 2 + WALL_T, -d / 2 + WALL_T, -0.01))
    inner = inner.makeFillet(max(R_CORNER - WALL_T, 0.2), [e for e in inner.Edges if abs(e.tangentAt(e.FirstParameter).z) > 0.99])
    cap = outer.cut(inner)
    for sx in (-LEG_SEP / 2, LEG_SEP / 2):    # stem legs from the top plate down past the skirt
        cap = cap.fuse(Part.makeBox(LEG[0], LEG[1], LEG_LEN + CAP_T - TOP_T, V(sx - LEG[0] / 2, -LEG[1] / 2, -LEG_LEN)))
    sp = STAB_SPACING.get(int(units)) if units >= 2 else None
    if sp:                                    # male cross pegs for the Kailh PG1350 stabilizer stems
        for sx in (-sp / 2, sp / 2):
            for ax, ay in ((STAB_CROSS[0], STAB_CROSS[2]), (STAB_CROSS[2], STAB_CROSS[1])):
                cap = cap.fuse(Part.makeBox(ax, ay, LEG_LEN + CAP_T - TOP_T, V(sx - ax / 2, -ay / 2, -LEG_LEN)))
    cap = cap.removeSplitter()
    inlay = None
    faces = legend_faces(name, w)
    if faces is not None:
        inlay = faces.extrude(V(0, 0, DEBOSS))
        inlay.translate(V(0, 0, CAP_T - DEBOSS))
        cap = cap.cut(inlay)
    for s in (cap, inlay):
        if s is not None:
            s.translate(V(cx, cy, z_bottom))
    return cap, inlay


def safe(name):
    return "".join(c if c.isalnum() else f"x{ord(c):02x}" for c in name)


def export_all(keys, pitch, out_dir):
    """One STEP + STL per cap (legend debossed) and per legend inlay, at the origin, top up."""
    import Mesh
    import MeshPart
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for k in keys:
        cap, inlay = make(k["name"], k["w"], pitch, 0, 0, LEG_LEN)
        base = f"r{k['row']}c{k['col']:02d}_{safe(k['name'])}_{k['w']:g}u"
        for suffix, sh in (("", cap), ("_legend", inlay)):
            if sh is None:
                continue
            sh.exportStep(os.path.join(out_dir, base + suffix + ".step"))
            Mesh.Mesh(MeshPart.meshFromShape(Shape=sh, LinearDeflection=0.02, AngularDeflection=0.2)).write(
                os.path.join(out_dir, base + suffix + ".stl"))
        rows.append((base, k["name"], k["w"]))
    with open(os.path.join(out_dir, "README.md"), "w") as fh:
        fh.write("# Keycaps (Kailh Choc V1)\n\nGenerated by `hardware/mechanical/case.py`; do not edit by hand.\n\n"
                 f"- Size: pitch x units - {GAP} mm gap, {CAP_T} mm tall, hollow ({TOP_T} mm top, {WALL_T} mm skirt).\n"
                 f"- Stem: two legs {LEG[0]:.2f} x {LEG[1]:.2f} mm, {LEG_SEP} mm apart, {LEG_LEN} mm long (Choc V1, 0.1 mm clearance).\n"
                 f"- Legend: debossed {DEBOSS} mm. `*_legend.*` is the matching inlay for two-colour / multi-material "
                 "printing (print it in the legend colour and the cap in the body colour, same origin).\n"
                 "- Files are at the origin with the top surface up; print top-down on resin/MJF or top-up with supports.\n"
                 "- The 2u Shift and 6u Space carry male cross pegs for Kailh PG1350 (Choc) plate-mount stabilizers "
                 f"({STAB_SPACING[2]:g} mm and {STAB_SPACING[6]:g} mm apart; 2U and 6.25U kits). Test-print one Shift cap "
                 "for fit before printing the set.\n\n| File | Legend | Units |\n|---|---|---|\n")
        fh.writelines(f"| {b} | `{n}` | {w:g} |\n" for b, n, w in rows)
    return len(rows)
