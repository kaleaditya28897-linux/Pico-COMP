#!/usr/bin/env python3
"""Generate the Pico-COMP main board (hardware/kicad/mainboard.kicad_pcb).

4-layer board (F.Cu / GND / 3V3+planes / B.Cu) carrying both RP2350A MCUs, flash, crystals,
BQ25798 charger, 5 V and 3.3 V bucks, USB-C, microSD, HDMI link to the panel, Wi-Fi module,
keyboard header and SWD/boot/reset. Pin assignments follow the KiCad symbol pin names
(symlib.py), the GPIO plan is in docs/hardware-plan.md.

Run: python3 hardware/mainboard/gen_pcb.py   (needs KiCad's pcbnew python module)
Then: python3 hardware/mainboard/route.py hardware/kicad/mainboard.kicad_pcb
"""
import os

import pcbnew
from pcbnew import FromMM, VECTOR2I

import symlib

here = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(here, "..", "kicad", "mainboard.kicad_pcb")
FP = "/usr/share/kicad/footprints"
BW, BH = 152.0, 68.0

board = pcbnew.NewBoard(OUT)
board.SetCopperLayerCount(4)
board.SetLayerName(pcbnew.In1_Cu, "GND")
board.SetLayerName(pcbnew.In2_Cu, "PWR")
_nets = {}
refs = {}


def mm(x, y):
    return VECTOR2I(FromMM(x), FromMM(y))


def N(name):
    if not name:
        return None
    if name not in _nets:
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        _nets[name] = n
    return _nets[name]


def add(ref, lib, name, x, y, rot=0, value="", back=False):
    fp = pcbnew.FootprintLoad(f"{FP}/{lib}.pretty", name)
    fp.SetReference(ref)
    fp.SetValue(value or name)
    board.Add(fp)
    if rot:
        fp.SetOrientationDegrees(rot)
    fp.SetPosition(mm(x, y))
    if back:
        fp.Flip(mm(x, y), True)
    fp.Reference().SetVisible(False)
    assert ref not in refs, f"duplicate reference {ref}"
    refs[ref] = fp
    return fp


def conn(ref, nets):
    """nets: {pad_number: net_name}; a pad key may be shared by several pads."""
    fp = refs[ref]
    for p in fp.Pads():
        n = nets.get(p.GetNumber())
        if n:
            p.SetNet(N(n))


def ic(ref, lib, name, sym, x, y, mapping, rot=0, value=""):
    """mapping: {symbol pin name: net}. Every named pin must exist in the symbol."""
    pins, _ = symlib.load(*sym)
    fp = add(ref, lib, name, x, y, rot, value or sym[1])
    nets = {}
    for pname, net in mapping.items():
        for num in pins[pname]:
            nets[num] = net
    conn(ref, nets)
    return fp


def C(ref, val, a, b, x, y, size="0402", rot=0):
    add(ref, "Capacitor_SMD", f"C_{size}_{ {'0402': '1005', '0603': '1608', '0805': '2012'}[size]}Metric", x, y, rot, val)
    conn(ref, {"1": a, "2": b})


def R(ref, val, a, b, x, y, rot=0):
    add(ref, "Resistor_SMD", "R_0402_1005Metric", x, y, rot, val)
    conn(ref, {"1": a, "2": b})


def place_edge(ref, edge, pos):
    """Slide a connector so the bounding box touches the board edge; pos is along the edge."""
    fp = refs[ref]
    b = fp.GetBoundingBox(False)
    cx, cy = (b.GetLeft() + b.GetRight()) / 2, (b.GetTop() + b.GetBottom()) / 2
    dx = dy = 0
    if edge == "right":
        dx = FromMM(BW) - b.GetRight() + FromMM(0.3)
        dy = FromMM(pos) - cy
    elif edge == "left":
        dx = -b.GetLeft() - FromMM(0.3)
        dy = FromMM(pos) - cy
    elif edge == "top":
        dy = -b.GetTop() - FromMM(0.3)
        dx = FromMM(pos) - cx
    elif edge == "bottom":
        dy = FromMM(BH) - b.GetBottom() + FromMM(0.3)
        dx = FromMM(pos) - cx
    fp.Move(VECTOR2I(int(dx), int(dy)))


