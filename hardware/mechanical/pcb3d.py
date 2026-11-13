"""Build a KiCad board in FreeCAD as separate objects: bare PCB + one object per component.

Input: hardware/kicad/<board>_parts.json from kicad/export_parts.py. Each component's KiCad STEP
model is placed exactly as KiCad does it (footprint rotation, back-side flip) and then moved into
the case frame, so every part shows up in the model tree and can be inspected or moved.
"""
import json
import math
import os

import FreeCAD as App
import Part

V = App.Vector
_cache = {}


def _model(path):
    if path not in _cache:
        _cache[path] = Part.read(path)
    return _cache[path].copy()


def _placed(m, part, z_bot, thick):
    sh = _model(m["path"])
    sx, sy, sz = m["scale"]
    if (sx, sy, sz) != (1, 1, 1):
        mat = App.Matrix()
        mat.scale(sx, sy, sz)
        sh = sh.transformGeometry(mat)
    rx, ry, rz = m["rot"]
    for ang, ax in ((-rx, V(1, 0, 0)), (-ry, V(0, 1, 0)), (-rz, V(0, 0, 1))):   # KiCad: X, Y, Z (clockwise)
        if ang:
            sh.rotate(V(0, 0, 0), ax, ang)
    ox, oy, oz = m["offset"]
    sh.translate(V(ox, oy, oz))
    if part["back"]:
        sh.rotate(V(0, 0, 0), V(1, 0, 0), 180)        # turn the part over (y -> -y, z -> -z)
        z = z_bot
    else:
        z = z_bot + thick
    if part["rot"]:
        sh.rotate(V(0, 0, 0), V(0, 0, 1), part["rot"])
    sh.translate(V(part["x"], -part["y"], z))           # board frame: KiCad y is down
    return sh


def build(doc, json_path, x0, ytop, z_bot, group, pcb_name, skip_npth_below=0.0):
    """Board origin (top-left corner) goes to case (x0, ytop); returns (pcb shape, {ref: shape})."""
    data = json.load(open(json_path))
    w, h, t = data["width"], data["height"], data["thickness"]
    pcb = Part.makeBox(w, h, t, V(0, -h, z_bot))
    holes = [Part.makeCylinder(d / 2, t + 2, V(x, -y, z_bot - 1)) for x, y, d in data["npth"] if d >= skip_npth_below]
    if holes:
        pcb = pcb.cut(Part.makeCompound(holes))
    layer_dir = os.path.join(os.path.dirname(json_path), "3d")
    board = data["board"]
    sub = os.path.join(layer_dir, f"{board}_substrate.step")
    if os.path.exists(sub):                  # real board from KiCad: drilled substrate + copper/silk/mask
        pcb = Part.read(sub)
        pcb.translate(V(0, 0, z_bot))
    pcb.translate(V(x0, ytop, 0))
    o = doc.addObject("Part::Feature", pcb_name)
    o.Label = f"{pcb_name} substrate (FR4)"
    o.Shape = pcb
    group.addObject(o)
    for suffix in ("copper", "silkscreen", "soldermask"):
        f = os.path.join(layer_dir, f"{board}_{suffix}.step")
        if os.path.exists(f):
            sh = Part.read(f)
            sh.translate(V(x0, ytop, z_bot))
            lo = doc.addObject("Part::Feature", f"{pcb_name}_{suffix}")
            lo.Label = f"{pcb_name} {suffix}"
            lo.Shape = sh
            group.addObject(lo)
    shapes, worst = {}, []
    for part in data["parts"]:
        if not part["models"]:
            continue
        sh = Part.makeCompound([_placed(m, part, z_bot, t) for m in part["models"]])
        sh.translate(V(x0, ytop, 0))
        name = "".join(c if c.isalnum() else "_" for c in part["ref"])
        o = doc.addObject("Part::Feature", f"{pcb_name}_{name}")
        o.Label = f"{part['ref']} {part['value']}"
        o.Shape = sh
        group.addObject(o)
        shapes[part["ref"]] = sh
        # sanity: the model's XY centre should sit on its footprint
        bx0, by0, bx1, by1 = part["bbox"]
        fc = V(x0 + (bx0 + bx1) / 2, ytop - (by0 + by1) / 2, 0)
        mc = sh.BoundBox.Center
        worst.append((math.hypot(fc.x - mc.x, fc.y - mc.y), part["ref"]))
    worst.sort(reverse=True)
    return pcb, shapes, worst[:3]
