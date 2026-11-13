#!/usr/bin/env python3
"""Finish the last unrouted connections of a board with a grid maze router (A*).

    python3 hardware/mainboard/maze_route.py hardware/kicad/mainboard.kicad_pcb [--nets A,B,...]

Targets come from KiCad's own DRC "unconnected_items" list, so this only touches what is left after
Freerouting (route.py). Each layer is rasterised at RES mm with a net-label image; a connection may
use cells whose distance to other-net copper (pads, tracks, vias, F.Cu power pours, holes, board
edge, keep-outs) leaves the rule clearance. Moves are 8-way on the routing layers; a layer change
places a via where every routing layer is clear. New copper is added to the rasters as it goes. The
result must be checked with KiCad DRC (kicad-cli pcb drc ...).
"""
import heapq
import json
import math
import os
import subprocess
import sys
import tempfile

import numpy as np
import pcbnew
from PIL import Image, ImageDraw
from pcbnew import FromMM, ToMM, VECTOR2I

RES = 0.05
CLR = 0.15              # target clearance (rule is 0.127)
EDGE = 0.35
VIA_D, VIA_DRILL = 0.45, 0.2
VIA_COST = 12.0         # in grid steps
LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu]
MARGIN = 6.0            # search window around the two endpoints, mm


def drc_unconnected(path):
    rpt = os.path.join(tempfile.mkdtemp(), "drc.json")
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--refill-zones", "--severity-all",
                    "-o", rpt, path], check=True, capture_output=True)
    out = []
    for v in json.load(open(rpt)).get("unconnected_items", []):
        it = v["items"]
        if len(it) == 2:
            out.append(((it[0]["pos"]["x"], it[0]["pos"]["y"]), (it[1]["pos"]["x"], it[1]["pos"]["y"]),
                        it[0]["uuid"], it[1]["uuid"]))
    return out


class Raster:
    def __init__(self, board):
        bb = board.GetBoardEdgesBoundingBox()
        self.x0, self.y0 = ToMM(bb.GetLeft()), ToMM(bb.GetTop())
        self.W = int(math.ceil(ToMM(bb.GetWidth()) / RES)) + 1
        self.H = int(math.ceil(ToMM(bb.GetHeight()) / RES)) + 1
        self.lab = {L: Image.new("I", (self.W, self.H), 0) for L in LAYERS}
        self.allblock = Image.new("L", (self.W, self.H), 0)   # holes, keep-outs: blocked everywhere
        self.drw = {L: ImageDraw.Draw(img) for L, img in self.lab.items()}
        self.adrw = ImageDraw.Draw(self.allblock)

    def px(self, x, y):
        return ((x - self.x0) / RES, (y - self.y0) / RES)

    def poly(self, L, pts, val):
        if len(pts) >= 3:
            self.drw[L].polygon([self.px(*p) for p in pts], fill=val)

    def seg(self, L, a, b, w, val):
        wp = max(1, int(round(w / RES)))
        self.drw[L].line([self.px(*a), self.px(*b)], fill=val, width=wp)
        for p in (a, b):
            cx, cy = self.px(*p)
            r = w / 2 / RES
            self.drw[L].ellipse([cx - r, cy - r, cx + r, cy + r], fill=val)

    def circle(self, L, c, rad, val):
        cx, cy = self.px(*c)
        r = rad / RES
        self.drw[L].ellipse([cx - r, cy - r, cx + r, cy + r], fill=val)


def chain_pts(chain):
    return [(ToMM(chain.CPoint(i).x), ToMM(chain.CPoint(i).y)) for i in range(chain.PointCount())]