GPIO = lambda n: f"GPIO{n}"

# --------------------------------------------------------------------------------------
# Netlist plan
# --------------------------------------------------------------------------------------
# NET MCU (U2): keyboard 0-19, I2C 20/21, charger INT 22, Wi-Fi 23-26, STAT 27, UART 28/29
NET_GPIO = {}
for r in range(6):
    NET_GPIO[r] = f"ROW{r}"
for c in range(14):
    NET_GPIO[6 + c] = f"COL{c}"
NET_GPIO.update({20: "I2C_SDA", 21: "I2C_SCL", 22: "CHG_INT", 23: "WL_ON", 24: "WL_DATA",
                 25: "WL_CS", 26: "WL_CLK", 27: "CHG_STAT", 28: "NET_TX", 29: "NET_RX"})
# UI MCU (U1): printer UART 0/1(+2/3 handshake), expansion 4-11, HSTX 12-19, SD SPI 20-23,
# card detect 24, LED 25, buzzer 26, spare 27, UART to NET 28/29
UI_GPIO = {0: "PRN_TX", 1: "PRN_RX", 2: "PRN_RTS", 3: "PRN_CTS"}
for g in range(4, 12):
    UI_GPIO[g] = f"EXP{g}"
UI_GPIO.update({12: "TMDS_D0P", 13: "TMDS_D0N", 14: "TMDS_CKP", 15: "TMDS_CKN",
                16: "TMDS_D2P", 17: "TMDS_D2N", 18: "TMDS_D1P", 19: "TMDS_D1N",
                20: "SD_MISO", 21: "SD_CS", 22: "SD_SCK", 23: "SD_MOSI", 24: "SD_DET",
                25: "UI_LED", 26: "BUZZ", 27: "UI_SPARE", 28: "UI_TX", 29: "UI_RX"})
NET_ALIAS = {"NET_TX": "UI_RX", "NET_RX": "UI_TX"}     # TX of one MCU is RX of the other
NET_GPIO = {g: NET_ALIAS.get(n, n) for g, n in NET_GPIO.items()}
UI_GPIO = {g: NET_ALIAS.get(n, n) for g, n in UI_GPIO.items()}


def rp2350(tag, ref, x, y, gpio, usb):
    m = {"IOVDD": "V3V3", "USB_OTP_VDD": "V3V3", "QSPI_IOVDD": "V3V3", "VREG_AVDD": "V3V3",
         "VREG_VIN": "V3V3", "ADC_AVDD": "V3V3", "DVDD": f"{tag}_1V1", "VREG_FB": f"{tag}_1V1",
         "VREG_LX": f"{tag}_LX", "VREG_PGND": "GND", "GND": "GND",
         "XIN": f"{tag}_XIN", "XOUT": f"{tag}_XOUT", "RUN": f"{tag}_RUN",
         "SWCLK": f"{tag}_SWCLK", "SWDIO": f"{tag}_SWDIO",
         "QSPI_SD0": f"{tag}_QSD0", "QSPI_SD1": f"{tag}_QSD1", "QSPI_SD2": f"{tag}_QSD2",
         "QSPI_SD3": f"{tag}_QSD3", "QSPI_SCLK": f"{tag}_QSCK", "~{QSPI_SS}": f"{tag}_QSS"}
    if usb:
        m.update({"USB_DM": "UI_DM", "USB_DP": "UI_DP"})
    for g in range(30):
        pn = [k for k in symlib.load("MCU_RaspberryPi", "RP2350A")[0] if k.startswith(f"GPIO{g}") and not k[len(f"GPIO{g}"):][:1].isdigit()][0]
        if g in gpio:
            m[pn] = gpio[g]
    ic(ref, "Package_DFN_QFN", "QFN-60-1EP_7x7mm_P0.4mm_EP3.4x3.4mm", ("MCU_RaspberryPi", "RP2350A"),
       x, y, m, value=f"RP2350A ({tag})")


