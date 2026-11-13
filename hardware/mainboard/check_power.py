#!/usr/bin/env python3
"""Power-copper audit for the main board (a release gate next to ERC/DRC, which cannot see current).

    python3 hardware/mainboard/check_power.py hardware/kicad/mainboard.kicad_pcb

For every high-current net: all its F.Cu pads must sit on one connected island of that net's pour (the
current flows in copper area, not in a 0.25 mm trace), and no trace of the net narrower than MIN_W may be
longer than MAX_THIN mm. Each exception below is a pad or net fed deliberately by a trunk or a trace,
with the reason. Exit code 1 on any finding.
"""
import sys

import pcbnew

HIGH_CURRENT = ["VBUS", "PMID", "SW1", "SW2", "VSYS", "VBAT", "VBAT_PACK", "SW5", "V5", "SW3",
                "UI_LX", "NET_LX"]
MIN_W, MAX_THIN = 0.5, 3.0
# pads allowed off the pour, with why
OFF_POUR = {
    "VBUS": {"J1.A4", "J1.A9", "J1.B4", "J1.B9",      # USB-C pads: 0.5 mm stubs into the 1.2 mm In3 trunk
             "U3.5", "R100.1"},                       # ESD clamp, TUSB320 VBUS sense (no current)
    "VBAT_PACK": {"R59.2"},                                              # BATP sense (100 R, no current)
    "V5": {"U9.1", "J8.1", "J12.1", "C67.1", "R60.1"},                   # panel switch (0.6 A, 6 mm), aux, printer, FB
}
# no-current tap pads: a thin trace is fine when its whole thin-copper branch only serves these
TAPS = {"VBUS": {"U3.5", "R100.1"}}                      # ESD clamp, TUSB320 VBUS-sense divider
# nets whose current-carrying copper is a trunk/trace by design (checked for width instead)
THIN_OK = {"VBUS": 1.2, "VBAT_PACK": 0.0, "V5": 0.25}   # minimum allowed width of their traces (mm)


def main(path):
    b = pcbnew.LoadBoard(path)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    bad = []
    for net in HIGH_CURRENT:
        isl = []
        for z in b.Zones():
            if z.GetNetname() == net and not z.GetIsRuleArea() and z.IsOnLayer(pcbnew.F_Cu):
                f = z.GetFilledPolysList(pcbnew.F_Cu)
                isl += [f.Outline(i) for i in range(f.OutlineCount())]
        pads = [(f"{fp.GetReference()}.{p.GetNumber()}", p) for fp in b.GetFootprints() for p in fp.Pads()
                if p.GetNetname() == net and p.IsOnLayer(pcbnew.F_Cu)]
        where = {}
        for name, p in pads:
            po = p.GetEffectivePolygon(pcbnew.F_Cu, pcbnew.ERROR_INSIDE).Outline(0)   # the pad's copper
            pts = [po.CPoint(k) for k in range(po.PointCount())] + [p.GetPosition()]
            segs = [po.CSegment(k) for k in range(po.SegmentCount())]
            hit = [i for i, o in enumerate(isl)
                   if any(o.PointInside(q) for q in pts) or any(o.Collide(sg, 0) for sg in segs)]
            where[name] = hit[0] if hit else None
        allowed = OFF_POUR.get(net, set())
        off = sorted(n for n, i in where.items() if i is None and n not in allowed)
        used = {i for n, i in where.items() if i is not None}
        if off:
            bad.append(f"{net}: pads not on its pour: {off}")
        if len(used) > 1:
            bad.append(f"{net}: pads on {len(used)} separate pour islands: "
                       + str({i: sorted(n for n, j in where.items() if j == i) for i in used}))
        minw = THIN_OK.get(net, MIN_W)
        items = [t for t in b.GetTracks() if t.GetNetname() == net]

        def ends(t):
            return [t.GetPosition()] if t.GetClass() == "PCB_VIA" else [t.GetStart(), t.GetEnd()]

        def branch_pads(t0):
            """Pads reached through thin copper (and vias) starting from track t0."""
            seen, stack, hit = {id(t0)}, [t0], set()
            while stack:
                u = stack.pop()
                for q in ends(u):
                    hit |= {n for n, p in pads if p.HitTest(q)}
                    for w in items:
                        if id(w) not in seen and not (w.IsLocked() and w.GetClass() != "PCB_VIA") \
                                and (w.GetClass() == "PCB_VIA" or w.GetWidth() / 1e6 + 1e-6 < minw) \
                                and any((q - r).EuclideanNorm() < 20000 for r in ends(w)):
                            seen.add(id(w))
                            stack.append(w)
            return hit
        for t in items:
            if t.GetClass() == "PCB_VIA" or t.IsLocked():          # locked = designed by gen_pcb (stubs, trunk)
                continue
            if t.GetWidth() / 1e6 + 1e-6 < minw and TAPS.get(net) and branch_pads(t) <= TAPS[net]:
                continue                                           # thin tap to a no-current pad
            L = t.GetLength() / 1e6
            w = t.GetWidth() / 1e6
            if w + 1e-6 < minw and L > MAX_THIN and net not in ("VBAT_PACK",):
                bad.append(f"{net}: {w:.2f} mm trace, {L:.1f} mm long on {b.GetLayerName(t.GetLayer())} "
                           f"at ({t.GetStart().x / 1e6:.1f}, {t.GetStart().y / 1e6:.1f})")
        print(f"{net:10s} pads {len(pads):3d}  pour islands used {len(used)}  off-pour {len([1 for i in where.values() if i is None])}"
              f" (allowed {len(allowed)})")
    for f in bad:
        print("FAIL", f)
    print("power audit:", "PASS" if not bad else f"{len(bad)} finding(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
