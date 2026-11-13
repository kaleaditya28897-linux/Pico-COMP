#!/usr/bin/env python3
"""Apply a netlist change from gen_pcb.py to the routed main board without re-routing it (an ECO).

    GEN_PCB_OUT=/tmp/x/mainboard.kicad_pcb python3 hardware/mainboard/gen_pcb.py
    python3 hardware/mainboard/eco.py /tmp/x/mainboard.kicad_pcb hardware/kicad/<routed>.kicad_pcb

Compares the fresh generator output with the routed board. Every footprint present in both must sit in
the same place (otherwise it stops: that is a placement change, not an ECO). Then it removes deleted
footprints, adds new ones, re-nets changed pads, deletes copper that now touches a pad of another net
(and all copper of nets that lost or changed a pad, so they get re-routed cleanly), and replaces the
power pours (POUR_*) with the generator's. Finish the new connections with maze_route.py and check DRC.
"""
import sys

import pcbnew


def pads(fp):
    return [(p.GetNumber(), p.GetNetname()) for p in fp.Pads()]


def main(gen_path, path):
    g = pcbnew.LoadBoard(gen_path)
    b = pcbnew.LoadBoard(path)
    G = {f.GetReference(): f for f in g.GetFootprints()}
    B = {f.GetReference(): f for f in b.GetFootprints()}
    for r in set(G) & set(B):
        assert G[r].GetPosition() == B[r].GetPosition() and G[r].GetOrientationDegrees() == \
            B[r].GetOrientationDegrees(), f"{r} moved: placement change, not an ECO"

    def net(name):
        if not name:
            return None
        n = b.FindNet(name)
        if n is None:
            n = pcbnew.NETINFO_ITEM(b, name)
            b.Add(n)
        return n

    touched = set()                                    # nets whose routing must be redone
    for r in sorted(set(B) - set(G)):                  # removed parts
        touched |= {p.GetNetname() for p in B[r].Pads() if p.GetNetname()}
        b.Delete(B[r])
        print("removed", r)
    for r in sorted(set(G) & set(B)):                  # re-netted pads
        for pb, pg in zip(B[r].Pads(), G[r].Pads()):
            old, new = pb.GetNetname(), pg.GetNetname()
            if old != new and not (old.startswith("unconnected-") and not new):
                if old and not old.startswith("unconnected-"):
                    touched.add(old)
                if new:
                    touched.add(new)
                pb.SetNet(net(new))
                print(f"renet {r}.{pb.GetNumber()}: {old} -> {new}")
        for k in ("MPN", "Spec"):
            if G[r].HasField(k):
                B[r].SetField(k, G[r].GetFieldText(k))
        B[r].SetValue(G[r].GetValue())
    for r in sorted(set(G) - set(B)):                  # new parts
        fp = G[r].Duplicate(False)
        fp = pcbnew.Cast_to_FOOTPRINT(fp) if not isinstance(fp, pcbnew.FOOTPRINT) else fp
        for p, pg in zip(fp.Pads(), G[r].Pads()):
            p.SetNet(net(pg.GetNetname()))
        b.Add(fp)
        touched |= {p.GetNetname() for p in fp.Pads() if p.GetNetname()}
        print("added", r, fp.GetValue())

    # power pours: take the generator's (their outlines follow the pads)
    for z in list(b.Zones()):
        if z.GetZoneName().startswith("POUR_"):
            b.Delete(z)
    for z in g.Zones():
        if z.GetZoneName().startswith("POUR_"):
            nz = z.Duplicate(False)
            nz = pcbnew.Cast_to_ZONE(nz) if not isinstance(nz, pcbnew.ZONE) else nz
            nz.SetNet(net(z.GetNetname()))
            b.Add(nz)

    # copper of re-netted / affected signal nets is re-routed from scratch (planes and pours stay)
    keep = {"GND", "V3V3"}
    dead = [t for t in b.GetTracks() if t.GetNetname() in touched - keep and not t.GetNetname().startswith("V")]
    # power nets (VBAT...): only copper that now lands on a pad of another net goes
    for t in b.GetTracks():
        if t in dead:
            continue
        for fp in b.GetFootprints():
            for p in fp.Pads():
                if p.GetNetname() == t.GetNetname() or not p.GetNetname():
                    continue
                if t.GetClass() == "PCB_VIA":
                    hit = p.HitTest(t.GetPosition())
                else:
                    hit = p.HitTest(t.GetStart()) or p.HitTest(t.GetEnd())
                if hit and (t.GetClass() == "PCB_VIA" or p.IsOnLayer(t.GetLayer())):
                    dead.append(t)
                    break
            else:
                continue
            break
    for t in dead:
        b.Delete(t)
    print("deleted copper items:", len(dead), "re-route nets:", sorted(touched - keep))
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(path, b)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