def support(tag, u, x, y, bootref, runref, swdref, usb=False, swd_dy=8):
    """Flash, crystal, regulator inductor, decoupling and buttons for one RP2350."""
    # decoupling: one 100 nF per supply pin group, plus bulk
    for i in range(6):
        C(f"C{u}{i + 1}", "100nF", "V3V3", "GND", x - 6 + i * 2.4, y - 6.2)
    C(f"C{u}7", "100nF", "V3V3", "GND", x - 6, y + 6.2)
    C(f"C{u}8", "100nF", f"{tag}_1V1", "GND", x - 3.6, y + 6.2)
    C(f"C{u}9", "100nF", f"{tag}_1V1", "GND", x - 1.2, y + 6.2)
    C(f"C{u}A", "4.7uF", f"{tag}_1V1", "GND", x + 1.6, y + 6.2, "0603")
    C(f"C{u}B", "4.7uF", "V3V3", "GND", x + 4.8, y + 6.2, "0603")
    add(f"L{u}", "Inductor_SMD", "L_1210_3225Metric", x + 9.6, y + 6.5, 0, "3.3uH")
    conn(f"L{u}", {"1": f"{tag}_LX", "2": f"{tag}_1V1"})
    # QSPI flash
    ic(f"F{u}", "Package_SO", "SOIC-8_5.3x5.3mm_P1.27mm", ("Memory_Flash", "W25Q128JVS"), x + 12, y - 2, {
        "~{CS}": f"{tag}_QSS", "DO/IO_{1}": f"{tag}_QSD1", "~{WP}/IO_{2}": f"{tag}_QSD2",
        "GND": "GND", "DI/IO_{0}": f"{tag}_QSD0", "CLK": f"{tag}_QSCK",
        "~{HOLD}/~{RESET}/IO_{3}": f"{tag}_QSD3", "VCC": "V3V3"})
    C(f"C{u}C", "100nF", "V3V3", "GND", x + 12, y - 6.5)
    # crystal 12 MHz with 1k series on XOUT
    add(f"Y{u}", "Crystal", "Crystal_SMD_3225-4Pin_3.2x2.5mm", x - 12, y, 90, "12MHz")
    conn(f"Y{u}", {"1": f"{tag}_XIN", "3": f"{tag}_XB", "2": "GND", "4": "GND"})
    R(f"R{u}1", "1k", f"{tag}_XB", f"{tag}_XOUT", x - 12, y + 4)
    C(f"C{u}D", "15pF", f"{tag}_XIN", "GND", x - 14.5, y - 3.5)
    C(f"C{u}E", "15pF", f"{tag}_XB", "GND", x - 14.5, y + 3.5)
    # BOOTSEL (QSPI_SS through 1k to a button), RUN pull-up + reset button
    R(f"R{u}2", "1k", f"{tag}_QSS", f"{tag}_BOOT", x + 12, y + 3.0)
    add(bootref, "Button_Switch_SMD", "SW_SPST_B3U-1000P", x + 16, y + 9.5, 0, "BOOTSEL")
    conn(bootref, {"1": f"{tag}_BOOT", "2": "GND"})
    R(f"R{u}3", "10k", "V3V3", f"{tag}_RUN", x + 15, y + 3.0)
    add(runref, "Button_Switch_SMD", "SW_SPST_B3U-1000P", x + 16, y + 14.5, 0, "RESET")
    conn(runref, {"1": f"{tag}_RUN", "2": "GND"})
    # SWD
    add(swdref, "Connector_PinHeader_1.27mm", "PinHeader_1x03_P1.27mm_Vertical_SMD_Pin1Left", x - 19, y + swd_dy, 0, "SWD")
    conn(swdref, {"1": f"{tag}_SWCLK", "2": "GND", "3": f"{tag}_SWDIO"})


