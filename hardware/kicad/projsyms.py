"""Write hardware/kicad/pico-comp.kicad_sym (project symbols). Called by the gen_sch.py scripts."""
import os

here = os.path.dirname(os.path.abspath(__file__))

# RM2 pins (RP-008943 Table 2): (number, name, electrical type, side, slot)
RM2 = [
    ("16", "VIN", "power_in", "L", 0), ("14", "VDDIO", "power_in", "L", 1),
    ("12", "WL_ON", "input", "L", 3), ("13", "BT_ON", "input", "L", 4),
    ("9", "~{CS}", "input", "L", 6), ("3", "SCLK", "input", "L", 7),
    ("5", "DATA_IN", "input", "L", 8), ("6", "DATA_OUT", "output", "L", 9),
    ("10", "~{IRQ}", "output", "L", 10),
    ("8", "GPIO0", "bidirectional", "R", 0), ("18", "GPIO1", "bidirectional", "R", 1),
    ("17", "GPIO2", "bidirectional", "R", 2),
    ("2", "NC", "no_connect", "R", 4), ("19", "NC", "no_connect", "R", 5), ("20", "NC", "no_connect", "R", 6),
    ("1", "GND", "power_in", "B", 0), ("4", "GND", "passive", "B", 1), ("7", "GND", "passive", "B", 2),
    ("11", "GND", "passive", "B", 3), ("15", "GND", "passive", "B", 4), ("21", "GND", "passive", "B", 5),
]


def rm2():
    w, top = 12.7, 13.97
    pins = []
    for num, name, et, side, k in RM2:
        if side == "L":
            x, y, a = -w - 5.08, top - 2.54 - k * 2.54, 0
        elif side == "R":
            x, y, a = w + 5.08, top - 2.54 - k * 2.54, 180
        else:
            x, y, a = -6.35 + k * 2.54, -top - 5.08, 90
        hide = " hide" if side == "B" and k else ""
        pins.append(f'      (pin {et} line (at {x:.2f} {y:.2f} {a}) (length 5.08){hide}\n'
                    f'        (name "{name}" (effects (font (size 1.27 1.27))))\n'
                    f'        (number "{num}" (effects (font (size 1.27 1.27)))))\n')
    return f'''  (symbol "RaspberryPi_RM2" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)
    (property "Reference" "U" (at {-w:.2f} {top + 1.5:.2f} 0) (effects (font (size 1.27 1.27)) (justify left)))
    (property "Value" "RaspberryPi_RM2" (at {-w:.2f} {-top - 8:.2f} 0) (effects (font (size 1.27 1.27)) (justify left)))
    (property "Footprint" "pico-comp:RaspberryPi_RM2" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Datasheet" "https://datasheets.raspberrypi.com/rm2/rm2-datasheet.pdf" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Description" "Raspberry Pi Radio Module 2, CYW43439 Wi-Fi 4 + Bluetooth 5.2, gSPI, onboard antenna" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (symbol "RaspberryPi_RM2_0_1"
      (rectangle (start {-w:.2f} {top:.2f}) (end {w:.2f} {-top:.2f}) (stroke (width 0.254) (type default)) (fill (type background)))
    )
    (symbol "RaspberryPi_RM2_1_1"
{"".join(pins)}    )
  )
'''


# JEDEC eMMC 153-ball FBGA (11.5 x 13), ball map from the Kimtigo KM110SS1064GxA datasheet (v1.3 table 2.1)
EMMC_SIG = {"A3": "DAT0", "A4": "DAT1", "A5": "DAT2", "B2": "DAT3", "B3": "DAT4", "B4": "DAT5", "B5": "DAT6",
            "B6": "DAT7", "M5": "CMD", "M6": "CLK", "K5": "RSTN", "H5": "STROBE"}
EMMC_PWR = {"C2": "VDDi", "E6": "VCC", "F5": "VCC", "J10": "VCC", "K9": "VCC",
            "C6": "VCCQ", "M4": "VCCQ", "N4": "VCCQ", "P3": "VCCQ", "P5": "VCCQ"}
EMMC_GND = ["A6", "C4", "E7", "G5", "H10", "J5", "K8", "N2", "N5", "P4", "P6"]


def emmc_balls():
    import re
    fp = "/usr/share/kicad/footprints/Package_BGA.pretty/LFBGA-153_11.5x13mm_Layout14x14_P0.5mm.kicad_mod"
    return sorted(set(re.findall(r'\(pad "([A-Z][0-9]+)"', open(fp).read())), key=lambda b: (b[0], int(b[1:])))


