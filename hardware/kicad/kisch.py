"""Minimal KiCad schematic writer driven by a generated PCB (used by gen_sch.py for both boards).

The PCB is the netlist source: every footprint becomes a library symbol, every symbol pin gets a
net label at its tip (no wires), unconnected pins get no-connect flags, and nets fed only by
power-input pins get a PWR_FLAG. The PCB footprints are then linked to the new symbols (path,
sheet) so KiCad's schematic-parity DRC and "Update PCB from Schematic" work.
"""
import os
import re
import uuid

SYMDIR = "/usr/share/kicad/symbols"
GRID = 1.27
NS = uuid.UUID("6f1f2c1e-5b0a-4bb8-9a0f-7d3c2a9e0c11")


# ------------------------------------------------------------------ s-expressions
class Q(str):
    """A quoted string atom."""


def parse(text):
    toks = re.findall(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+', text)
    pos = 0

    def rd():
        nonlocal pos
        t = toks[pos]
        pos += 1
        if t == "(":
            out = []
            while toks[pos] != ")":
                out.append(rd())
            pos += 1
            return out
        if t.startswith('"'):
            return Q(bytes(t[1:-1], "utf-8").decode("unicode_escape") if "\\" in t else t[1:-1])
        return t
    return rd()


def dump(x, ind=0):
    if isinstance(x, list):
        if not any(isinstance(e, list) for e in x):
            return "(" + " ".join(dump(e) for e in x) + ")"
        head = [dump(e) for e in x[:1]]
        parts = []
        for e in x[1:]:
            parts.append(("\n" + "  " * (ind + 1) + dump(e, ind + 1)) if isinstance(e, list) else " " + dump(e))
        return "(" + head[0] + "".join(parts) + ")"
    if isinstance(x, Q):
        return '"' + x.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    return str(x)


def find(node, key):
    return [e for e in node if isinstance(e, list) and e and e[0] == key]


def first(node, key):
    r = find(node, key)
    return r[0] if r else None


# ------------------------------------------------------------------ symbol library
_libcache = {}


def _lib(lib, extra_dirs):
    if lib not in _libcache:
        for d in list(extra_dirs) + [SYMDIR]:
            p = os.path.join(d, f"{lib}.kicad_sym")
            if os.path.exists(p):
                _libcache[lib] = parse(open(p).read())
                break
        else:
            raise FileNotFoundError(lib)
    return _libcache[lib]


def load_symbol(lib, name, extra_dirs=()):
    """Flattened symbol (extends resolved), renamed to 'lib:name' for lib_symbols."""
    root = _lib(lib, extra_dirs)
    sym = next(s for s in find(root, "symbol") if s[1] == name)
    ext = first(sym, "extends")
    if ext:
        parent = load_symbol(lib, ext[1], extra_dirs)
        props = {p[1]: p for p in find(sym, "property")}
        out = [e for e in parent if not (isinstance(e, list) and e[0] == "property" and e[1] in props)]
        out = [e for e in out if not (isinstance(e, list) and e[0] == "symbol")]
        out += list(props.values())
        for sub in find(parent, "symbol"):
            sub = list(sub)
            sub[1] = Q(name + sub[1][sub[1].rindex("_", 0, sub[1].rindex("_")):])
            out.append(sub)
        sym = out
    sym = [e for e in sym if not (isinstance(e, list) and e[0] == "extends")]
    sym = list(sym)
    full = f"{lib}:{name}"
    subs = []
    for e in sym[2:]:
        if isinstance(e, list) and e[0] == "symbol":
            e = list(e)
            suffix = e[1][len(e[1].rsplit("_", 2)[0]):]
            e[1] = Q(name + suffix)
            subs.append(e)
    return [sym[0], Q(full)] + [e for e in sym[2:] if not (isinstance(e, list) and e[0] == "symbol")] + subs


def pins_of(sym, unit):
    """[(number, name, x, y, angle, etype)] for a unit (unit-0 pins are common), De Morgan style 1."""
    out = []
    for sub in find(sym, "symbol"):
        u, st = (int(v) for v in sub[1].rsplit("_", 2)[1:])
        if u not in (0, unit) or st not in (0, 1):
            continue
        for p in find(sub, "pin"):
            at = first(p, "at")
            out.append((first(p, "number")[1], first(p, "name")[1], float(at[1]), float(at[2]),
                        int(float(at[3])) if len(at) > 3 else 0, p[1]))
    return out


def units_of(sym):
    us = sorted({int(sub[1].rsplit("_", 2)[1]) for sub in find(sym, "symbol")} - {0})
    return us or [1]


def extent(sym, unit):
    """Body + pin bbox in library coordinates (y up)."""
    xs, ys = [], []
    for sub in find(sym, "symbol"):
        u, st = (int(v) for v in sub[1].rsplit("_", 2)[1:])
        if u not in (0, unit) or st not in (0, 1):
            continue
        for g in sub[2:]:
            if not isinstance(g, list):
                continue
            for k in ("start", "end", "center", "at", "mid"):
                for e in find(g, k):
                    xs.append(float(e[1]))
                    ys.append(float(e[2]))
            for pts in find(g, "pts"):
                for xy in find(pts, "xy"):
                    xs.append(float(xy[1]))
                    ys.append(float(xy[2]))
    if not xs:
        return -2.54, -2.54, 2.54, 2.54
    return min(xs), min(ys), max(xs), max(ys)


# ------------------------------------------------------------------ schematic writer
def uid(*k):
    return str(uuid.uuid5(NS, "/".join(map(str, k))))


def snap(v):
    return round(round(v / GRID) * GRID, 4)


def font(size=1.27, hide=False, justify=None):
    e = ["effects", ["font", ["size", size, size]]]
    if justify:
        e.append(["justify"] + justify)
    if hide:
        e.append(["hide", "yes"])
    return e


class Schematic:
    def __init__(self, project, title, paper="A1", extra_dirs=()):
        self.project = project
        self.root = uid(project, "root")
        self.items = []
        self.libsyms = {}
        self.extra_dirs = extra_dirs
        self.paper = paper
        self.title = title
        self.links = {}           # ref -> symbol uuid (first unit)
        self.netpins = {}         # net -> [etype]
        self.flagged = set()

    def symbol(self, lib, name):
        key = f"{lib}:{name}"
        if key not in self.libsyms:
            self.libsyms[key] = load_symbol(lib, name, self.extra_dirs)
        return self.libsyms[key]

    def text(self, s, x, y, size=2.5):
        self.items.append(["text", Q(s), ["exclude_from_sim", "no"], ["at", snap(x), snap(y), 0],
                           font(size, justify=["left", "bottom"]), ["uuid", uid(self.project, "text", s, x, y)]])

    def label(self, net, x, y, ang):
        just = ["left", "bottom"] if ang in (0, 90) else ["right", "bottom"]
        self.items.append(["global_label", Q(net), ["shape", "passive"], ["at", x, y, ang],
                           ["fields_autoplaced", "yes"], font(1.27, justify=[just[0]]),
                           ["uuid", uid(self.project, "label", net, x, y)],
                           ["property", Q("Intersheetrefs"), Q("${INTERSHEET_REFS}"), ["at", x, y, 0],
                            font(1.27, hide=True)]])

    def place(self, ref, lib, name, x, y, value, footprint, pad_nets, fields=(), unit=1):
        """Place one unit at (x, y); label its pins from pad_nets {pad number: net}."""
        sym = self.symbol(lib, name)
        su = uid(self.project, "sym", ref, unit)
        self.links.setdefault(ref, su)
        self.fields = getattr(self, "fields", {})
        props = {p[1]: p for p in find(sym, "property")}
        x0, y0, x1, y1 = extent(sym, unit)
        node = ["symbol", ["lib_id", Q(f"{lib}:{name}")], ["at", x, y, 0], ["unit", unit],
                ["exclude_from_sim", "no"], ["in_bom", "no" if ref.startswith(("H", "FID", "#")) else "yes"],
                ["on_board", "yes"], ["dnp", "no"], ["uuid", su]]
        vals = {"Reference": ref, "Value": value, "Footprint": footprint,
                "Datasheet": props["Datasheet"][2] if "Datasheet" in props else "",
                "Description": props["Description"][2] if "Description" in props else ""}
        vals.update(dict(fields))
        self.fields[ref] = {k: vals[k] for k in ("Datasheet", "Description")}
        for i, (k, v) in enumerate(vals.items()):
            if k == "Reference":
                at = ["at", snap(x + x0), snap(y - y1 - 1.5), 0]
                eff = font(1.27, justify=["left", "bottom"])
            elif k == "Value":
                at = ["at", snap(x + x0), snap(y - y0 + 2.0), 0]
                eff = font(1.27, justify=["left", "top"])
            else:
                at = ["at", x, y, 0]
                eff = font(1.27, hide=True)
            node.append(["property", Q(k), Q(v), at, eff])
        for (num, pname, px, py, ang, etype) in pins_of(sym, unit):
            node.append(["pin", Q(num), ["uuid", uid(self.project, "pin", ref, num)]])
        node.append(["instances", ["project", Q(self.project),
                                   ["path", Q("/" + self.root), ["reference", Q(ref)], ["unit", unit]]]])
        self.items.append(node)
        # labels / no-connects at the pin tips (library y is up, schematic y is down)
        for (num, pname, px, py, ang, etype) in pins_of(sym, unit):
            tx, ty = round(x + px, 4), round(y - py, 4)
            net = pad_nets.get(num)
            if net:
                self.label(net, tx, ty, (ang + 180) % 360)
                self.netpins.setdefault(net, []).append(etype)
            elif not ref.startswith("#"):
                self.items.append(["no_connect", ["at", tx, ty], ["uuid", uid(self.project, "nc", ref, num, unit)]])
                self.nc = getattr(self, "nc", {})
                self.nc[(ref, num)] = pname
        return sym

    def size(self, lib, name, unit, pad_nets, longest=None):
        """Footprint of a placed unit including label text, in schematic units (w, h, x-offset, y-offset)."""
        sym = self.symbol(lib, name)
        x0, y0, x1, y1 = extent(sym, unit)
        lab = 1.0 * (longest or max([len(n) for n in pad_nets.values()] + [0])) + 2.0
        left = any(ang == 0 and px <= x0 + 0.01 for (_, _, px, _, ang, _) in pins_of(sym, unit))
        right = any(ang == 180 and px >= x1 - 0.01 for (_, _, px, _, ang, _) in pins_of(sym, unit))
        up = any(ang == 270 for (*_, ang, _) in pins_of(sym, unit))
        down = any(ang == 90 for (*_, ang, _) in pins_of(sym, unit))
        l = (lab if left else 0) + 2
        r = (lab if right else 0) + 2
        t = (lab if up else 0) + 4
        b = (lab if down else 0) + 5
        return (x1 - x0) + l + r, (y1 - y0) + t + b, l - x0, t + y1

    def power_flags(self, x, y):
        """PWR_FLAG on nets that only have power-input pins (ERC: 'power pin not driven')."""
        i = 0
        for net, types in sorted(self.netpins.items()):
            if "power_in" in types and "power_out" not in types:
                ref = f"#FLG{i + 1:02d}"
                px, py = snap(x + (i % 8) * 20), snap(y + (i // 8) * 12)
                self.place(ref, "power", "PWR_FLAG", px, py, "PWR_FLAG", "", {"1": net})
                i += 1

    def save(self, path, date=""):
        lib = ["lib_symbols"] + list(self.libsyms.values())
        sch = ["kicad_sch", ["version", "20250114"], ["generator", Q("pico-comp-gen_sch")],
               ["generator_version", Q("9.0")], ["uuid", self.root], ["paper", Q(self.paper)],
               ["title_block", ["title", Q(self.title)], ["date", Q(date)], ["rev", Q("1.0")],
                ["company", Q("Pico-COMP")],
                ["comment", 1, Q("Generated from the PCB generator netlist; pins connect by net labels.")]],
               lib] + self.items + [["sheet_instances", ["path", Q("/"), ["page", Q("1")]]],
                                    ["embedded_fonts", "no"]]
        open(path, "w").write(dump(sch) + "\n")


def link_pcb(board, sch, sheetfile):
    """Point every footprint at its schematic symbol so parity checks pass."""
    import pcbnew
    for fp in board.GetFootprints():
        su = sch.links.get(fp.GetReference())
        if su:
            fp.SetPath(pcbnew.KIID_PATH(f"/{su}"))
            for pad in fp.Pads():
                pname = getattr(sch, "nc", {}).get((fp.GetReference(), pad.GetNumber()))
                if pname is not None and not pad.GetNetname():
                    pn = "" if pname in ("", "~") else pname.replace("/", "{slash}") + "-"
                    name = f"unconnected-({fp.GetReference()}-{pn}Pad{pad.GetNumber()})"
                    net = board.FindNet(name)
                    if not net:
                        net = pcbnew.NETINFO_ITEM(board, name)
                        board.Add(net)
                    pad.SetNet(net)
            for k, v in sch.fields.get(fp.GetReference(), {}).items():
                fp.SetField(k, str(v))
                fp.GetField(k).SetVisible(False)
            fp.SetSheetfile(sheetfile)
            fp.SetSheetname("/")