# --------------------------------------------------------------------------------------
# MCUs
# --------------------------------------------------------------------------------------
UI_X, UI_Y = 102.0, 42.0
NET_X, NET_Y = 52.0, 44.0
rp2350("UI", "U1", UI_X, UI_Y, UI_GPIO, usb=True)
support("UI", 1, UI_X, UI_Y, "SW1", "SW2", "J3", usb=True, swd_dy=-9)
rp2350("NET", "U2", NET_X, NET_Y, NET_GPIO, usb=False)
support("NET", 2, NET_X, NET_Y, "SW3", "SW4", "J4", swd_dy=4)

# --------------------------------------------------------------------------------------
# Power: USB-C -> BQ25798 -> VSYS -> 5 V buck -> 3.3 V buck
# --------------------------------------------------------------------------------------
add("J1", "Connector_USB", "USB_C_Receptacle_HRO_TYPE-C-31-M-12", 0, 0, 90, "USB-C")
conn("J1", {"A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND",
            "A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS",
            "A5": "CC1", "B5": "CC2", "A6": "USB_P", "B6": "USB_P", "A7": "USB_N", "B7": "USB_N"})
place_edge("J1", "right", 16)
R("RCC1", "5.1k", "CC1", "GND", 138, 20)
R("RCC2", "5.1k", "CC2", "GND", 138, 22)
ic("U3", "Package_TO_SOT_SMD", "SOT-23-6", ("Power_Protection", "USBLC6-2SC6"), 140, 8, {
    "I/O1": "USB_P", "GND": "GND", "I/O2": "USB_N", "VBUS": "VBUS"}, value="USBLC6-2SC6")
R("RUD1", "27", "USB_P", "UI_DP", 132, 14)
R("RUD2", "27", "USB_N", "UI_DM", 132, 16)

# BQ25798 charger (2S pack on BAT)
ic("U5", "Package_DFN_QFN", "Texas_RQM0029A_VQFN-29_4x4mm_P0.4mm", ("Battery_Management", "BQ25798"),
   28, 26, {"STAT": "CHG_STAT", "VBUS": "VBUS", "BTST1": "BTST1", "REGN": "REGN", "D+": "USB_P",
            "D-": "USB_N", "VAC2": "VBUS", "VAC1": "VBUS", "SCL": "I2C_SCL", "SDA": "I2C_SDA",
            "TS": "TS", "ILIM_HIZ": "ILIM", "BATP": "VBAT", "BTST2": "BTST2", "~{INT}": "CHG_INT",
            "BAT": "VBAT", "SYS": "VSYS", "SW2": "SW2", "GND": "GND", "SW1": "SW1", "PMID": "PMID",
            "~{CE}": "GND"})
