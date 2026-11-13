#!/usr/bin/env python3
"""Pico-COMP keyboard layout: 6 rows x 14u at 17 mm pitch, Kailh Choc V1 (low profile).

Outputs (in this directory):
  plate.dxf    1.2 mm switch plate: outline, 13.8 mm switch cutouts, 6.3 x 6.6 mm stabilizer cutouts
               (mm, origin top-left, y up)
  matrix.csv   key name, row, column, x/y centre in mm, width in units
Run: python3 layout.py
"""
import csv
import os

PITCH = 17.0          # mm per 1u (both axes)
CUTOUT = 13.8         # Choc V1 plate cutout
PLATE_R = 4.0         # plate corner radius (same as hardware/placement.py)
MARGIN = 3.0          # plate margin around the keys
ROW_U = 14.0          # every row sums to exactly 14u -> 238 mm

# (label, width in u). Arrows form an inverted T: Up in the Shift row, Left/Down/Right below.
ROWS = [
    [("Esc", 1)] + [(f"F{i}", 1) for i in range(1, 13)] + [("Del", 1)],
    [("`", 1)] + [(c, 1) for c in "1234567890-="] + [("Bksp", 1)],
    [("Tab", 1.5)] + [(c, 1) for c in "QWERTYUIOP"] + [("[", 1), ("]", 1.5)],
    [("Ctrl", 1.5)] + [(c, 1) for c in "ASDFGHJKL"] + [(";", 1), ("'", 1), ("Enter", 1.5)],
    [("Shift", 2)] + [(c, 1) for c in "ZXCVBNM"] + [(",", 1), (".", 1), ("/", 1), ("Up", 1), ("Shift", 1)],
    [("Ctrl", 1.25), ("Fn", 1.25), ("Alt", 1.25), ("Space", 6), ("Alt", 1.25),
     ("Left", 1), ("Down", 1), ("Right", 1)],
]


def build():
    keys = []
    for r, row in enumerate(ROWS):
        total = sum(w for _, w in row)
        assert abs(total - ROW_U) < 1e-9, f"row {r} is {total}u, expected {ROW_U}u"
        x = 0.0
        for c, (name, w) in enumerate(row):
            cx = (x + w / 2) * PITCH
            cy = (r + 0.5) * PITCH
            keys.append(dict(name=name, row=r, col=c, x=cx, y=cy, w=w))
            x += w
    return keys


# Kailh PG1350 (Choc V1) plate-mount stabilizers, from the Kailh drawings (keebio-references):
# housing BSPG1350-WD003 clips into a 6.30 x 6.60 mm plate opening; stem BSPG1350-WD002 has a 1.00 mm
# cross socket; wires BWPG1350-07003 (2u, 24.00 mm between legs) and BWPG1350-07002 (76.00 mm, sold
# as 6.25u, used here for the 6u space bar).
STAB_CUTOUT = (6.30, 6.60)        # plate opening (x along the wire, y)
STAB_SPACING = {2: 24.0, 6: 76.0}  # key width (u) -> distance between the two stabilizer housings


def stabs(keys):
    """[(key, x, y)] stabilizer housing centres (layout frame) for every key that needs one."""
    out = []
    for k in keys:
        sp = STAB_SPACING.get(int(k["w"])) if k["w"] >= 2 else None
        if sp:
            for dx in (-sp / 2, sp / 2):
                out.append((k, k["x"] + dx, k["y"]))
    return out


def rect(f, x0, y0, x1, y1):
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    f.write("0\nLWPOLYLINE\n8\n0\n90\n4\n70\n1\n")
    for px, py in pts:
        f.write(f"10\n{px:.3f}\n20\n{-py:.3f}\n")


def rounded_rect(f, x0, y0, x1, y1, r):
    """Closed polyline with 90 degree arc corners (DXF bulge = tan(90/4))."""
    b = 0.41421356
    pts = [(x0 + r, y0, 0), (x1 - r, y0, b), (x1, y0 + r, 0), (x1, y1 - r, b),
           (x1 - r, y1, 0), (x0 + r, y1, b), (x0, y1 - r, 0), (x0, y0 + r, b)]
    f.write(f"0\nLWPOLYLINE\n8\n0\n90\n{len(pts)}\n70\n1\n")
    for px, py, bulge in pts:
        f.write(f"10\n{px:.3f}\n20\n{-py:.3f}\n" + (f"42\n{-bulge:.8f}\n" if bulge else ""))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    keys = build()
    width = ROW_U * PITCH
    height = len(ROWS) * PITCH

    with open(os.path.join(here, "matrix.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "row", "col", "x_mm", "y_mm", "width_u"])
        for k in keys:
            w.writerow([k["name"], k["row"], k["col"], f"{k['x']:.2f}", f"{k['y']:.2f}", k["w"]])

    with open(os.path.join(here, "plate.dxf"), "w") as f:
        f.write("0\nSECTION\n2\nENTITIES\n")
        rounded_rect(f, -MARGIN, -MARGIN, width + MARGIN, height + MARGIN, PLATE_R)
        for k in keys:
            h = CUTOUT / 2
            rect(f, k["x"] - h, k["y"] - h, k["x"] + h, k["y"] + h)
        sx, sy = STAB_CUTOUT[0] / 2, STAB_CUTOUT[1] / 2
        for _, x, y in stabs(keys):
            rect(f, x - sx, y - sy, x + sx, y + sy)
        f.write("0\nENDSEC\n0\nEOF\n")

    print(f"{len(keys)} keys, matrix {len(ROWS)} rows x {max(len(r) for r in ROWS)} cols")
    print(f"key area {width:.0f} x {height:.0f} mm, plate {width + 2*MARGIN:.0f} x {height + 2*MARGIN:.0f} mm")


if __name__ == "__main__":
    main()
