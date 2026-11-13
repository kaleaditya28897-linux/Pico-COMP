#!/usr/bin/env python3
"""Merge same-net vias whose drills are closer than the hole-to-hole rule (left by maze_route.py next to a
fan-out via). Keeps the locked (or larger) via, deletes the other and moves the track ends that met it onto
the kept via. Run: python3 hardware/mainboard/merge_vias.py board.kicad_pcb  (then re-run DRC).
"""
import math
import sys

import pcbnew

HOLE_TO_HOLE = 0.25    # mm, board setup


def main(path):
    b = pcbnew.LoadBoard(path)
    vias = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]
    gone, merged = set(), 0
    for i, a in enumerate(vias):
        for c in vias[i + 1:]:
            if id(a) in gone or id(c) in gone or a.GetNetCode() != c.GetNetCode():
                continue
            pa, pc = a.GetPosition(), c.GetPosition()
            d = math.hypot(pa.x - pc.x, pa.y - pc.y) / 1e6
            if d - (a.GetDrill() + c.GetDrill()) / 2e6 >= HOLE_TO_HOLE:
                continue
            keep, drop = (a, c) if (a.IsLocked(), a.GetWidth()) >= (c.IsLocked(), c.GetWidth()) else (c, a)
            kp, dp = keep.GetPosition(), drop.GetPosition()
            for t in b.GetTracks():
                if t.GetClass() == "PCB_VIA" or t.GetNetCode() != drop.GetNetCode():
                    continue
                if t.GetStart() == dp:
                    t.SetStart(kp)
                if t.GetEnd() == dp:
                    t.SetEnd(kp)
            gone.add(id(drop))
            b.Delete(drop)
            merged += 1
    for t in list(b.GetTracks()):          # tracks the snap shrank to nothing
        if t.GetClass() != "PCB_VIA" and t.GetStart() == t.GetEnd():
            b.Delete(t)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(path, b)
    print("merged vias:", merged)


if __name__ == "__main__":
    main(sys.argv[1])