add("L5", "Inductor_SMD", "L_Bourns_SRP7028A_7.3x6.6mm", 28, 38, 0, "2.2uH 7A")
conn("L5", {"1": "SW1", "2": "SW2"})
C("C50", "10uF", "VBUS", "GND", 21, 18, "0805")
C("C51", "10uF", "VBUS", "GND", 21, 21, "0805")
C("C52", "10uF", "PMID", "GND", 21, 24, "0805")
C("C53", "10uF", "PMID", "GND", 21, 27, "0805")
C("C54", "47nF", "BTST1", "SW1", 35, 19)
C("C55", "47nF", "BTST2", "SW2", 35, 21)
C("C56", "4.7uF", "REGN", "GND", 35, 24, "0603")
C("C57", "10uF", "VSYS", "GND", 36, 28, "0805")
C("C58", "10uF", "VSYS", "GND", 36, 31, "0805")
C("C59", "10uF", "VBAT", "GND", 21, 31, "0805")
C("C5A", "10uF", "VBAT", "GND", 21, 34, "0805")
R("R50", "5.23k", "REGN", "TS", 40, 19)
R("R51", "30.1k", "TS", "GND", 40, 21)
R("R52", "47k", "REGN", "ILIM", 40, 23)
R("R53", "47k", "ILIM", "GND", 40, 25)
R("R54", "4.7k", "V3V3", "I2C_SDA", 44, 19)
R("R55", "4.7k", "V3V3", "I2C_SCL", 44, 21)
R("R56", "10k", "V3V3", "CHG_INT", 44, 23)
R("R57", "10k", "V3V3", "CHG_STAT", 44, 25)
add("J2", "Connector_AMASS", "AMASS_XT30PW-M_1x02_P2.50mm_Horizontal", 0, 0, 90, "BATTERY 2S")
conn("J2", {"1": "VBAT", "2": "GND"})
place_edge("J2", "left", 26)
add("J5", "Connector_JST", "JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical", 10, 46, 0, "NTC")
conn("J5", {"1": "TS", "2": "GND"})

# 5 V buck (TPS62933, VSYS -> 5 V / 3 A)
ic("U6", "Package_TO_SOT_SMD", "SOT-583-8", ("Regulator_Switching", "TPS62933"), 62, 12,
   {"EN": "VSYS", "VIN": "VSYS", "GND": "GND", "SW": "SW5", "BST": "BST5", "SS": "SS5", "FB": "FB5"})
add("L6", "Inductor_SMD", "L_Bourns_SRP7028A_7.3x6.6mm", 62, 22, 0, "4.7uH 5A")
conn("L6", {"1": "SW5", "2": "V5"})
C("C60", "10uF", "VSYS", "GND", 55, 9, "0805")
C("C61", "10uF", "VSYS", "GND", 55, 12, "0805")
C("C62", "100nF", "BST5", "SW5", 69, 9)
C("C63", "10nF", "SS5", "GND", 69, 11)
R("R60", "52.3k", "V5", "FB5", 69, 13)
R("R61", "10k", "FB5", "GND", 69, 15)
C("C64", "22uF", "V5", "GND", 70, 22, "0805")
C("C65", "22uF", "V5", "GND", 70, 25, "0805")
C("C66", "22uF", "V5", "GND", 70, 28, "0805")

# 3.3 V buck (AP63203, 5 V -> 3.3 V / 2 A)
ic("U7", "Package_TO_SOT_SMD", "TSOT-23-6", ("Regulator_Switching", "AP63203WU"), 90, 10,
   {"FB": "V3V3", "EN": "V5", "IN": "V5", "GND": "GND", "SW": "SW3", "BST": "BST3"})
add("L7", "Inductor_SMD", "L_Bourns_SRN6045TA", 90, 20, 0, "4.7uH 3A")
conn("L7", {"1": "SW3", "2": "V3V3"})
C("C70", "10uF", "V5", "GND", 84, 14, "0805")
C("C71", "100nF", "BST3", "SW3", 96, 9)
C("C72", "22uF", "V3V3", "GND", 98, 20, "0805")
C("C73", "22uF", "V3V3", "GND", 98, 23, "0805")
C("C74", "22uF", "V3V3", "GND", 98, 26, "0805")
R("R70", "1k", "V3V3", "PWR_LED", 98, 4)
add("D1", "LED_SMD", "LED_0603_1608Metric", 101, 4, 0, "PWR")
conn("D1", {"1": "GND", "2": "PWR_LED"})

# --------------------------------------------------------------------------------------
# Peripherals
# --------------------------------------------------------------------------------------
# HDMI (internal link to the panel; mouth faces the hinge/top edge). Standard HDMI-A pin order.
add("J6", "Connector_Video", "HDMI_A_Molex_208658-1001_Horizontal", 0, 0, 90, "HDMI to panel")
conn("J6", {"1": "HD_D2P", "2": "GND", "3": "HD_D2N", "4": "HD_D1P", "5": "GND", "6": "HD_D1N",
            "7": "HD_D0P", "8": "GND", "9": "HD_D0N", "10": "HD_CKP", "11": "GND", "12": "HD_CKN",
            "17": "GND", "SH": "GND"})
