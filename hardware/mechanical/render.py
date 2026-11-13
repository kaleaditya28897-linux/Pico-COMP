#!/usr/bin/env python3
"""Photo-style renders of the assembly (offscreen VTK), for reviewing the FreeCAD model.

  FreeCADCmd hardware/mechanical/render_export.py    # meshes + colours -> hardware/mechanical/render/
  python3 hardware/mechanical/render.py [view ...]   # PNGs -> hardware/mechanical/render/*.png

Views: hero (3/4 front, lid open), top, side, back, closed, detail_kb, detail_ports.
"""
import json
import os
import sys

import vtk

here = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(here, "render")

VIEWS = {   # camera position, focal point, view-up (case frame, mm), parallel scale or None
    "hero": ((420, -300, 330), (125, 70, 60), (0, 0, 1), None),
    "top": ((125, 70, 600), (125, 70, 0), (0, 1, 0), 105),
    "side": ((620, 70, 90), (125, 70, 60), (0, 0, 1), None),
    "back": ((-200, 520, 260), (125, 70, 60), (0, 0, 1), None),
    "closed": ((430, -280, 260), (125, 70, 20), (0, 0, 1), None),
    "detail_kb": ((200, -60, 160), (150, 60, 30), (0, 0, 1), None),
    "detail_ports": ((420, 20, 90), (240, 60, 15), (0, 0, 1), None),
}


def actor(path, color, spec, rough):
    r = vtk.vtkSTLReader()
    r.SetFileName(path)
    n = vtk.vtkPolyDataNormals()
    n.SetInputConnection(r.GetOutputPort())
    n.SetFeatureAngle(35)
    n.SplittingOn()
    m = vtk.vtkPolyDataMapper()
    m.SetInputConnection(n.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(m)
    p = a.GetProperty()
    p.SetInterpolationToPhong()
    p.SetColor(*color)
    p.SetAmbient(0.95 if color[0] > 0.99 else 0.18)       # amber screen text glows
    p.SetDiffuse(0.85)
    p.SetSpecular(spec)
    p.SetSpecularPower(rough)
    return a


def render(view, items, size=(1600, 1000)):
    ren = vtk.vtkRenderer()
    ren.SetBackground(0.93, 0.94, 0.96)
    ren.SetBackground2(0.62, 0.66, 0.72)
    ren.GradientBackgroundOn()
    for it in items:
        if view != "closed" and it.get("closed_only"):
            continue
        if view == "closed" and it.get("open_only"):
            continue
        ren.AddActor(actor(it["stl"], it["color"], it.get("spec", 0.25), it.get("rough", 30)))
    ren.RemoveAllLights()
    for pos, inten in (((500, -400, 600), 0.85), ((-400, -200, 300), 0.35), ((100, 600, 400), 0.3)):
        L = vtk.vtkLight()
        L.SetPosition(*pos)
        L.SetFocalPoint(125, 70, 30)
        L.SetIntensity(inten)
        ren.AddLight(L)
    cam = ren.GetActiveCamera()
    pos, fp, up, ps = VIEWS[view]
    cam.SetPosition(*pos)
    cam.SetFocalPoint(*fp)
    cam.SetViewUp(*up)
    if ps:
        cam.ParallelProjectionOn()
        cam.SetParallelScale(ps)
    else:
        cam.SetViewAngle(28)
    ren.ResetCameraClippingRange()
    # ambient occlusion + anti-aliasing
    basic = vtk.vtkRenderStepsPass()
    ssao = vtk.vtkSSAOPass()
    ssao.SetRadius(6.0)
    ssao.SetKernelSize(128)
    ssao.SetBias(0.05)
    ssao.BlurOn()
    ssao.SetDelegatePass(basic)
    ren.SetPass(ssao)
    ren.UseFXAAOn()
    rw = vtk.vtkRenderWindow()
    rw.SetOffScreenRendering(1)
    rw.SetMultiSamples(0)
    rw.AddRenderer(ren)
    rw.SetSize(*size)
    rw.Render()
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(rw)
    w2i.Update()
    wr = vtk.vtkPNGWriter()
    wr.SetFileName(os.path.join(OUT, f"{view}.png"))
    wr.SetInputConnection(w2i.GetOutputPort())
    wr.Write()
    print("wrote", f"render/{view}.png")


if __name__ == "__main__":
    items = json.load(open(os.path.join(OUT, "scene.json")))
    for v in sys.argv[1:] or ["hero", "top", "closed", "detail_kb"]:
        render(v, items)
