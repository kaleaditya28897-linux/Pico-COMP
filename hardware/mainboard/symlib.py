"""Minimal KiCad symbol-library reader: pin number -> name, and default footprint."""
import re

SYM = "/usr/share/kicad/symbols"


def _block(text, name):
    m = re.search(r'\(symbol "%s"' % re.escape(name), text)
    if not m:
        raise KeyError(name)
    i, depth = m.start(), 0
    for j in range(i, len(text)):
        depth += (text[j] == "(") - (text[j] == ")")
        if depth == 0:
            return text[i:j + 1]
    raise ValueError(name)


def load(lib, name):
    text = open(f"{SYM}/{lib}.kicad_sym").read()
    blk = _block(text, name)
    ext = re.search(r'\(extends "([^"]+)"', blk)
    if ext:                                   # derived symbol: pins come from parent
        parent = _block(text, ext.group(1))
        pins_src = parent
    else:
        pins_src = blk
    pins = {}
    for m in re.finditer(r'\(pin \w+ \w+.*?\(name "([^"]*)".*?\(number "([^"]*)"', pins_src, re.S):
        pins.setdefault(m.group(1), []).append(m.group(2))
    fp = re.search(r'\(property "Footprint" "([^"]*)"', blk) or re.search(r'\(property "Footprint" "([^"]*)"', pins_src)
    return pins, (fp.group(1) if fp else "")


if __name__ == "__main__":
    import sys
    pins, fp = load(sys.argv[1], sys.argv[2])
    print(fp)
    for n, nums in pins.items():
        print(n, nums)
