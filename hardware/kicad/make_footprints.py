#!/usr/bin/env python3
"""Write pico-comp.pretty/RaspberryPi_RM2.kicad_mod from the RM2 datasheet (RP-008943, Figure 6).

Module 14.5 x 16.5 mm, origin at the module centre, antenna end at -Y (top in KiCad).
21 castellated pads, 1.5 mm pitch, 2.0 x 1.0 mm, protruding 0.5 mm past the module edge.
Pins 1-7 down the left edge, 8-14 along the bottom, 15-21 up the right edge.
RF keep-out (no copper on any layer): 35.5 mm wide, from 13.5 mm beyond the antenna edge to
5.0 mm inside it (11.5 mm above the bottom edge). Place the antenna end at the board edge.
Also writes Kailh_Choc_V1.kicad_mod (keyboard switch).
Run: python3 hardware/kicad/make_footprints.py
"""
import os

here = os.path.dirname(os.path.abspath(__file__))
W, H = 14.5, 16.5
hw, hh = W / 2, H / 2


def pads():
    out = []
    for k in range(7):                                   # left, pin 1 at the top
        out.append((1 + k, -hw + 0.5, -hh + 5.7 + k * 1.5, 2.0, 1.0))
    for k in range(7):                                   # bottom, left to right
        out.append((8 + k, -hw + 2.75 + k * 1.5, hh - 0.5, 1.0, 2.0))
    for k in range(7):                                   # right, bottom to top
        out.append((15 + k, hw - 0.5, hh - 1.8 - k * 1.5, 2.0, 1.0))
    return out


def rect(layer, x0, y0, x1, y1, w=0.1):
    return (f'  (fp_rect (start {x0:.3f} {y0:.3f}) (end {x1:.3f} {y1:.3f}) '
            f'(stroke (width {w}) (type solid)) (fill no) (layer "{layer}"))\n')


def line(layer, x0, y0, x1, y1, w=0.12):
    return (f'  (fp_line (start {x0:.3f} {y0:.3f}) (end {x1:.3f} {y1:.3f}) '
            f'(stroke (width {w}) (type solid)) (layer "{layer}"))\n')


ko_top, ko_bot = -hh - 13.5, hh - 11.5
s = ['(footprint "RaspberryPi_RM2"\n  (version 20240108)\n  (generator "make_footprints.py")\n  (layer "F.Cu")\n',
     '  (descr "Raspberry Pi Radio Module 2 (RMC20452T), CYW43439 Wi-Fi/BT, 21 castellated pads 1.5 mm pitch, '
     'onboard antenna; footprint per RP-008943 Figure 6")\n',
     '  (tags "RM2 CYW43439 WiFi castellated")\n  (attr smd)\n',
     '  (property "Reference" "U" (at 0 -1 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))\n',
     '  (property "Value" "RM2" (at 0 1 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))\n']
s.append(rect("F.Fab", -hw, -hh, hw, hh))
s.append(line("F.Fab", -hw, -hh + 4.5, hw, -hh + 4.5, 0.1))           # antenna / can boundary
s.append(f'  (fp_text user "ANTENNA" (at 0 {-hh + 2.2:.2f} 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.1))))\n')
s.append(f'  (fp_text user "${{REFERENCE}}" (at 0 2 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))\n')
# silkscreen: corner brackets outside the pads + pin-1 marker
o = 0.75
s.append(line("F.SilkS", -hw - o, -hh + 0.5, -hw - o, -hh + 3.0))   # antenna edge sits on the board edge:
s.append(line("F.SilkS", hw + o, -hh + 0.5, hw + o, -hh + 3.0))     # no silk across it
s.append(f'  (fp_circle (center {-hw - 1.3:.2f} {-hh + 5.7:.2f}) (end {-hw - 1.1:.2f} {-hh + 5.7:.2f}) '
         '(stroke (width 0.2) (type solid)) (fill yes) (layer "F.SilkS"))\n')
s.append(rect("F.CrtYd", -hw - 0.85, ko_top, hw + 0.85, hh + 0.85, 0.05))
s.append(rect("F.CrtYd", -17.75, ko_top, 17.75, ko_bot, 0.05))
s.append(f'  (fp_text user "RF KEEP-OUT" (at 0 {ko_top + 3:.2f} 0) (layer "Cmts.User") (effects (font (size 1 1) (thickness 0.15))))\n')
for n, x, y, sx, sy in pads():
    s.append(f'  (pad "{n}" smd rect (at {x:.3f} {y:.3f}) (size {sx} {sy}) (layers "F.Cu" "F.Paste" "F.Mask"))\n')
