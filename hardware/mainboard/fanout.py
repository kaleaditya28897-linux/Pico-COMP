#!/usr/bin/env python3
"""Plane fan-out for the main board: every SMD pad on a plane net gets a short stub and a via.

    python3 hardware/mainboard/fanout.py hardware/kicad/mainboard.kicad_pcb

GND (In1 plane) and V3V3 (In4 plane) are what made autorouting fail: hundreds of pins, many on the
two 0.4 mm-pitch QFN-60s, each needing an escape via. This places them deterministically:
  - exposed pads (QFN thermal pads) get a grid of vias in the pad;
  - other pads get a stub straight out of the pad, away from the part's centre, to the first via
    position that clears every other-net pad, via and stub (plus board edge and rule-area keep-outs),
    re-using a nearby same-net via when one is reachable.
New tracks/vias are locked so the autorouter keeps them. Run it once, on a freshly generated board: the
generator's own locked copper (RP2350 regulator recipe, charger links) and its pours are kept and treated as
obstacles, and pads that a same-net pour or recipe copper already connects get no fan-out.
"""
import math
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

PLANE_NETS = {"GND", "V3V3"}
# Fine-pitch ICs whose signal pins also get a dog-bone (stub + via) so routers start on inner layers.
SIGNAL_FANOUT = {"U1", "U2", "U5", "U10"}
LOCAL_MM = 3.0          # skip a signal pin whose only partner pad is this close (easy on the top layer)
POUR_NETS = {"VBUS", "PMID", "VSYS", "VBAT", "VBAT_PACK", "V5", "SW1", "SW2", "SW3", "SW5"}   # F.Cu pours: no fan-out
VIA_D, VIA_DRILL = 0.45, 0.2
BGA_VIA = (0.35, 0.15)  # via-in-pad for the 0.5 mm-pitch BGA (0.1 mm annular ring)
STUB_W = 0.2
# eMMC (U12) ball C4 is GND and sits right under DAT5 (B4). With a via in every pad, B4 has no escape at
# the 0.25 mm hole-clearance rule (its only free diagonals pass 0.354 mm from two drills; 0.389 is needed).
# So C4 gets no via: it is tied on F.Cu to GND ball G5 (which has one), zig-zagging between the NC balls
# D4/E5 through the empty D5/E4/F4/G4 sites; DAT5 then escapes straight down column 4 on an inner layer.
BGA_NO_VIA = {"C4": ("G5", [(0.5, 0.5), (0.0, 1.0), (0.0, 2.0)])}
CLR = 0.15              # a little over the 0.127 mm rule
EDGE = 0.35             # copper to board edge
TAG = "fanout"


def seg_point_dist(a, b, p):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(ax + t * dx - px, ay + t * dy - py)


def seg_seg_dist(a, b, c, d):
    def ccw(p, q, r):
        return (r[1] - p[1]) * (q[0] - p[0]) - (q[1] - p[1]) * (r[0] - p[0])
    if (ccw(a, c, d) * ccw(b, c, d) < 0) and (ccw(a, b, c) * ccw(a, b, d) < 0):
        return 0.0
    return min(seg_point_dist(a, b, c), seg_point_dist(a, b, d), seg_point_dist(c, d, a), seg_point_dist(c, d, b))


def mm(v):
    return (ToMM(v.x), ToMM(v.y))