def emmc():
    w, top = 12.7, 20.32
    pins = []

    def pin(num, name, et, x, y, a, hide=False):
        pins.append(f'      (pin {et} line (at {x:.2f} {y:.2f} {a}) (length 5.08){" hide" if hide else ""}\n'
                    f'        (name "{name}" (effects (font (size 1.27 1.27))))\n'
                    f'        (number "{num}" (effects (font (size 1.27 1.27)))))\n')
    left = ["M6", "M5", "A3", "A4", "A5", "B2", "B3", "B4", "B5", "B6", "K5", "H5"]
    for i, b in enumerate(left):
        pin(b, EMMC_SIG[b], "bidirectional" if b != "M6" else "input", -w - 5.08, top - 2.54 - i * 2.54 - (2.54 if i >= 2 else 0) - (2.54 if i >= 10 else 0), 0)
    right = list(EMMC_PWR)
    for i, b in enumerate(right):
        stacked = EMMC_PWR[b] in [EMMC_PWR[r] for r in right[:i]]
        pin(b, EMMC_PWR[b], "power_in" if not stacked else "passive", w + 5.08,
            top - 2.54 - (0 if b == "C2" else (2.54 * 2 if EMMC_PWR[b] == "VCC" else 2.54 * 4)), 180, hide=stacked)
    for i, b in enumerate(EMMC_GND):
        pin(b, "GND", "power_in" if i == 0 else "passive", 0, -top - 5.08, 90, hide=i > 0)
    used = set(EMMC_SIG) | set(EMMC_PWR) | set(EMMC_GND)
    for b in emmc_balls():
        if b not in used:
            pin(b, "NC", "no_connect", w + 5.08, -top + 2.54, 180, hide=True)
    return f'''  (symbol "eMMC_FBGA153" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)
    (property "Reference" "U" (at {-w:.2f} {top + 1.5:.2f} 0) (effects (font (size 1.27 1.27)) (justify left)))
    (property "Value" "eMMC_FBGA153" (at {-w:.2f} {-top - 8:.2f} 0) (effects (font (size 1.27 1.27)) (justify left)))
    (property "Footprint" "Package_BGA:LFBGA-153_11.5x13mm_Layout14x14_P0.5mm" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Datasheet" "https://files.pine64.org/doc/datasheet/pinephone/Kimtigo_fbga153_16_32_64_eMMC_datasheet_v1.3.pdf" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Description" "JEDEC eMMC 5.1, 153-ball FBGA 11.5x13 mm (e.g. Kimtigo KM110SS1064GxA 64 GB)" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (symbol "eMMC_FBGA153_0_1"
      (rectangle (start {-w:.2f} {top:.2f}) (end {w:.2f} {-top:.2f}) (stroke (width 0.254) (type default)) (fill (type background)))
    )
    (symbol "eMMC_FBGA153_1_1"
{"".join(pins)}    )
  )
'''


def nfet_q3a():
    """N-channel power MOSFET in TI's SON 3.3 x 3.3 (Q3A) package, pins as the pico-comp footprint
    VSON-8_3.3x3.3mm_P0.65mm_TI_Q3A: 1-3 source, 4 gate, 5 drain (pins 5-8 + tab are one pad)."""
    pins = []
    for num, name, et, x, y, a, hide in (("5", "D", "passive", 2.54, 5.08, 270, ""),
                                          ("4", "G", "input", -5.08, 0, 0, ""),
                                          ("1", "S", "passive", 2.54, -5.08, 90, ""),
                                          ("2", "S", "passive", 2.54, -5.08, 90, " hide"),
                                          ("3", "S", "passive", 2.54, -5.08, 90, " hide")):
        pins.append(f'      (pin {et} line (at {x:.2f} {y:.2f} {a}) (length 2.54){hide}\n'
                    f'        (name "{name}" (effects (font (size 1.27 1.27))))\n'
                    f'        (number "{num}" (effects (font (size 1.27 1.27)))))\n')
    return f'''  (symbol "NMOS_SON8_Q3A" (pin_names (offset 0.254)) (exclude_from_sim no) (in_bom yes) (on_board yes)
    (property "Reference" "Q" (at 5.08 1.27 0) (effects (font (size 1.27 1.27)) (justify left)))
    (property "Value" "NMOS_SON8_Q3A" (at 5.08 -1.27 0) (effects (font (size 1.27 1.27)) (justify left)))
    (property "Footprint" "pico-comp:VSON-8_3.3x3.3mm_P0.65mm_TI_Q3A" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Datasheet" "https://www.ti.com/lit/ds/symlink/csd17581q3a.pdf" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Description" "N-channel MOSFET, SON 3.3 x 3.3 (pins 1-3 S, 4 G, 5-8 D)" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (symbol "NMOS_SON8_Q3A_0_1"
      (polyline (pts (xy -2.54 0) (xy 0.254 0)) (stroke (width 0) (type default)) (fill (type none)))
      (polyline (pts (xy 0.254 1.905) (xy 0.254 -1.905)) (stroke (width 0.254) (type default)) (fill (type none)))
      (polyline (pts (xy 0.762 2.286) (xy 0.762 -2.286)) (stroke (width 0.254) (type default)) (fill (type none)))
      (polyline (pts (xy 0.762 1.778) (xy 2.54 1.778) (xy 2.54 2.54)) (stroke (width 0) (type default)) (fill (type none)))
      (polyline (pts (xy 0.762 -1.778) (xy 2.54 -1.778) (xy 2.54 -2.54)) (stroke (width 0) (type default)) (fill (type none)))
      (polyline (pts (xy 0.762 0) (xy 2.54 0) (xy 2.54 -1.778)) (stroke (width 0) (type default)) (fill (type none)))
      (polyline (pts (xy 1.016 0) (xy 2.032 0.381) (xy 2.032 -0.381) (xy 1.016 0)) (stroke (width 0) (type default)) (fill (type outline)))
    )
    (symbol "NMOS_SON8_Q3A_1_1"
{"".join(pins)}    )
  )
'''


def write():
    body = rm2() + emmc() + nfet_q3a()
    open(os.path.join(here, "pico-comp.kicad_sym"), "w").write(
        '(kicad_symbol_lib (version 20241209) (generator "pico-comp-projsyms")\n' + body + ")\n")


if __name__ == "__main__":
    write()
