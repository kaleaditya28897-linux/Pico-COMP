#!/usr/bin/env python3
"""Maze-route named connections between explicit points, typically from a fan-out via of a pin that is
boxed in on F.Cu (DRC reports such an open at the pin, so maze_route.py would start there and fail).

    python3 hardware/mainboard/route_from.py board.kicad_pcb NET:REF.PAD[:via]>REF.PAD[:via] ...

`REF.PAD:via` means "the via on that pad's fan-out stub" (the locked via of the same net nearest the pad);
plain `REF.PAD` is the pad centre. Routes with maze_route.route_pair, widest window first that works.
"""
import math
import os
import sys

import pcbnew
from pcbnew import ToMM

import maze_route as mz


def point(board, spec, net):
    ref, rest = spec.split(".", 1)
    num, _, via = rest.partition(":")
    pad = [p for p in board.FindFootprintByReference(ref).Pads() if p.GetNumber() == num][0]
    c = pad.GetPosition()
    if not via:
        return (ToMM(c.x), ToMM(c.y))
    vs = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == net]
    v = min(vs, key=lambda t: math.hypot(t.GetPosition().x - c.x, t.GetPosition().y - c.y))
    assert math.hypot(v.GetPosition().x - c.x, v.GetPosition().y - c.y) < pcbnew.FromMM(2.5), f"no via near {spec}"
    return (ToMM(v.GetPosition().x), ToMM(v.GetPosition().y))


def main(path, jobs):
    board = pcbnew.LoadBoard(path)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    nets_info = {n.GetNetCode(): n for n in board.GetNetsByNetcode().values()}
    R = mz.build(board)
    for job in jobs:
        net, ends = job.split(":", 1)
        sa, sb = ends.split(">")
        a, b = point(board, sa, net), point(board, sb, net)
        ni = board.FindNet(net)
        nc = board.GetDesignSettings().m_NetSettings.GetEffectiveNetClass(net)
        w = max(ToMM(nc.GetTrackWidth()), 0.127)
        res = None
        for m in (6.0, 15.0, 40.0, 140.0):
            mz.MARGIN = m
            res = mz.route_pair(board, R, a, b, ni.GetNetCode(), w, nets_info)
            if res:
                break
        print(f"{net}: {a} -> {b}: {'routed ' + str(res) + f' (window {m})' if res else 'FAILED'}", flush=True)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]), sys.argv[2:])