def run(path, only=None):
    """only: set of "REF.PAD" to fan out on an already-routed board (e.g. after an ECO); existing copper
    is kept and treated as an obstacle, and the plane / BGA passes are skipped."""
    board = pcbnew.LoadBoard(path)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    bb = board.GetBoardEdgesBoundingBox()
    X0, Y0, X1, Y1 = ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())
    keepouts = [z for z in board.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
    keepouts += [z for fp in board.GetFootprints() for z in fp.Zones()          # e.g. the RM2 RF keep-out
                 if z.GetIsRuleArea() and z.GetDoNotAllowVias()]

    pads = []                                          # (pad, netname, {layer: poly}, through)
    for p in board.GetPads():
        through = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
        polys = {}
        for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
            if p.IsOnLayer(lay):
                polys[lay] = p.GetEffectivePolygon(lay, pcbnew.ERROR_INSIDE)
        if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:  # holes: keep vias off them on every layer
            polys = {pcbnew.F_Cu: p.GetEffectivePolygon(pcbnew.F_Cu, pcbnew.ERROR_INSIDE)} if not polys else polys
        pads.append((p, p.GetNetname(), polys, through))
    vias, stubs = [], []                               # (x, y, net) / ((ax, ay), (bx, by), w, layer, net)
    r = VIA_D / 2
    if True:                                           # existing copper: vias at their real size on every layer
        cu = [l for l in range(pcbnew.PCB_LAYER_ID_COUNT) if pcbnew.IsCopperLayer(l) and board.IsLayerEnabled(l)]
        for t in board.GetTracks():
            if t.GetClass() == "PCB_VIA":
                c = mm(t.GetPosition())
                vias.append((c[0], c[1], t.GetNetname()))
                stubs += [(c, c, ToMM(t.GetWidth(pcbnew.F_Cu)), l, t.GetNetname()) for l in cu]
            else:
                stubs.append((mm(t.GetStart()), mm(t.GetEnd()), ToMM(t.GetWidth()), t.GetLayer(), t.GetNetname()))

    # F.Cu pours (PWR_*, VREG_*): other nets keep out (a via or stub there would cut the pour)
    pours = [(z.GetNetname(), z.Outline()) for z in board.Zones()
             if not z.GetIsRuleArea() and z.GetNetname() and z.IsOnLayer(pcbnew.F_Cu)]

    def in_pour(pt, net, margin):
        return any(zn != net and (ol.Contains(pt) or ol.Collide(pt, FromMM(margin))) for zn, ol in pours)

    def connected_already(p):
        """Pad sits in a same-net F.Cu pour, or recipe copper of its net already touches it."""
        n = p.GetNetname()
        if any(zn == n and ol.Contains(p.GetPosition()) for zn, ol in pours):
            return True
        return any(t.IsLocked() and t.GetNetname() == n and
                   (p.HitTest(t.GetPosition()) if t.GetClass() == "PCB_VIA" else (p.HitTest(t.GetStart()) or p.HitTest(t.GetEnd())))
                   for t in board.GetTracks())

    def via_ok(x, y, net):
        if not (X0 + EDGE + r <= x <= X1 - EDGE - r and Y0 + EDGE + r <= y <= Y1 - EDGE - r):
            return False
        pt = VECTOR2I(FromMM(x), FromMM(y))
        for z in keepouts:
            if z.Outline().Collide(pt, FromMM(r)):
                return False
        if in_pour(pt, net, r + CLR):
            return False
        for p, pn, polys, through in pads:
            if pn == net and pn:
                continue
            for poly in polys.values():                # a via touches every layer
                if poly.Collide(pt, FromMM(r + CLR)):
                    return False
        for vx, vy, vn in vias:
            if vn != net and math.hypot(vx - x, vy - y) < 2 * r + CLR:
                return False
            if vn == net and math.hypot(vx - x, vy - y) < 2 * r + 0.1:
                return False
        for a, b, w, lay, sn in stubs:
            if sn != net and seg_point_dist(a, b, (x, y)) < w / 2 + r + CLR:
                return False
        return True

    def stub_ok(a, b, layer, net, own_pad):
        sa, sb = VECTOR2I(FromMM(a[0]), FromMM(a[1])), VECTOR2I(FromMM(b[0]), FromMM(b[1]))
        seg = pcbnew.SEG(sa, sb)
        if layer == pcbnew.F_Cu and any(zn != net and ol.Collide(seg, FromMM(STUB_W / 2 + CLR)) for zn, ol in pours):
            return False
        for p, pn, polys, through in pads:
            if p is own_pad or (pn == net and pn):
                continue
            poly = polys.get(layer)
            if poly is not None and poly.Collide(seg, FromMM(STUB_W / 2 + CLR)):
                return False
        for vx, vy, vn in vias:
            if vn != net and seg_point_dist(a, b, (vx, vy)) < STUB_W / 2 + r + CLR:
                return False
        for c, d, w, lay, sn in stubs:
            if lay == layer and sn != net and seg_seg_dist(a, b, c, d) < STUB_W / 2 + w / 2 + CLR:
                return False
        return True

    added_v, added_t, failed = 0, 0, []

    def add_via(x, y, netinfo):
        nonlocal added_v
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
        v.SetWidth(FromMM(VIA_D))
        v.SetDrill(FromMM(VIA_DRILL))
        v.SetNet(netinfo)
        v.SetLocked(True)
        board.Add(v)
        vias.append((x, y, netinfo.GetNetname()))
        added_v += 1

    def add_stub(a, b, layer, netinfo):
        nonlocal added_t
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(VECTOR2I(FromMM(a[0]), FromMM(a[1])))
        t.SetEnd(VECTOR2I(FromMM(b[0]), FromMM(b[1])))
        t.SetWidth(FromMM(STUB_W))
        t.SetLayer(layer)
        t.SetNet(netinfo)
        t.SetLocked(True)
        board.Add(t)
        stubs.append((a, b, STUB_W, layer, netinfo.GetNetname()))
        added_t += 1

    # BGA (the eMMC): every connected ball gets a via-in-pad (filled + capped at the fab). Plane balls reach
    # their plane; signal balls get an escape the autorouter continues from on the inner layers.
    for fp in board.GetFootprints():
        if only or "BGA" not in str(fp.GetFPID().GetLibItemName()):
            continue
        pads_by_num = {q.GetNumber(): q for q in fp.Pads()}
        for p in fp.Pads():
            n = p.GetNetname()
            if not n or n.startswith("unconnected-"):
                continue
            if p.GetNumber() in BGA_NO_VIA:          # tied on F.Cu instead (see BGA_NO_VIA)
                pts = [p.GetPosition()] + [VECTOR2I(p.GetPosition().x + FromMM(dx), p.GetPosition().y + FromMM(dy))
                                           for dx, dy in BGA_NO_VIA[p.GetNumber()][1]] + \
                      [pads_by_num[BGA_NO_VIA[p.GetNumber()][0]].GetPosition()]
                for a, b in zip(pts, pts[1:]):
                    t = pcbnew.PCB_TRACK(board)
                    t.SetStart(a)
                    t.SetEnd(b)
                    t.SetWidth(FromMM(0.127))
                    t.SetLayer(pcbnew.F_Cu)
                    t.SetNet(p.GetNet())
                    t.SetLocked(True)
                    board.Add(t)
                    stubs.append((mm(a), mm(b), 0.127, pcbnew.F_Cu, n))
                continue
            c = mm(p.GetPosition())
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(p.GetPosition())
            v.SetWidth(FromMM(BGA_VIA[0]))
            v.SetDrill(FromMM(BGA_VIA[1]))
            v.SetNet(p.GetNet())
            v.SetLocked(True)
            board.Add(v)
            vias.append((c[0], c[1], n))
            added_v += 1
    bga_pads = {id(p) for fp in board.GetFootprints() if "BGA" in str(fp.GetFPID().GetLibItemName()) for p in fp.Pads()}
    targets = [p for p in board.GetPads() if p.GetNetname() in PLANE_NETS and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD
               and id(p) not in bga_pads and not connected_already(p)]
    net_pads = {}
    for p in board.GetPads():
        net_pads.setdefault(p.GetNetname(), []).append(p)

    def wants_signal_fanout(p):
        n = p.GetNetname()
        if not n or n.startswith("unconnected-") or n in PLANE_NETS or n in POUR_NETS:
            return False
        if connected_already(p):
            return False
        if p.GetParentFootprint().GetReference() not in SIGNAL_FANOUT or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            return False
        w, h = ToMM(p.GetSize().x), ToMM(p.GetSize().y)
        if w >= 2.0 and h >= 2.0:
            return False
        others = [q for q in net_pads[n] if q is not p]
        c = mm(p.GetPosition())
        if len(others) == 1 and math.hypot(*(a - b for a, b in zip(mm(others[0].GetPosition()), c))) < LOCAL_MM:
            return False
        return True
    targets += [p for p in board.GetPads() if wants_signal_fanout(p)]
    if only:
        targets = [p for p in board.GetPads() if f"{p.GetParentFootprint().GetReference()}.{p.GetNumber()}" in only]
    # exposed/thermal pads first: via grid inside the pad
    for p in targets:
        w, h = ToMM(p.GetSize().x), ToMM(p.GetSize().y)
        if w >= 2.0 and h >= 2.0:
            cx, cy = mm(p.GetPosition())
            n = 3 if min(w, h) >= 3.0 else 2
            step = min(w, h) / (n + 0.5)
            for i in range(n):
                for j in range(n):
                    x, y = cx + (i - (n - 1) / 2) * step, cy + (j - (n - 1) / 2) * step
                    if via_ok(x, y, p.GetNetname()):
                        add_via(x, y, p.GetNet())
    # every other plane-net pad: stub + via (or re-use a close same-net via)
    order = sorted(targets, key=lambda p: -len(p.GetParentFootprint().Pads()))   # dense ICs first
    for p in order:
        w, h = ToMM(p.GetSize().x), ToMM(p.GetSize().y)
        if w >= 2.0 and h >= 2.0:
            continue
        net = p.GetNetname()
        layer = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
        c = mm(p.GetPosition())
        o = mm(p.GetParentFootprint().GetPosition())
        dx, dy = c[0] - o[0], c[1] - o[1]
        L = math.hypot(dx, dy)
        base_dirs = [(dx / L, dy / L)] if L > 0.05 else [(1, 0), (0, 1), (-1, 0), (0, -1)]
        dirs = []
        for ux, uy in base_dirs:
            dirs += [(ux, uy), (-uy, ux), (uy, -ux), (-ux, -uy)]
        pb = p.GetBoundingBox()
        corners = [(ToMM(pb.GetLeft()), ToMM(pb.GetTop())), (ToMM(pb.GetRight()), ToMM(pb.GetBottom())),
                   (ToMM(pb.GetLeft()), ToMM(pb.GetBottom())), (ToMM(pb.GetRight()), ToMM(pb.GetTop()))]
        done = False
        # re-use a same-net via within reach
        for vx, vy, vn in sorted(vias, key=lambda v: math.hypot(v[0] - c[0], v[1] - c[1])):
            if vn == net and math.hypot(vx - c[0], vy - c[1]) < 1.2 and stub_ok(c, (vx, vy), layer, net, p):
                add_stub(c, (vx, vy), layer, p.GetNet())
                done = True
                break
            if math.hypot(vx - c[0], vy - c[1]) >= 1.2:
                break
        for di, (ux, uy) in enumerate(dirs):
            if done:
                break
            ext = max((cx - c[0]) * ux + (cy - c[1]) * uy for cx, cy in corners)
            for k in range(30):
                if done:
                    break
                d = ext + r + CLR + 0.05 + k * 0.1
                for lat in (0, 0.25, -0.25, 0.5, -0.5, 0.8, -0.8):
                    x, y = c[0] + ux * d - uy * lat, c[1] + uy * d + ux * lat
                    if via_ok(x, y, net) and stub_ok(c, (x, y), layer, net, p):
                        add_via(x, y, p.GetNet())
                        add_stub(c, (x, y), layer, p.GetNet())
                        done = True
                        break
        if not done:
            failed.append(f"{p.GetParentFootprint().GetReference()}.{p.GetNumber()}")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    print(f"fan-out: {added_v} vias, {added_t} stubs; {len(targets)} plane pads; not placed: {failed or 'none'}")


if __name__ == "__main__":
    # python3 fanout.py board.kicad_pcb [--only=U5.12,U1.46]
    sel = [a[7:].split(",") for a in sys.argv[2:] if a.startswith("--only=")]
    run(sys.argv[1], set(sel[0]) if sel else None)