def build(board):
    R = Raster(board)
    R.smd = Image.new("L", (R.W, R.H), 0)              # every SMD pad: no via may land on one (solder wicking)
    sdrw = ImageDraw.Draw(R.smd)
    for p in board.GetPads():
        nc = p.GetNetCode() or -1
        if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and p.IsOnLayer(pcbnew.F_Cu):
            ps = p.GetEffectivePolygon(pcbnew.F_Cu, pcbnew.ERROR_OUTSIDE)
            for i in range(ps.OutlineCount()):
                pts = chain_pts(ps.COutline(i))
                if len(pts) >= 3:
                    sdrw.polygon([R.px(*q) for q in pts], fill=1)
        for L in LAYERS:
            if p.IsOnLayer(L) or p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                ps = p.GetEffectivePolygon(L, pcbnew.ERROR_OUTSIDE)
                for i in range(ps.OutlineCount()):
                    R.poly(L, chain_pts(ps.COutline(i)), nc)
        if p.GetDrillSize().x > 0:                     # drilled holes block all routing layers
            c = (ToMM(p.GetPosition().x), ToMM(p.GetPosition().y))
            r = ToMM(max(p.GetDrillSize().x, p.GetSize().x)) / 2
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                cx, cy = R.px(*c)
                R.adrw.ellipse([cx - r / RES, cy - r / RES, cx + r / RES, cy + r / RES], fill=1)
    for t in board.GetTracks():
        nc = t.GetNetCode() or -1
        if t.GetClass() == "PCB_VIA":
            c = (ToMM(t.GetPosition().x), ToMM(t.GetPosition().y))
            for L in LAYERS:
                R.circle(L, c, ToMM(t.GetWidth(pcbnew.F_Cu)) / 2, nc)
        elif t.GetLayer() in R.lab:
            R.seg(t.GetLayer(), (ToMM(t.GetStart().x), ToMM(t.GetStart().y)), (ToMM(t.GetEnd().x), ToMM(t.GetEnd().y)),
                  ToMM(t.GetWidth()), nc)
    for z in board.Zones():
        if z.GetIsRuleArea():
            if z.GetDoNotAllowTracks():
                ol = z.Outline()
                for i in range(ol.OutlineCount()):
                    R.adrw.polygon([R.px(*p) for p in chain_pts(ol.COutline(i))], fill=1)
            continue
        if z.GetZoneName().startswith(("POUR_", "PWR_", "VREG_")) and z.GetLayer() == pcbnew.F_Cu:   # keep pours whole
            fp = z.GetFilledPolysList(pcbnew.F_Cu)
            for i in range(fp.OutlineCount()):
                R.poly(pcbnew.F_Cu, chain_pts(fp.COutline(i)), z.GetNetCode())
    for fp in board.GetFootprints():
        for z in fp.Zones():
            if z.GetIsRuleArea() and z.GetDoNotAllowTracks():
                ol = z.Outline()
                for i in range(ol.OutlineCount()):
                    R.adrw.polygon([R.px(*p) for p in chain_pts(ol.COutline(i))], fill=1)
    e = int(round(EDGE / RES))
    edge = np.ones((R.H, R.W), bool)
    edge[e:-e, e:-e] = False
    R.edge = edge
    return R


def dilate(mask, k):
    """Square dilation by k cells (separable max)."""
    out = mask.copy()
    for ax in (0, 1):
        acc = out.copy()
        for s in range(1, k + 1):
            acc |= np.roll(out, s, axis=ax) | np.roll(out, -s, axis=ax)
        out = acc
    return out


def route_pair(board, R, a, b, net, w, nets_info):
    x0 = min(a[0], b[0]) - MARGIN
    x1 = max(a[0], b[0]) + MARGIN
    y0 = min(a[1], b[1]) - MARGIN
    y1 = max(a[1], b[1]) + MARGIN
    i0, j0 = max(0, int((x0 - R.x0) / RES)), max(0, int((y0 - R.y0) / RES))
    i1, j1 = min(R.W, int((x1 - R.x0) / RES)), min(R.H, int((y1 - R.y0) / RES))
    allb = np.array(R.allblock)[j0:j1, i0:i1] > 0
    k_tr = int(math.ceil((CLR + w / 2) / RES))
    k_via = int(math.ceil((CLR + VIA_D / 2) / RES))
    free, viafree = [], None
    for L in LAYERS:
        lab = np.array(R.lab[L])[j0:j1, i0:i1]
        other = (lab != 0) & (lab != net)
        free.append(~(dilate(other, k_tr) | allb | R.edge[j0:j1, i0:i1]))
        vb = dilate(other, k_via)
        viafree = ~vb if viafree is None else viafree & ~vb
    viafree &= ~dilate(allb, k_via - k_tr) & ~R.edge[j0:j1, i0:i1]
    viafree &= ~dilate(np.array(R.smd)[j0:j1, i0:i1] > 0, int(math.ceil((VIA_D / 2 + 0.05) / RES)))
    own = [np.array(R.lab[L])[j0:j1, i0:i1] == net for L in LAYERS]
    H, W = free[0].shape

    def cell(p):
        return (int(round((p[0] - R.x0) / RES)) - i0, int(round((p[1] - R.y0) / RES)) - j0)
    sa, sb = cell(a), cell(b)
    # start: any layer where the start point is own copper (or free); goal: own copper at b
    starts = [(l, sa[0], sa[1]) for l in range(4) if 0 <= sa[0] < W and 0 <= sa[1] < H and own[l][sa[1], sa[0]]]
    goals = {(l, sb[0], sb[1]) for l in range(4) if 0 <= sb[0] < W and 0 <= sb[1] < H and own[l][sb[1], sb[0]]}
    if not starts or not goals:
        return None
    for l, x, y in starts + list(goals):
        free[l][y, x] = True
    gx, gy = sb
    D = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
    g = {}
    prev = {}
    pq = []
    for s in starts:
        g[s] = 0.0
        heapq.heappush(pq, (math.hypot(s[1] - gx, s[2] - gy), 0.0, s))
    found = None
    while pq:
        f, gc, s = heapq.heappop(pq)
        if gc > g.get(s, 1e18):
            continue
        if s in goals:
            found = s
            break
        l, x, y = s
        for dx, dy, c in D:
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and free[l][ny, nx]:
                if dx and dy and not (free[l][y, nx] and free[l][ny, x]):
                    continue
                n = (l, nx, ny)
                ng = gc + c
                if ng < g.get(n, 1e18):
                    g[n] = ng
                    prev[n] = s
                    heapq.heappush(pq, (ng + math.hypot(nx - gx, ny - gy), ng, n))
        if viafree[y, x]:
            for nl in range(4):
                if nl != l and free[nl][y, x]:
                    n = (nl, x, y)
                    ng = gc + VIA_COST
                    if ng < g.get(n, 1e18):
                        g[n] = ng
                        prev[n] = s
                        heapq.heappush(pq, (ng + math.hypot(x - gx, y - gy), ng, n))
    if not found:
        return None
    path = [found]
    while path[-1] in prev:
        path.append(prev[path[-1]])
    path.reverse()
    # to board items: simplify straight runs, vias at layer changes
    ni = nets_info[net]

    def los(c0, c1, mask):
        """Straight line c0->c1 stays on free cells (sampled at 1/3 cell)."""
        n = int(max(abs(c1[0] - c0[0]), abs(c1[1] - c0[1])) * 3) + 1
        for t in range(n + 1):
            x = round(c0[0] + (c1[0] - c0[0]) * t / n)
            y = round(c0[1] + (c1[1] - c0[1]) * t / n)
            if not mask[y, x]:
                return False
        return True

    # split into same-layer runs (a via sits between runs), then string-pull each run
    runs, cur = [], [path[0]]
    for st in path[1:]:
        if st[0] != cur[-1][0]:
            runs.append(cur)
            cur = [st]
        else:
            cur.append(st)
    runs.append(cur)

    def world(c):
        return (R.x0 + (c[1] + i0) * RES, R.y0 + (c[2] + j0) * RES)
    out_t, out_v = 0, 0
    for ri, run in enumerate(runs):
        lay = run[0][0]
        keep = [run[0]]
        k = 0
        while k < len(run) - 1:
            m = len(run) - 1
            while m > k + 1 and not los((run[k][1], run[k][2]), (run[m][1], run[m][2]), free[lay]):
                m -= 1
            keep.append(run[m])
            k = m
        wp = [world(c) for c in keep]
        if ri == 0:
            wp[0] = a
        if ri == len(runs) - 1:
            wp[-1] = b
        for p0, p1 in zip(wp, wp[1:]):
            out_t += add_track(board, R, (lay,) + tuple(p0), (lay,) + tuple(p1), LAYERS[lay], w, ni)
        if ri < len(runs) - 1:                                       # via to the next run
            vx, vy = wp[-1]
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(VECTOR2I(FromMM(vx), FromMM(vy)))
            v.SetWidth(FromMM(VIA_D))
            v.SetDrill(FromMM(VIA_DRILL))
            v.SetNet(ni)
            board.Add(v)
            for L in LAYERS:
                R.circle(L, (vx, vy), VIA_D / 2, net)
            out_v += 1
    return out_t, out_v