s.append(f'''  (zone (net 0) (net_name "") (layers "F.Cu" "In1.Cu" "In2.Cu" "B.Cu") (name "RM2_RF_KEEPOUT") (hatch edge 0.5)
    (connect_pads (clearance 0)) (min_thickness 0.25)
    (keepout (tracks not_allowed) (vias not_allowed) (pads not_allowed) (copperpour not_allowed) (footprints allowed))
    (fill (thermal_gap 0.5) (thermal_bridge_width 0.5))
    (polygon (pts (xy -17.75 {ko_top}) (xy 17.75 {ko_top}) (xy 17.75 {ko_bot}) (xy -17.75 {ko_bot}))))
''')
s.append('  (model "${KIPRJMOD}/pico-comp.3dshapes/RaspberryPi_RM2.step" (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))\n)\n')
open(os.path.join(here, "pico-comp.pretty", "RaspberryPi_RM2.kicad_mod"), "w").write("".join(s))
print("wrote RaspberryPi_RM2.kicad_mod")


# ---------------------------------------------------------------- Kailh Choc V1 (CPG1350), PCB-mount
def choc():
    c = ['(footprint "Kailh_Choc_V1"\n  (version 20240108)\n  (generator "make_footprints.py")\n  (layer "F.Cu")\n',
         '  (descr "Kailh Choc V1 (CPG1350) low-profile switch, soldered, 3.4 mm centre post, 1.9 mm pegs")\n',
         '  (tags "Kailh Choc V1 CPG1350 keyboard switch")\n  (attr through_hole)\n',
         '  (property "Reference" "SW" (at 0 -8.6 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))\n',
         '  (property "Value" "Choc_V1" (at 0 8.6 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))\n']
    c.append(rect("F.Fab", -6.9, -6.9, 6.9, 6.9))
    c.append(rect("F.Fab", -7.5, -7.5, 7.5, 7.5))
    c.append(rect("F.SilkS", -7.6, -7.6, 7.6, 7.6, 0.12))
    c.append(rect("F.CrtYd", -7.75, -7.75, 7.75, 7.75, 0.05))  # 15 mm upper housing + 0.25
    c.append('  (pad "1" thru_hole circle (at 0 -5.9) (size 2.2 2.2) (drill 1.2) (layers "*.Cu" "*.Mask"))\n')
    c.append('  (pad "2" thru_hole circle (at 5 -3.8) (size 2.2 2.2) (drill 1.2) (layers "*.Cu" "*.Mask"))\n')
    for x, d in ((0, 3.4), (-5.5, 1.9), (5.5, 1.9)):
        c.append(f'  (pad "" np_thru_hole circle (at {x} 0) (size {d} {d}) (drill {d}) (layers "*.Cu" "*.Mask"))\n')
    c.append('  (model "${KIPRJMOD}/pico-comp.3dshapes/Kailh_Choc_V1.step" (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))\n)\n')
    open(os.path.join(here, "pico-comp.pretty", "Kailh_Choc_V1.kicad_mod"), "w").write("".join(c))
    print("wrote Kailh_Choc_V1.kicad_mod")


choc()


# ---------------------------------------------------------------- Kailh PG1350 plate-mount stabilizers
STAB_PCB_CUT = (7.8, 8.0)      # PCB clearance under each housing (housing body 7.30 x 7.60, drawing WD003)


def stab(name, spacing, descr):
    c = [f'(footprint "{name}"\n  (version 20240108)\n  (generator "make_footprints.py")\n  (layer "F.Cu")\n',
         f'  (descr "{descr}")\n  (tags "Kailh Choc PG1350 stabilizer")\n  (attr exclude_from_pos_files)\n',
         '  (property "Reference" "ST" (at 0 -5.5 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))\n',
         f'  (property "Value" "{name}" (at 0 5.5 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))\n']
    w, h = STAB_PCB_CUT
    for sx in (-spacing / 2, spacing / 2):
        c.append(rect("Edge.Cuts", sx - w / 2, -h / 2, sx + w / 2, h / 2, 0.1))
        c.append(rect("F.Fab", sx - 3.65, -3.8, sx + 3.65, 3.8, 0.1))         # housing 7.30 x 7.60
        c.append(rect("F.CrtYd", sx - w / 2 - 0.25, -h / 2 - 0.25, sx + w / 2 + 0.25, h / 2 + 0.25, 0.05))
    c.append(line("F.Fab", -spacing / 2, -2.0, spacing / 2, -2.0, 0.1))      # wire
    c.append(f'  (model "${{KIPRJMOD}}/pico-comp.3dshapes/{name}.step" (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))\n)\n')
    open(os.path.join(here, "pico-comp.pretty", f"{name}.kicad_mod"), "w").write("".join(c))
    print(f"wrote {name}.kicad_mod")


stab("Kailh_Choc_Stabilizer_2u", 24.0, "Kailh PG1350 plate-mount stabilizer, 2u (wire BWPG1350-07003, 24 mm); PCB clearance cut-outs under the housings")
stab("Kailh_Choc_Stabilizer_6u", 76.0, "Kailh PG1350 plate-mount stabilizer, 76 mm wire BWPG1350-07002 (6.25u kit) on a 6u key; PCB clearance cut-outs under the housings")