place_edge("J6", "top", 116)
for i, (a, b) in enumerate([("TMDS_D0P", "HD_D0P"), ("TMDS_D0N", "HD_D0N"), ("TMDS_CKP", "HD_CKP"),
                            ("TMDS_CKN", "HD_CKN"), ("TMDS_D2P", "HD_D2P"), ("TMDS_D2N", "HD_D2N"),
                            ("TMDS_D1P", "HD_D1P"), ("TMDS_D1N", "HD_D1N")]):
    R(f"R8{i}", "270", a, b, 102 + i * 2.2, 28)
# 5 V power out to the panel (separate from HDMI)
add("J7", "Connector_JST", "JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical", 72, 4, 0, "PANEL 5V")
conn("J7", {"1": "V5", "2": "GND"})
add("J8", "Connector_JST", "JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical", 81, 4, 0, "BACKLIGHT/AUX 5V")
conn("J8", {"1": "V5", "2": "GND"})

# microSD (SPI mode)
add("J9", "Connector_Card", "microSD_HC_Hirose_DM3AT-SF-PEJM5", 0, 0, 90, "microSD")
conn("J9", {"1": "SD_NC2", "2": "SD_CS", "3": "SD_MOSI", "4": "V3V3", "5": "SD_SCK", "6": "GND",
            "7": "SD_MISO", "8": "SD_NC1", "9": "SD_DET", "10": "GND", "SH": "GND"})
place_edge("J9", "right", 52)
R("R90", "10k", "V3V3", "SD_NC1", 124, 41)
R("R91", "10k", "V3V3", "SD_NC2", 124, 43)
R("R92", "10k", "V3V3", "SD_CS", 124, 45)
C("C90", "100nF", "V3V3", "GND", 124, 47)

# Wi-Fi module (CYW43439 gSPI) + U.FL. PLACEHOLDER footprint: replace with the vendor
# footprint of the chosen module (Murata 1DX / RPi RM2) before ordering.
wifi = pcbnew.FOOTPRINT(board)
wifi.SetReference("U8")
wifi.SetValue("CYW43439 module (PLACEHOLDER)")
for i, nm in enumerate(["GND", "V3V3", "V3V3", "WL_ON", "WL_DATA", "WL_CLK", "WL_CS", "GND"]):
    p = pcbnew.PAD(wifi)
    p.SetNumber(str(i + 1))
    p.SetShape(pcbnew.PAD_SHAPE_RECT)
    p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    p.SetSize(mm(0.8, 2.0))
    p.SetLayerSet(p.SMDMask())
    p.SetPosition(mm(-4.0 + i * 1.143, 5.0))
    p.SetNet(N(nm))
    wifi.Add(p)
rf = pcbnew.PAD(wifi)
rf.SetNumber("9")
rf.SetShape(pcbnew.PAD_SHAPE_RECT)
rf.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
rf.SetSize(mm(1.0, 1.0))
rf.SetLayerSet(rf.SMDMask())
rf.SetPosition(mm(-6.0, 0))
rf.SetNet(N("WL_RF"))
wifi.Add(rf)
for i, (x, y) in enumerate([(-6, -6), (6, -6), (6, 6), (-6, 6)]):
    pass
board.Add(wifi)
refs["U8"] = wifi
wifi.SetPosition(mm(90, 52))
add("J10", "Connector_Coaxial", "U.FL_Hirose_U.FL-R-SMT-1_Vertical", 79, 60, 0, "ANT U.FL")
conn("J10", {"1": "WL_RF", "2": "GND"})
C("C80", "100nF", "V3V3", "GND", 98, 47)
C("C81", "10uF", "V3V3", "GND", 98, 50, "0805")

