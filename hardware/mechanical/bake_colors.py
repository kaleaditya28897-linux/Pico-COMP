"""Write the material colours into pico-comp.FCStd (its GuiDocument.xml) so the file opens coloured.

FreeCADCmd has no view providers and the GUI needs OpenGL, so the GUI part of the document is
written directly: one ViewProvider per object with ShapeColor / Transparency / Visibility.
Called from case.py: bake(doc, path) after doc.saveAs(path).
"""
import os
import sys
import zipfile
from xml.sax.saxutils import quoteattr

here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
sys.path.insert(0, here)
from palette import MAT, material  # noqa: E402


def packed(rgb):
    r, g, b = (int(round(c * 255)) & 0xFF for c in rgb)
    return (r << 24) | (g << 16) | (b << 8)          # alpha byte 0 = opaque in FreeCAD's packing


def view_provider(name, rgb=None, visible=True, group=False):
    props = [f'<Property name="Visibility" type="App::PropertyBool" status="1"><Bool value="{"true" if visible else "false"}"/></Property>']
    if rgb is not None:
        props.append(f'<Property name="ShapeColor" type="App::PropertyColor" status="1"><PropertyColor value="{packed(rgb)}"/></Property>')
        props.append(f'<Property name="LineColor" type="App::PropertyColor" status="1"><PropertyColor value="{packed((0.1, 0.1, 0.1))}"/></Property>')
        props.append('<Property name="Transparency" type="App::PropertyPercent" status="1"><Integer value="0"/></Property>')
    return (f'<ViewProvider name={quoteattr(name)} expanded="{1 if group else 0}">'
            f'<Properties Count="{len(props)}" TransientCount="0">{"".join(props)}</Properties></ViewProvider>')


def bake(doc, path):
    vps = []
    for g in doc.Objects:
        if g.TypeId != "App::DocumentObjectGroup":
            continue
        vps.append(view_provider(g.Name, group=True))
        for o in g.Group:
            if hasattr(o, "Shape"):
                vps.append(view_provider(o.Name, MAT[material(o, g.Name)][0]))
    xml = ("<?xml version='1.0' encoding='utf-8'?>\n<Document SchemaVersion=\"1\" HasExpansion=\"1\">\n"
           f'<ViewProviderData Count="{len(vps)}">\n' + "\n".join(vps) + "\n</ViewProviderData>\n"
           '<Camera settings=""/>\n</Document>\n')
    tmp = path + ".tmp"
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename != "GuiDocument.xml":
                zout.writestr(item, zin.read(item.filename))
        zout.writestr("GuiDocument.xml", xml)
    os.replace(tmp, path)
    print(f"baked colours for {len(vps)} view providers into {os.path.basename(path)}")
