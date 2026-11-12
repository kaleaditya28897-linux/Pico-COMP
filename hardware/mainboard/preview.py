#!/usr/bin/env python3
"""Draw a placement/track preview PNG of a KiCad board: python3 preview.py board.kicad_pcb out.png"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pcbnew
from matplotlib.patches import Rectangle

b = pcbnew.LoadBoard(sys.argv[1])
bb = b.GetBoardEdgesBoundingBox()
x0, y0, w, h = bb.GetX() / 1e6, bb.GetY() / 1e6, bb.GetWidth() / 1e6, bb.GetHeight() / 1e6
fig, ax = plt.subplots(figsize=(w / 8, h / 8), dpi=110)
ax.add_patch(Rectangle((x0, y0), w, h, fill=False, ec="y", lw=1.5))
for fp in b.GetFootprints():
    r = fp.GetBoundingBox(False)
    ax.add_patch(Rectangle((r.GetX() / 1e6, r.GetY() / 1e6), r.GetWidth() / 1e6, r.GetHeight() / 1e6,
                           fill=False, ec="c", lw=0.6))
    for p in fp.Pads():
        s = p.GetBoundingBox()
        ax.add_patch(Rectangle((s.GetX() / 1e6, s.GetY() / 1e6), s.GetWidth() / 1e6, s.GetHeight() / 1e6,
                               fc="#c83", ec="none"))
    ax.text(fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6, fp.GetReference(), fontsize=4, color="w", ha="center")
colors = {pcbnew.F_Cu: "#d33", pcbnew.B_Cu: "#38f", pcbnew.In1_Cu: "#3c3", pcbnew.In2_Cu: "#cc3"}
for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA":
        ax.plot(t.GetPosition().x / 1e6, t.GetPosition().y / 1e6, "o", ms=1.5, color="#ccc")
    else:
        a, c = t.GetStart(), t.GetEnd()
        ax.plot([a.x / 1e6, c.x / 1e6], [a.y / 1e6, c.y / 1e6], color=colors.get(t.GetLayer(), "w"),
                lw=max(0.4, t.GetWidth() / 1e6 * 2), solid_capstyle="round", alpha=0.8)
ax.set_xlim(x0 - 2, x0 + w + 2)
ax.set_ylim(y0 + h + 2, y0 - 2)
ax.set_aspect("equal")
ax.set_facecolor("#102010")
fig.savefig(sys.argv[2], facecolor="#102010", bbox_inches="tight")
