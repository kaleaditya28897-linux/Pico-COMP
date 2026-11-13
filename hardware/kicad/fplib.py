"""Project copies of KiCad library footprints (pico-comp.pretty), shared by both PCB generators.

A copy is made when a part needs our own STEP model (pico-comp.3dshapes) or when silkscreen must
be trimmed because the part overhangs the board edge. Boards then reference pico-comp:<name>, so
the placed footprint matches its library copy (no 'footprint differs from library' DRC warnings).
"""
import os
import re

import kisch

here = os.path.dirname(os.path.abspath(__file__))
SYS_FP = "/usr/share/kicad/footprints"
LIB = "pico-comp"
OWN_3D = {"QFN-60-1EP_7x7mm_P0.4mm_EP3.4x3.4mm", "Texas_RQM0029A_VQFN-29_4x4mm_P0.4mm",
          "L_Bourns_SRP7028A_7.3x6.6mm", "USB_C_Receptacle_HRO_TYPE-C-31-M-12",
          "AMASS_XT30PW-M_1x02_P2.50mm_Horizontal"}


def _silk_pts(e):
    pts = [kisch.first(e, k) for k in ("start", "end")]
    return [(float(p[1]), float(p[2])) for p in pts if p]


def _drop_silk(src, test):
    node = kisch.parse(src)

    def bad(e):
        if not (isinstance(e, list) and e[0] in ("fp_line", "fp_rect") and kisch.first(e, "layer")
                and kisch.first(e, "layer")[1] == "F.SilkS"):
            return False
        return test(_silk_pts(e))
    return kisch.dump([e for e in node if not bad(e)]) + "\n"


# silk to drop, as a test on the line's points in footprint coordinates
TRIM = {
    # USB-C mouth sits on the board edge
    "USB_C_Receptacle_HRO_TYPE-C-31-M-12": lambda pts: min(y for _, y in pts) >= 1.9,
    # right-angle header: the pins overhang the board edge, keep only the body outline
    "PinHeader_1x20_P2.54mm_Horizontal": lambda pts: max(x for x, _ in pts) > 4.2,
}


def needs_copy(name):
    return name in OWN_3D or name in TRIM


def copy(lib, name):
    """Write pico-comp.pretty/<name>.kicad_mod from the KiCad library; returns the project lib name."""
    src = open(f"{SYS_FP}/{lib}.pretty/{name}.kicad_mod").read()
    if name in OWN_3D:
        src = re.sub(r'\(model "[^"]*"', f'(model "${{KIPRJMOD}}/{LIB}.3dshapes/{name}.step"', src)
    if name in TRIM:
        src = _drop_silk(src, TRIM[name])
    open(os.path.join(here, f"{LIB}.pretty", f"{name}.kicad_mod"), "w").write(src)
    return LIB


def keepout_circle(board, x, y, r, name="FIDUCIAL_KEEPOUT"):
    """No-track/no-via rule area (octagon) around a point, e.g. a fiducial: Freerouting ignores
    footprint-local clearances but honours rule areas."""
    import math

    import pcbnew
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetLayerSet(pcbnew.LSET.AllCuMask())
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowZoneFills(True)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    z.SetZoneName(name)
    ol = z.Outline()
    ol.NewOutline()
    for i in range(8):
        a = math.pi / 8 + i * math.pi / 4
        ol.Append(pcbnew.FromMM(x + r * math.cos(a)), pcbnew.FromMM(y + r * math.sin(a)))
    board.Add(z)
