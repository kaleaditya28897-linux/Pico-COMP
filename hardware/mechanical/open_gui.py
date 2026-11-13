"""Open the assembly in the FreeCAD GUI with the material colours (palette.py), everything visible.
(pico-comp.FCStd already carries the colours; this script re-applies them after edits.)
Run: FreeCAD hardware/mechanical/open_gui.py      (build it first: FreeCADCmd hardware/mechanical/case.py)

Tree groups: Case, Display, Battery, Mainboard, Keyboard, Keycaps, Fasteners, Cables. Every board
component is its own object labelled "<ref> <value>" (e.g. "U1 RP2350A (UI)"); select one and use
Edit > Placement to move it, or hide a group with Space.
"""
import os
import sys

import FreeCAD as App
import FreeCADGui as Gui

here = os.path.dirname(os.path.abspath(__file__))
doc = App.openDocument(os.path.join(here, "pico-comp.FCStd"))
Gui.ActiveDocument = Gui.getDocument(doc.Name)
sys.path.insert(0, here)
from palette import MAT, material  # noqa: E402

for g in doc.Objects:
    if g.TypeId != "App::DocumentObjectGroup":
        continue
    for o in g.Group:
        if hasattr(o, "Shape") and o.ViewObject is not None:
            o.ViewObject.Visibility = True
            o.ViewObject.ShapeColor = MAT[material(o, g.Name)][0]
view = Gui.activeDocument().activeView()
view.viewIsometric()
view.fitAll()
