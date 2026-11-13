#!/usr/bin/env python3
"""Autoroute a KiCad board with Freerouting, then fill zones and save in place.

Usage: python3 route.py board.kicad_pcb [max_passes] [--skip=NET1,NET2] [--keep]
       python3 route.py --cleanup board.kicad_pcb      (only remove router leftovers)
       python3 route.py --import board.kicad_pcb file.ses  (re-import a Freerouting session)
Needs Java 21 (/usr/lib/jvm/openjdk21) and freerouting.jar (FREEROUTING_JAR env, default
~/.cache/freerouting-2.1.0.jar, downloaded from the GitHub release if missing).
"""
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

import pcbnew
from ses_import import import_ses

JAVA = os.environ.get("JAVA21", "/usr/lib/jvm/openjdk21/bin/java")
JAR = os.environ.get("FREEROUTING_JAR", os.path.expanduser("~/.cache/freerouting-2.1.0.jar"))
URL = "https://github.com/freerouting/freerouting/releases/download/v2.1.0/freerouting-2.1.0.jar"


# nets whose every pad sits on its own F.Cu pour (gen_pcb.py PWR_* / VREG_*): nothing for the router to do
POUR_ONLY = ["PMID", "SW1", "SW2", "SW3", "SW5", "VSYS", "VBAT", "VBAT_PACK", "UI_LX", "NET_LX"]


def remove_dangling(board, path):
    """Router clean-up: zero-length and duplicate segments, then whatever KiCad's DRC itself reports
    as track_dangling / via_dangling (deleted by UUID, repeated until none). Saves to `path`."""
    import json
    removed = 0
    seen = set()
    for t in sorted(board.GetTracks(), key=lambda t: not t.IsLocked()):   # locked first: keep those
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            key = ("v", p.x, p.y, t.GetNetCode())
        else:
            a, b = sorted([(t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y)])
            if a == b:
                board.Delete(t)
                removed += 1
                continue
            key = (t.GetLayer(), a, b, t.GetNetCode())
        if key in seen and not t.IsLocked():
            board.Delete(t)
            removed += 1
        else:
            seen.add(key)
    rpt = os.path.join(tempfile.mkdtemp(), "drc.json")
    while True:
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(path, board)
        subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all", "-o", rpt, path],
                       check=True, capture_output=True)
        ids = {it["uuid"] for v in json.load(open(rpt))["violations"]
               if v["type"] in ("track_dangling", "via_dangling") for it in v["items"]}
        # locked copper is the fan-out (plane vias, BGA via-in-pad, dog-bones): it can look dangling
        # before its route exists, or where a pad's only other connection is a plane, so keep it
        dead = [t for t in board.GetTracks() if t.m_Uuid.AsString() in ids and not t.IsLocked()]
        if not dead:
            return removed
        for t in dead:
            board.Delete(t)
        removed += len(dead)


