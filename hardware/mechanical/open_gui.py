"""Open the assembly in the FreeCAD GUI, coloured by group, everything visible and fitted.
Run: FreeCAD hardware/mechanical/open_gui.py      (build it first: FreeCADCmd hardware/mechanical/case.py)

Tree groups: Case, Display, Battery, Mainboard, Keyboard, Keycaps, Fasteners, Cables. Every board
component is its own object labelled "<ref> <value>" (e.g. "U1 RP2350A (UI)"); select one and use
Edit > Placement to move it, or hide a group with Space.
"""
import os

import FreeCAD as App
import FreeCADGui as Gui

here = os.path.dirname(os.path.abspath(__file__))
doc = App.openDocument(os.path.join(here, "pico-comp.FCStd"))
Gui.ActiveDocument = Gui.getDocument(doc.Name)
GROUP_COLOR = {"Case": (0.22, 0.22, 0.25), "Display": (0.05, 0.05, 0.1), "Battery": (0.2, 0.4, 0.8),
               "Mainboard": (0.55, 0.55, 0.58), "Keyboard": (0.3, 0.3, 0.32), "Keycaps": (0.92, 0.92, 0.88),
               "Fasteners": (0.7, 0.7, 0.72), "Cables": (0.1, 0.1, 0.1)}
NAME_COLOR = {"KeyPlate": (0.75, 0.75, 0.78), "MainPCB": (0.0, 0.4, 0.55), "KeyboardPCB": (0.0, 0.45, 0.2),
              "MainPCB_copper": (0.85, 0.6, 0.25), "KeyboardPCB_copper": (0.85, 0.6, 0.25),
              "MainPCB_silkscreen": (0.95, 0.95, 0.95), "KeyboardPCB_silkscreen": (0.95, 0.95, 0.95),
              "MainPCB_soldermask": (0.05, 0.3, 0.1), "KeyboardPCB_soldermask": (0.05, 0.3, 0.1),
              "DisplayActiveArea": (0.1, 0.25, 0.1), "HingePin": (0.6, 0.6, 0.62)}
for g in doc.Objects:
    if g.TypeId != "App::DocumentObjectGroup":
        continue
    for o in g.Group:
        vo = o.ViewObject
        vo.Visibility = True
        rgb = NAME_COLOR.get(o.Name) or ((0.15, 0.15, 0.15) if o.Name.endswith("_legend") else GROUP_COLOR.get(g.Name))
        if rgb:
            vo.ShapeColor = rgb
view = Gui.activeDocument().activeView()
view.viewIsometric()
view.fitAll()
