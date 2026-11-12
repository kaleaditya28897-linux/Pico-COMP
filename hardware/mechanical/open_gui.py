"""Open the case in the FreeCAD GUI with everything visible and fitted.
Run: FreeCAD hardware/mechanical/open_gui.py
"""
import os

import FreeCAD as App
import FreeCADGui as Gui

here = os.path.dirname(os.path.abspath(__file__))
doc = App.openDocument(os.path.join(here, "pico-comp.FCStd"))
Gui.ActiveDocument = Gui.getDocument(doc.Name)
colors = {"Base": (0.25, 0.25, 0.28), "Lid": (0.25, 0.25, 0.28), "KeyPlate": (0.75, 0.75, 0.78),
          "DisplayPanel": (0.05, 0.05, 0.1), "Antenna": (1.0, 0.7, 0.0), "Cells18650": (0.2, 0.4, 0.8),
          "HingePin": (0.5, 0.5, 0.5), "KeyboardPCB": (0.0, 0.5, 0.25), "MainPCB": (0.0, 0.4, 0.55)}
for o in doc.Objects:
    vo = o.ViewObject
    vo.Visibility = True
    if o.Name in colors:
        vo.ShapeColor = colors[o.Name]
view = Gui.activeDocument().activeView()
view.viewIsometric()
view.fitAll()
