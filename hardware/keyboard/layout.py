#!/usr/bin/env python3
"""Pico-COMP keyboard layout: 6 rows x 14u at 17 mm pitch, Kailh Choc V1 (low profile).

Outputs (in this directory):
  plate.dxf    switch-plate outline + 13.8 mm switch cutouts (mm, origin top-left, y up)
  matrix.csv   key name, row, column, x/y centre in mm, width in units
Run: python3 layout.py
"""
import csv
import os

PITCH = 17.0          # mm per 1u (both axes)
CUTOUT = 13.8         # Choc V1 plate cutout
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


def rect(f, x0, y0, x1, y1):
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    f.write("0\nLWPOLYLINE\n8\n0\n90\n4\n70\n1\n")
    for px, py in pts:
        f.write(f"10\n{px:.3f}\n20\n{-py:.3f}\n")


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
        rect(f, -MARGIN, -MARGIN, width + MARGIN, height + MARGIN)
        for k in keys:
            h = CUTOUT / 2
            rect(f, k["x"] - h, k["y"] - h, k["x"] + h, k["y"] + h)
        f.write("0\nENDSEC\n0\nEOF\n")

    print(f"{len(keys)} keys, matrix {len(ROWS)} rows x {max(len(r) for r in ROWS)} cols")
    print(f"key area {width:.0f} x {height:.0f} mm, plate {width + 2*MARGIN:.0f} x {height + 2*MARGIN:.0f} mm")


if __name__ == "__main__":
    main()
