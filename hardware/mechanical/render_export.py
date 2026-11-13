"""Export pico-comp.FCStd as one STL per material for render.py.  Run: FreeCADCmd hardware/mechanical/render_export.py

Objects carried by the lid are exported twice: as modelled (open, LID_SHOW in case.py) and swung
closed about the hinge.
"""
import json
import os

import FreeCAD as App
import sys

import Mesh
import MeshPart

here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
sys.path.insert(0, here)
OUT = os.path.join(here, "render")
os.makedirs(OUT, exist_ok=True)
OPEN_DEG = 110.0                        # case.py saves the lid this far open (LID_SHOW); closed = swing back
HINGE = App.Vector(0, 140.0, 37.0)      # case.py HINGE_Y / HINGE_Z

from palette import LID_OBJS, MAT, material  # noqa: E402


doc = App.openDocument(os.path.join(here, "pico-comp.FCStd"))
meshes = {}
for g in doc.Objects:
    if g.TypeId != "App::DocumentObjectGroup":
        continue
    for o in g.Group:
        if not hasattr(o, "Shape") or o.Shape.isNull():
            continue
        mat = material(o, g.Name)
        lid = o.Name in LID_OBJS or o.Name.startswith(("ScrewLid", "Bumper"))
        poses = [("", o.Shape)]
        if lid:
            cl = o.Shape.copy()
            cl.rotate(HINGE, App.Vector(1, 0, 0), OPEN_DEG)
            poses = [("closed", cl), ("open", o.Shape)]
        for pose, sh in poses:
            key = (mat, pose)
            m = MeshPart.meshFromShape(Shape=sh, LinearDeflection=0.08, AngularDeflection=0.25, Relative=False)
            meshes.setdefault(key, Mesh.Mesh()).addMesh(m)
scene = []
for (mat, pose), m in meshes.items():
    name = f"{mat}{'_' + pose if pose else ''}"
    path = os.path.join(OUT, name + ".stl")
    m.write(path)
    rgb, spec, rough = MAT[mat]
    scene.append(dict(stl=path, color=rgb, spec=spec, rough=rough,
                      closed_only=pose == "closed", open_only=pose == "open"))
json.dump(scene, open(os.path.join(OUT, "scene.json"), "w"), indent=1)
print("exported", len(scene), "meshes")
