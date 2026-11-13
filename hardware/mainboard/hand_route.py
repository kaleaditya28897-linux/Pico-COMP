#!/usr/bin/env python3
"""Hand routes for the nets Freerouting cannot finish (route.py --skip=...). Run after route.py:

    python3 hardware/mainboard/hand_route.py hardware/kicad/mainboard.kicad_pcb

Each route is a polyline on one layer from pad to pad (board mm). The script replaces any existing
tracks of those nets, refills zones and saves; then check with kicad-cli DRC.
"""
import sys

import pcbnew

ROUTES = {
    # AP63203 BST (U7.6) -> bootstrap cap C71.1: straight across on F.Cu
    "BST3": [(pcbnew.F_Cu, 0.25, [(91.138, 9.05), (92.0, 9.0), (95.52, 9.0)])],
    # BQ25798 BATP (U5.18) -> 100R R59.1: east out of the pin row, down under C57, across to R59
    "VBATP": [(pcbnew.F_Cu, 0.15, [(29.875, 26.8), (31.0, 26.8), (33.3, 29.1), (38.9, 29.1), (39.49, 29.0)])],
    # TPS22917 CT (U9.4) -> C69.1: around the bottom of U9 (C69 sits on the far side)
    "PANEL_CT": [(pcbnew.F_Cu, 0.15, [(77.138, 9.95), (77.138, 11.3), (72.32, 11.3), (72.32, 9.0)])],
}


def main(path):
    board = pcbnew.LoadBoard(path)
    for net, segs in ROUTES.items():
        ni = board.FindNet(net)
        assert ni, net
        for t in list(board.GetTracks()):
            if t.GetNetname() == net:
                board.Delete(t)
        for layer, width, pts in segs:
            for a, b in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(a[0]), pcbnew.FromMM(a[1])))
                t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(b[0]), pcbnew.FromMM(b[1])))
                t.SetLayer(layer)
                t.SetWidth(pcbnew.FromMM(width))
                t.SetNet(ni)
                board.Add(t)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    print("hand-routed:", ", ".join(ROUTES))


if __name__ == "__main__":
    main(sys.argv[1])
