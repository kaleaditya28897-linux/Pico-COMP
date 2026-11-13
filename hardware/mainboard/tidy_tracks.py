#!/usr/bin/env python3
"""Merge collinear track segments that meet end to end (same net, layer, width) into single tracks.

    python3 hardware/mainboard/tidy_tracks.py board.kicad_pcb

Grid routers leave a segment per grid step; this joins them so the board stays easy to edit in KiCad.
Connectivity is unchanged (a merged track passes through every removed joint). Locked tracks are kept.
"""
import collections
import sys

import pcbnew


def run(path):
    board = pcbnew.LoadBoard(path)
    before = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_TRACK")
    vias = {(v.GetPosition().x, v.GetPosition().y) for v in board.GetTracks() if v.GetClass() == "PCB_VIA"}
    changed = True
    while changed:
        changed = False
        ends = collections.defaultdict(list)
        segs = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and not t.IsLocked()]
        for t in segs:
            for p in (t.GetStart(), t.GetEnd()):
                ends[(p.x, p.y, t.GetLayer(), t.GetNetCode())].append(t)
        dead = set()
        for (x, y, lay, net), ts in ends.items():
            if len(ts) != 2 or (x, y) in vias:
                continue
            a, b = ts
            if id(a) in dead or id(b) in dead or a.GetWidth() != b.GetWidth():
                continue
            pa = a.GetEnd() if (a.GetStart().x, a.GetStart().y) == (x, y) else a.GetStart()
            pb = b.GetEnd() if (b.GetStart().x, b.GetStart().y) == (x, y) else b.GetStart()
            ax, ay = x - pa.x, y - pa.y
            bx, by = pb.x - x, pb.y - y
            cross = ax * by - ay * bx
            if abs(cross) > 1e-6 * (abs(ax) + abs(ay)) * (abs(bx) + abs(by)) or ax * bx + ay * by <= 0:
                continue
            a.SetStart(pa)
            a.SetEnd(pb)
            board.Delete(b)
            dead.add(id(b))
            dead.add(id(a))          # re-evaluate a in the next sweep
            changed = True
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    after = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_TRACK")
    print(f"tidy: {before} -> {after} track segments")


if __name__ == "__main__":
    run(sys.argv[1])
