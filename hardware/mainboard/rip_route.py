#!/usr/bin/env python3
"""Rip-up and reroute for connections maze_route.py can't reach because other nets' copper walls them in
(typically a BGA ball or fine-pitch pin whose escape gaps are already taken).

    python3 hardware/mainboard/rip_route.py board.kicad_pcb [radius_mm] [rounds]

For each DRC-unconnected pair: delete other nets' unlocked tracks and vias within `radius` of either
endpoint, route the trapped net first (maze_route, wide window), then reroute everything that opened.
A round is kept only if the total number of unconnected pairs went down; otherwise the board is
restored. Locked copper (fan-out) is never touched. Check the result with KiCad DRC.
"""
import math
import os
import shutil
import sys

import pcbnew

import maze_route as mz


def near(t, p, r):
    """Track or via t within r mm of point p (mm)."""
    px, py = pcbnew.FromMM(p[0]), pcbnew.FromMM(p[1])
    if t.GetClass() == "PCB_VIA":
        q = t.GetPosition()
        return math.hypot(q.x - px, q.y - py) <= pcbnew.FromMM(r)
    a, b = t.GetStart(), t.GetEnd()
    dx, dy = b.x - a.x, b.y - a.y
    L2 = dx * dx + dy * dy
    u = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - a.x) * dx + (py - a.y) * dy) / L2))
    return math.hypot(a.x + u * dx - px, a.y + u * dy - py) <= pcbnew.FromMM(r)


def opens(path):
    return mz.drc_unconnected(path)


def main(path, radius=1.5, rounds=3):
    bak = path + ".rip-bak"
    for rnd in range(rounds):
        pairs = opens(path)
        print(f"round {rnd}: {len(pairs)} unconnected", flush=True)
        if not pairs:
            return 0
        progress = False
        for a, b, ua, ub in pairs:
            before = len(opens(path))
            if before == 0:
                return 0
            shutil.copy(path, bak)
            board = pcbnew.LoadBoard(path)
            item = {t.m_Uuid.AsString(): t for t in list(board.GetTracks()) + list(board.GetPads())}.get(ua)
            if item is None:
                continue
            net = item.GetNetname()
            victims = [t for t in board.GetTracks() if not t.IsLocked() and t.GetNetname() != net
                       and (near(t, a, radius) or near(t, b, radius))]
            for t in victims:
                board.Delete(t)
            pcbnew.SaveBoard(path, board)
            mz.main(path, {net}, passes=(15.0, 60.0))         # the trapped net first
            mz.main(path, None, passes=(6.0, 15.0, 40.0))     # then whatever the rip opened
            after = len(opens(path))
            ok = after < before
            print(f"  {net}: ripped {len(victims)}, unconnected {before} -> {after}"
                  + ("" if ok else " (reverted)"), flush=True)
            if ok:
                progress = True
            else:
                shutil.copy(bak, path)
        if not progress:
            radius *= 1.6                                     # nothing gave: rip a wider area next round
    left = len(opens(path))
    print("left:", left)
    return left


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]), *(float(x) for x in sys.argv[2:3]), *(int(x) for x in sys.argv[3:4]))