def add_track(board, R, a, b, layer, w, ni):
    if (a[1], a[2]) == (b[1], b[2]):
        return 0
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(VECTOR2I(FromMM(a[1]), FromMM(a[2])))
    t.SetEnd(VECTOR2I(FromMM(b[1]), FromMM(b[2])))
    t.SetLayer(layer)
    t.SetWidth(FromMM(w))
    t.SetNet(ni)
    board.Add(t)
    R.seg(layer, (a[1], a[2]), (b[1], b[2]), w, ni.GetNetCode())
    return 1


def main(path, only=None, passes=(6.0, 15.0, 40.0)):
    """Route every DRC-unconnected pair, shortest first; repeat with wider search windows."""
    global MARGIN
    total = 0
    for m in passes:
        MARGIN = m
        done, left = one_pass(path, only)
        total += done
        print(f"pass (window {m} mm): routed {done}, still unconnected {left}", flush=True)
        if left == 0 or done == 0 and m == passes[-1]:
            break
    return total


def one_pass(path, only=None):
    board = pcbnew.LoadBoard(path)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    items = {}
    for t in list(board.GetTracks()) + list(board.GetPads()):
        items[t.m_Uuid.AsString()] = t
    nets_info = {n.GetNetCode(): n for n in board.GetNetsByNetcode().values()}
    R = build(board)
    done, failed = 0, []
    pairs = sorted(drc_unconnected(path), key=lambda q: math.hypot(q[0][0] - q[1][0], q[0][1] - q[1][1]))
    for a, b, ua, ub in pairs:
        ia = items.get(ua)
        if ia is None:
            continue
        net = ia.GetNetCode()
        name = ia.GetNetname()
        if only and name not in only:
            continue
        nc = board.GetDesignSettings().m_NetSettings.GetEffectiveNetClass(name)
        w = max(ToMM(nc.GetTrackWidth()), 0.127)
        res = route_pair(board, R, a, b, net, w, nets_info)
        if res:
            done += 1
        else:
            failed.append(name)
        if done and done % 20 == 0:                   # checkpoint: partial progress is never lost
            pcbnew.SaveBoard(path, board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    return done, len(drc_unconnected(path))


if __name__ == "__main__":
    nets = None
    for a in sys.argv[2:]:
        if a.startswith("--nets="):
            nets = set(a[7:].split(","))
    main(os.path.abspath(sys.argv[1]), nets)