def main():
    path = os.path.abspath(sys.argv[1])
    passes = sys.argv[2] if len(sys.argv) > 2 else "40"
    if not os.path.exists(JAR):
        os.makedirs(os.path.dirname(JAR), exist_ok=True)
        urllib.request.urlretrieve(URL, JAR)
    board = pcbnew.LoadBoard(path)
    if "--keep" not in sys.argv:                # --keep: start from the existing (e.g. maze-routed) copper
        for t in list(board.GetTracks()):      # clear earlier autorouting; locked items (fan-out) stay
            if not t.IsLocked():
                board.Delete(t)
    tmp = tempfile.mkdtemp()
    dsn, ses = os.path.join(tmp, "b.dsn"), os.path.join(tmp, "b.ses")
    # hide every pour on a signal layer (named POUR_*) from the router: it would treat them as planes
    # that other nets can't cross, and its own tracks would then split them. Nets are routed as traces
    # (plane-layer zones like the In1 GND plane stay), and the pours fill around them afterwards.
    pours = [z for z in board.Zones() if z.GetZoneName().startswith("POUR_")]
    for z in pours:
        board.Remove(z)
    assert pcbnew.ExportSpecctraDSN(board, dsn), "DSN export failed"
    for z in pours:
        board.Add(z)
    skip = [n for a in sys.argv[3:] if a.startswith("--skip=") for n in a[7:].split(",")]
    # F.Cu pours (PWR_* power stages, VREG_* RP2350 regulators): KiCad exports them as "plane" areas, which
    # Freerouting happily routes other nets through (it expects planes to be split). Add a matching F.Cu
    # keep-out for each, and leave out the nets those pours connect completely.
    txt = open(dsn).read()
    polys = re.findall(r'\(plane "?([^\s"]+)"? \(polygon F\.Cu 0 ([^)]*)\)\)', txt)
    if polys:
        ko = "".join(f'    (keepout "" (polygon F.Cu 0 {pts.strip()}))\n' for _, pts in polys)
        txt = txt.replace("    (plane ", ko + "    (plane ", 1)
        open(dsn, "w").write(txt)
        skip += [n for n in POUR_ONLY if n not in skip]
        print(f"pour keep-outs: {len(polys)}")
    if skip:                     # leave these nets out (Freerouting retries an unroutable net forever)
        txt = open(dsn).read()
        for n in skip:
            txt = re.sub(r'\(net "?%s"?\s*\(pins[^)]*\)\s*\)' % re.escape(n), "", txt)
            txt = re.sub(r'(\(class [^(]*?)\s"?%s"?(?=[\s)])' % re.escape(n), r"\1", txt)
        open(dsn, "w").write(txt)
        print("skipped nets (route them by hand):", skip)
    # headless: with the GUI flag on (Freerouting's saved default) it routes, then never writes the session
    subprocess.run([JAVA, "-jar", JAR, "--gui.enabled=false", "--usage_and_diagnostic_data.disable_analytics=true",
                    "--feature_flags.multi_threading=false", f"--router.max_passes={passes}",
                    *os.environ.get("ROUTE_EXTRA", "").split(),
                    "-de", dsn, "-do", ses, "-mp", passes, "-mt", "1"],
                   check=True)
    assert os.path.exists(ses), "freerouting produced no session file"
    # the session holds the whole routed board: drop the unlocked copper it started from (--keep), or
    # wires Freerouting ripped up would stay behind next to their replacements
    for t in list(board.GetTracks()):
        if not t.IsLocked():
            board.Delete(t)
    print("imported segs/vias:", import_ses(board, ses))
    print("removed dangling track/via items:", remove_dangling(board, path))
    print("routed:", len(board.GetTracks()), "track/via items ->", path)


def prune_fanout(board, path):
    """Final step once everything is connected: delete fan-out that the routing never used (dog-bone and
    BGA vias reported dangling, then the stubs that leaves), locked or not; plane nets are left alone."""
    import json
    rpt = os.path.join(tempfile.mkdtemp(), "drc.json")
    removed = 0
    while True:
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(path, board)
        subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all", "-o", rpt, path],
                       check=True, capture_output=True)
        ids = {it["uuid"] for v in json.load(open(rpt))["violations"]
               if v["type"] in ("track_dangling", "via_dangling") for it in v["items"]}
        dead = [t for t in board.GetTracks() if t.m_Uuid.AsString() in ids and t.GetNetname() not in ("GND", "V3V3")]
        if not dead:
            return removed
        for t in dead:
            board.Delete(t)
        removed += len(dead)


if __name__ == "__main__":
    if sys.argv[1] == "--prune":                      # drop unused fan-out from a fully routed board
        p = os.path.abspath(sys.argv[2])
        print("pruned:", prune_fanout(pcbnew.LoadBoard(p), p))
    elif sys.argv[1] == "--cleanup":                  # clean an already-routed board in place
        p = os.path.abspath(sys.argv[2])
        print("removed:", remove_dangling(pcbnew.LoadBoard(p), p))
    elif sys.argv[1] == "--import":                   # route.py --import board.kicad_pcb session.ses
        p = os.path.abspath(sys.argv[2])
        brd = pcbnew.LoadBoard(p)
        for t in list(brd.GetTracks()):
            brd.Delete(t)
        print("imported segs/vias:", import_ses(brd, sys.argv[3]))
        print("removed:", remove_dangling(brd, p))
    else:
        main()
