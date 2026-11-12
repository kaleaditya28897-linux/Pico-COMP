"""Minimal Specctra SES -> KiCad tracks/vias importer (pcbnew's own importer rejects Freerouting 2.x output)."""
import re
import pcbnew


def import_ses(board, ses_path):
    toks = re.findall(r'\(|\)|"[^"]*"|[^\s()]+', open(ses_path).read())
    pos = 0

    def parse():
        nonlocal pos
        pos += 1                      # '('
        node = []
        while toks[pos] != ')':
            if toks[pos] == '(':
                node.append(parse())
            else:
                node.append(toks[pos].strip('"'))
                pos += 1
        pos += 1
        return node
    root = parse()
    routes = next(n for n in root if isinstance(n, list) and n[0] == 'routes')
    res = next(n for n in routes if isinstance(n, list) and n[0] == 'resolution')
    unit = {'um': 1000, 'mm': 1000000, 'mil': 25400}[res[1]] / float(res[2])   # nm per SES unit
    net_out = next(n for n in routes if isinstance(n, list) and n[0] == 'network_out')
    layer = {board.GetLayerName(i): i for i in range(pcbnew.PCB_LAYER_ID_COUNT) if pcbnew.IsCopperLayer(i) and board.IsLayerEnabled(i)}
    vias = 0
    segs = 0
    for net in net_out[1:]:
        item = board.FindNet(net[1])
        for e in net[2:]:
            if e[0] == 'wire':
                p = e[1]
                if p[0] != 'path':
                    continue
                lay, w = layer[p[1]], int(float(p[2]) * unit)
                pts = [(int(float(p[i]) * unit), -int(float(p[i + 1]) * unit)) for i in range(3, len(p), 2)]
                for a, b in zip(pts, pts[1:]):
                    t = pcbnew.PCB_TRACK(board)
                    t.SetStart(pcbnew.VECTOR2I(*a)); t.SetEnd(pcbnew.VECTOR2I(*b))
                    t.SetLayer(lay); t.SetWidth(w); t.SetNet(item)
                    board.Add(t); segs += 1
            elif e[0] == 'via':
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pcbnew.VECTOR2I(int(float(e[2]) * unit), -int(float(e[3]) * unit)))
                m = re.search(r'_(\d+):(\d+)_um', e[1])
                v.SetWidth(int(m.group(1)) * 1000); v.SetDrill(int(m.group(2)) * 1000)
                v.SetNet(item); board.Add(v); vias += 1
    return segs, vias