# Keyboard matrix header (matches keyboard.kicad_pcb J1: ROW0-5 then COL0-13)
add("J11", "Connector_PinHeader_2.54mm", "PinHeader_1x20_P2.54mm_Horizontal", 12, 65, 90, "KB_MATRIX")
conn("J11", {str(i + 1): n for i, n in enumerate([f"ROW{r}" for r in range(6)] + [f"COL{c}" for c in range(14)])})

# Printer UART / expansion / status
add("J12", "Connector_JST", "JST_SH_SM06B-SRSS-TB_1x06-1MP_P1.00mm_Horizontal", 140, 64, 0, "PRINTER")
conn("J12", {"1": "V5", "2": "PRN_TX", "3": "PRN_RX", "4": "PRN_RTS", "5": "PRN_CTS", "6": "GND"})
add("J13", "Connector_PinHeader_1.27mm", "PinHeader_1x10_P1.27mm_Vertical", 120, 62, 90, "EXPANSION")
conn("J13", {"1": "V3V3", "2": "GND", **{str(3 + i): f"EXP{4 + i}" for i in range(8)}})
R("R95", "1k", "UI_LED", "UI_LEDK", 106, 56)
add("D2", "LED_SMD", "LED_0603_1608Metric", 109, 56, 0, "UI")
conn("D2", {"1": "GND", "2": "UI_LEDK"})

# Mounting holes (M2.5)
for i, (x, y) in enumerate([(4, 4), (BW - 4, 4), (4, BH - 4), (BW - 4, BH - 4)]):
    add(f"H{i + 1}", "MountingHole", "MountingHole_2.7mm_M2.5", x, y, 0, "M2.5")

# --------------------------------------------------------------------------------------
# Outline, zones, rules
# --------------------------------------------------------------------------------------
pts = [(0, 0), (BW, 0), (BW, BH), (0, BH)]
for a, b in zip(pts, pts[1:] + pts[:1]):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetStart(mm(*a))
    s.SetEnd(mm(*b))
    s.SetWidth(FromMM(0.1))
    board.Add(s)


def zone(layer, net):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(N(net))
    z.SetIsRuleArea(False)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in [(0.5, 0.5), (BW - 0.5, 0.5), (BW - 0.5, BH - 0.5), (0.5, BH - 0.5)]:
        ol.Append(FromMM(x), FromMM(y))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetMinThickness(FromMM(0.2))
    board.Add(z)


zone(pcbnew.In1_Cu, "GND")
zone(pcbnew.In2_Cu, "V3V3")
zone(pcbnew.B_Cu, "GND")

ds = board.GetDesignSettings()
ds.m_TrackMinWidth = FromMM(0.127)
ds.m_ViasMinSize = FromMM(0.45)
ds.m_MinThroughDrill = FromMM(0.2)
ds.m_MinClearance = FromMM(0.127)
ds.m_CopperEdgeClearance = FromMM(0.3)
nc = ds.m_NetSettings.GetDefaultNetclass()
nc.SetClearance(FromMM(0.15))
nc.SetTrackWidth(FromMM(0.15))
nc.SetViaDiameter(FromMM(0.5))
nc.SetViaDrill(FromMM(0.25))
pw = pcbnew.NETCLASS("Power")
pw.SetClearance(FromMM(0.2))
pw.SetTrackWidth(FromMM(0.3))
pw.SetViaDiameter(FromMM(0.6))
pw.SetViaDrill(FromMM(0.3))
ds.m_NetSettings.SetNetclass("Power", pw)
for pat in ("VBUS", "VBAT", "VSYS", "V5", "SW1", "SW2", "SW5", "SW3", "PMID"):
    ds.m_NetSettings.SetNetclassPatternAssignment(pat, "Power")

board.Save(OUT)
print(f"{len(refs)} footprints, {len(_nets)} nets, {BW:.0f} x {BH:.0f} mm -> {OUT}")
