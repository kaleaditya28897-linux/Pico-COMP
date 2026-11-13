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


def write():
    body = rm2()
    open(os.path.join(here, "pico-comp.kicad_sym"), "w").write(
        '(kicad_symbol_lib (version 20241209) (generator "pico-comp-projsyms")\n' + body + ")\n")


if __name__ == "__main__":
    write()
