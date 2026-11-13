#!/usr/bin/env python3
"""Export each board's parts (position, side, rotation, 3D models) for the FreeCAD assembly.

Run: python3 hardware/kicad/export_parts.py [board ...]   (needs KiCad's pcbnew python module)
Writes hardware/kicad/<board>_parts.json; hardware/mechanical/case.py loads every model as its
own FreeCAD object, so each component can be inspected or moved individually. Also writes
hardware/kicad/3d/<board>_{substrate,copper,silkscreen,soldermask}.step: the bare board with its real
copper and silkscreen, used by case.py instead of a plain slab.
"""
import json
import os

import pcbnew

here = os.path.dirname(os.path.abspath(__file__))
VARS = {"${KICAD10_3DMODEL_DIR}": "/usr/share/kicad/3dmodels", "${KICAD9_3DMODEL_DIR}": "/usr/share/kicad/3dmodels",
        "${KICAD8_3DMODEL_DIR}": "/usr/share/kicad/3dmodels", "${KIPRJMOD}": here}


def resolve(p):
    for k, v in VARS.items():
        p = p.replace(k, v)
    if p.endswith(".wrl"):
        p = p[:-4] + ".step"
    return p if os.path.exists(p) else None


def export(name):
    b = pcbnew.LoadBoard(os.path.join(here, f"{name}.kicad_pcb"))
    bb = b.GetBoardEdgesBoundingBox()
    thick = b.GetDesignSettings().GetBoardThickness() / 1e6
    parts, missing = [], []
    for fp in b.GetFootprints():
        models = []
        for m in fp.Models():
            if not m.m_Show:
                continue
            path = resolve(m.m_Filename)
            if not path:
                missing.append(f"{fp.GetReference()}: {m.m_Filename}")
                continue
            models.append(dict(path=path, offset=[m.m_Offset.x, m.m_Offset.y, m.m_Offset.z],
                               rot=[m.m_Rotation.x, m.m_Rotation.y, m.m_Rotation.z],
                               scale=[m.m_Scale.x, m.m_Scale.y, m.m_Scale.z]))
        pos = fp.GetPosition()
        fb = fp.GetBoundingBox(False)
        fbox = [(fb.GetLeft() - bb.GetLeft()) / 1e6, (fb.GetTop() - bb.GetTop()) / 1e6,
                (fb.GetRight() - bb.GetLeft()) / 1e6, (fb.GetBottom() - bb.GetTop()) / 1e6]
        parts.append(dict(ref=fp.GetReference(), value=fp.GetValue(),
                          footprint=str(fp.GetFPID().GetLibItemName()),
                          x=(pos.x - bb.GetLeft()) / 1e6, y=(pos.y - bb.GetTop()) / 1e6,
                          rot=fp.GetOrientationDegrees(), back=fp.IsFlipped(), models=models, bbox=fbox))
    holes = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetDrillSize().x > 0 and p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                c = p.GetPosition()
                holes.append([(c.x - bb.GetLeft()) / 1e6, (c.y - bb.GetTop()) / 1e6, p.GetDrillSize().x / 1e6])
    out = dict(board=name, width=bb.GetWidth() / 1e6, height=bb.GetHeight() / 1e6, thickness=thick,
               npth=holes, parts=parts)
    json.dump(out, open(os.path.join(here, f"{name}_parts.json"), "w"), indent=0)
    print(f"{name}: {len(parts)} parts, {sum(len(p['models']) for p in parts)} models, {len(holes)} NPTH"
          + (f", missing models: {missing}" if missing else ""))


LAYERS = {   # FreeCAD object suffix -> kicad-cli step options (board in its own frame, bottom at z = 0)
    "substrate": ["--board-only", "--cut-vias-in-body"],
    "copper": ["--no-board-body", "--no-components", "--include-tracks", "--include-pads", "--include-zones"],
    "silkscreen": ["--no-board-body", "--no-components", "--include-silkscreen"],
    "soldermask": ["--no-board-body", "--no-components", "--include-soldermask"],
}


def export_layers(name):
    """Bare-board STEP layers (substrate, outer copper, silkscreen, soldermask) for the FreeCAD model."""
    import subprocess
    out = os.path.join(here, "3d")
    os.makedirs(out, exist_ok=True)
    for suffix, opts in LAYERS.items():
        subprocess.run(["kicad-cli", "pcb", "export", "step", "--force", *opts, "-o",
                        os.path.join(out, f"{name}_{suffix}.step"), os.path.join(here, f"{name}.kicad_pcb")],
                       check=True, capture_output=True)
    print(f"{name}: layer STEPs in hardware/kicad/3d/")


if __name__ == "__main__":
    import sys
    for n in sys.argv[1:] or ("mainboard", "keyboard"):
        export(n)
        export_layers(n)
