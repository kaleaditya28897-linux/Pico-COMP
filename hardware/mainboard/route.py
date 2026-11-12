#!/usr/bin/env python3
"""Autoroute a KiCad board with Freerouting, then fill zones and save in place.

Usage: python3 route.py board.kicad_pcb [max_passes]
Needs Java 21 (/usr/lib/jvm/openjdk21) and freerouting.jar (FREEROUTING_JAR env, default
~/.cache/freerouting-2.1.0.jar, downloaded from the GitHub release if missing).
"""
import os
import subprocess
import sys
import tempfile
import urllib.request

import pcbnew
from ses_import import import_ses

JAVA = os.environ.get("JAVA21", "/usr/lib/jvm/openjdk21/bin/java")
JAR = os.environ.get("FREEROUTING_JAR", os.path.expanduser("~/.cache/freerouting-2.1.0.jar"))
URL = "https://github.com/freerouting/freerouting/releases/download/v2.1.0/freerouting-2.1.0.jar"


def main():
    path = os.path.abspath(sys.argv[1])
    passes = sys.argv[2] if len(sys.argv) > 2 else "40"
    if not os.path.exists(JAR):
        os.makedirs(os.path.dirname(JAR), exist_ok=True)
        urllib.request.urlretrieve(URL, JAR)
    board = pcbnew.LoadBoard(path)
    for t in list(board.GetTracks()):          # start from a clean ratsnest
        board.Remove(t)
    tmp = tempfile.mkdtemp()
    dsn, ses = os.path.join(tmp, "b.dsn"), os.path.join(tmp, "b.ses")
    assert pcbnew.ExportSpecctraDSN(board, dsn), "DSN export failed"
    subprocess.run([JAVA, "-jar", JAR, "-de", dsn, "-do", ses, "-mp", passes, "-mt", "1"], check=True)
    assert os.path.exists(ses), "freerouting produced no session file"
    print("imported segs/vias:", import_ses(board, ses))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    print("routed:", len(board.GetTracks()), "track/via items ->", path)


if __name__ == "__main__":
    main()
