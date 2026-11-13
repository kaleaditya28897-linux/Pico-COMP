#!/usr/bin/env python3
"""Generate the Pico-COMP main board (hardware/kicad/mainboard.kicad_pcb).

6-layer board (F.Cu sig / In1 GND plane / In2 sig / In3 sig / In4 3V3 plane / B.Cu sig + GND pour) carrying both RP2350A MCUs, flash, crystals,
BQ25798 charger, 5 V and 3.3 V bucks, USB-C, microSD, HDMI link to the panel, Wi-Fi module,
keyboard header and SWD/boot/reset. Pin assignments follow the KiCad symbol pin names
(symlib.py), the GPIO plan is in docs/hardware-plan.md.

Run: python3 hardware/mainboard/gen_pcb.py   (needs KiCad's pcbnew python module)
Then: python3 hardware/mainboard/route.py hardware/kicad/mainboard.kicad_pcb
"""
import json
import os

import pcbnew
from pcbnew import FromMM, VECTOR2I

import symlib
import rp2350_vreg  # noqa: E402  (Raspberry Pi minimal-design regulator layout, MIT)

import sys  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kicad"))
import fplib  # noqa: E402

here = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("GEN_PCB_OUT") or os.path.join(here, "..", "kicad", "mainboard.kicad_pcb")   # override: scratch build
FP = "/usr/share/kicad/footprints"
KICAD = os.path.join(here, "..", "kicad")
LOCAL_LIB = "pico-comp"                      # hardware/kicad/pico-comp.pretty (+ pico-comp.3dshapes)
BW, BH = 152.0, 84.0
# Parts are placed in a 68 mm-tall design frame; their y is stretched to the real board height so the
# autorouter has room (68 mm was too dense to route with intact planes). Edge-referenced parts
# (RM2, keyboard header, holes, fiducials) pass fixed=True and are placed in real board coordinates.
SY = BH / 68.0

import sys as _sys
if os.path.exists(OUT) and "--force" not in _sys.argv:
    _old = pcbnew.LoadBoard(OUT)
    _routed = [t for t in _old.GetTracks() if not t.IsLocked()]      # locked copper = generator recipes / fan-out
    if _routed:
        _sys.exit(f"{OUT} has {len(_routed)} routed tracks. Refusing to overwrite it; "
                  "make netlist changes in KiCad, or pass --force to regenerate from scratch.")
board = pcbnew.NewBoard(OUT)
board.SetCopperLayerCount(6)
board.SetLayerName(pcbnew.In1_Cu, "GND")
board.SetLayerName(pcbnew.In4_Cu, "PWR")
# 6 layers: F.Cu sig / In1 GND plane / In2 sig / In3 sig / In4 3V3 plane / B.Cu sig + GND pour.
# Plane layers are LT_POWER so the autorouter never routes on (and splits) them.
board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
board.SetLayerType(pcbnew.In4_Cu, pcbnew.LT_POWER)
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


def add(ref, lib, name, x, y, rot=0, value="", back=False, mpn="", spec="", fixed=False):
    if not fixed:
        y = y * SY
    if fplib.needs_copy(name):
        lib = fplib.copy(lib, name)
    path = os.path.join(KICAD, f"{lib}.pretty") if lib == LOCAL_LIB else f"{FP}/{lib}.pretty"
    fp = pcbnew.FootprintLoad(path, name)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetReference(ref)
    fp.SetValue(value or name)
    for k, v in (("MPN", mpn), ("Spec", spec)):
        if v:
            fp.SetField(k, v)
            fp.GetField(k).SetVisible(False)
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


SYMBOL = {}                                   # ref -> (symbol lib, symbol name), used by gen_sch.py


def ic(ref, lib, name, sym, x, y, mapping, rot=0, value="", mpn=""):
    """mapping: {symbol pin name: net}. Every named pin must exist in the symbol."""
    pins, _ = symlib.load(*sym)
    fp = add(ref, lib, name, x, y, rot, value or sym[1], mpn=mpn or value or sym[1])
    SYMBOL[ref] = sym
    nets = {}
    for pname, net in mapping.items():
        for num in pins[pname]:
            nets[num] = net
    conn(ref, nets)
    return fp


HV_NETS = {"VBUS", "PMID", "VSYS", "VBAT", "VBAT_PACK", "SW1", "SW2", "SW5", "BTST1", "BTST2", "TS"}


def C(ref, val, a, b, x, y, size="0402", rot=0):
    volts = "25V" if {a, b} & HV_NETS else ("10V" if {a, b} & {"V5", "REGN", "BST5", "SS5"} else "6.3V")
    if val.endswith("pF") or val.endswith("nF"):
        diel = "C0G" if val.endswith("pF") else "X7R"
        volts = "50V" if {a, b} & HV_NETS or ref == "C511" else volts if volts != "6.3V" else "16V"
    else:
        diel = "X5R"
    add(ref, "Capacitor_SMD", f"C_{size}_{ {'0402': '1005', '0603': '1608', '0805': '2012'}[size]}Metric", x, y, rot, val,
        spec=f"{val} {volts} {diel} {size}")
    conn(ref, {"1": a, "2": b})


def R(ref, val, a, b, x, y, rot=0):
    add(ref, "Resistor_SMD", "R_0402_1005Metric", x, y, rot, val, spec=f"{val} 1% 0402")
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


def zone_local(net, name, pts, priority, clearance=0.15, layer=pcbnew.F_Cu):
    """Solid-connected copper pour with an explicit outline (real board mm), e.g. a switch node."""
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(N(net))
    z.SetZoneName(name)
    z.SetAssignedPriority(priority)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in pts:
        ol.Append(FromMM(x), FromMM(y))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetLocalClearance(FromMM(clearance))
    z.SetMinThickness(FromMM(0.15))
    board.Add(z)
    return z


def track(net, a, b, w, layer=pcbnew.F_Cu):
    """Locked copper drawn by the generator (layout recipes): kept by fanout/route.py and the routers."""
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(mm(*a))
    t.SetEnd(mm(*b))
    t.SetWidth(FromMM(w))
    t.SetLayer(layer)
    t.SetNet(N(net))
    t.SetLocked(True)
    board.Add(t)


def via(net, at, d, drill):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(mm(*at))
    v.SetWidth(FromMM(d))
    v.SetDrill(FromMM(drill))
    v.SetNet(N(net))
    v.SetLocked(True)
    board.Add(v)


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
# UI MCU (U1): expansion 0-3 + 8-11 (I2C0 on 8/9, SPI1 on 8-11), printer UART1 4-7 (TX, RX, CTS, RTS),
# HSTX 12-19, SD SPI0 20-23,
# card detect 24, LED 25, buzzer 26, panel power 27, UART to NET 28/29
# UART0 is the MCU link on 28/29, so the printer uses UART1 (GPIO4 TX, 5 RX, 6 CTS, 7 RTS)
UI_GPIO = {4: "PRN_TX", 5: "PRN_RX", 6: "PRN_CTS", 7: "PRN_RTS"}
EXP_GPIO = [0, 1, 2, 3, 8, 9]
for g in EXP_GPIO:
    UI_GPIO[g] = f"EXP{g}"
# UI GPIO10/11 drive the NET MCU's SWD port: the UI firmware reflashes the NET MCU (one update file)
UI_GPIO.update({10: "NET_SWCLK", 11: "NET_SWDIO"})
# RP2350B extra GPIO: 64 GB eMMC, 4-bit SD/MMC bus via PIO (DAT0-3 consecutive for the PIO program)
# power button sense (through D50, shared with the charger's QON): sleep/wake and soft power-off
UI_GPIO.update({37: "UI_PWR_KEY"})
UI_GPIO.update({30: "EMMC_CLK", 31: "EMMC_CMD", 32: "EMMC_DAT0", 33: "EMMC_DAT1", 34: "EMMC_DAT2",
                35: "EMMC_DAT3", 36: "EMMC_RST"})
UI_GPIO.update({12: "TMDS_D0P", 13: "TMDS_D0N", 14: "TMDS_CKP", 15: "TMDS_CKN",
                16: "TMDS_D2P", 17: "TMDS_D2N", 18: "TMDS_D1P", 19: "TMDS_D1N",
                20: "SD_MISO", 21: "SD_CS", 22: "SD_SCK", 23: "SD_MOSI", 24: "SD_DET",
                25: "UI_LED", 26: "BUZZ", 27: "PANEL_EN", 28: "UI_TX", 29: "UI_RX"})
NET_ALIAS = {"NET_TX": "UI_RX", "NET_RX": "UI_TX"}     # TX of one MCU is RX of the other
NET_GPIO = {g: NET_ALIAS.get(n, n) for g, n in NET_GPIO.items()}
UI_GPIO = {g: NET_ALIAS.get(n, n) for g, n in UI_GPIO.items()}


def rp2350(tag, ref, x, y, gpio, usb, part="RP2350A"):
    """part: RP2350A (QFN-60, GPIO0-29) or RP2350B (QFN-80, GPIO0-47)."""
    m = {"IOVDD": "V3V3", "USB_OTP_VDD": "V3V3", "QSPI_IOVDD": "V3V3", "VREG_AVDD": f"{tag}_AVDD",   # RC-filtered (vreg)
         "VREG_VIN": "V3V3", "ADC_AVDD": "V3V3", "DVDD": f"{tag}_1V1", "VREG_FB": f"{tag}_1V1",
         "VREG_LX": f"{tag}_LX", "VREG_PGND": "GND", "GND": "GND",
         "XIN": f"{tag}_XIN", "XOUT": f"{tag}_XOUT", "RUN": f"{tag}_RUN",
         "SWCLK": f"{tag}_SWCLK", "SWDIO": f"{tag}_SWDIO",
         "QSPI_SD0": f"{tag}_QSD0", "QSPI_SD1": f"{tag}_QSD1", "QSPI_SD2": f"{tag}_QSD2",
         "QSPI_SD3": f"{tag}_QSD3", "QSPI_SCLK": f"{tag}_QSCK", "~{QSPI_SS}": f"{tag}_QSS"}
    if usb:   # _P/_N suffixes: KiCad's diff-pair router pairs them
        m.update({"USB_DM": f"{usb}_N", "USB_DP": f"{usb}_P"})
    pins = symlib.load("MCU_RaspberryPi", part)[0]
    for g in range(48 if part == "RP2350B" else 30):
        pn = [k for k in pins if k.startswith(f"GPIO{g}") and not k[len(f"GPIO{g}"):][:1].isdigit()][0]
        if g in gpio:
            m[pn] = gpio[g]
    fpn = "QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm" if part == "RP2350B" else "QFN-60-1EP_7x7mm_P0.4mm_EP3.4x3.4mm"
    ic(ref, "Package_DFN_QFN", fpn, ("MCU_RaspberryPi", part), x, y, m, value=f"{part} ({tag})", mpn=part)


def vreg(tag, u, ref, part):
    """RP2350 core regulator, copied from Raspberry Pi's minimal design (rp2350_vreg.py, MIT, see there):
    L (AOTA-B201610S3R3-101-T, polarity dot on pad 1 = 1V1), 4.7 uF in/out, 33R + 4.7 uF VREG_AVDD filter,
    their local pours, tracks and vias, all in the RP2350's frame. VREG_VIN is fed from the In4 3.3 V plane
    through a via under the chip (the reference board has a 3.3 V top pour instead)."""
    lay = rp2350_vreg.LAYOUT[part]
    o = refs[ref].GetPosition()
    ox, oy = o.x / 1e6, o.y / 1e6
    net = {"LX": f"{tag}_LX", "1V1": f"{tag}_1V1", "AVDD": f"{tag}_AVDD", "3V3": "V3V3", "GND": "GND"}
    cap = dict(lib="Capacitor_SMD", name="C_0402_1005Metric", value="4.7uF", mpn="GRM155R60J475ME47D",
               spec="4.7uF 6.3V X5R 0402")
    spec = {"L": dict(ref=f"L{u}", lib=LOCAL_LIB, name=rp2350_vreg.FOOTPRINTS["L1"], value="3.3uH",
                      mpn="AOTA-B201610S3R3-101-T", spec=""),
            "CIN": dict(cap, ref=f"C{u}21", lib=LOCAL_LIB, name=rp2350_vreg.FOOTPRINTS["C6"]),
            "COUT": dict(cap, ref=f"C{u}20", lib=LOCAL_LIB, name=rp2350_vreg.FOOTPRINTS["C6"]),
            "CAVDD": dict(cap, ref=f"C{u}25"),
            "RAVDD": dict(ref=f"R{u}4", lib="Resistor_SMD", name="R_0402_1005Metric", value="33",
                          mpn="", spec="33 1% 0402")}
    for role, pl in lay["parts"].items():
        sp = spec[role]
        add(sp["ref"], sp["lib"], sp["name"], ox + pl["at"][0], oy + pl["at"][1], pl["rot"], sp["value"],
            mpn=sp["mpn"], spec=sp["spec"], fixed=True)
        conn(sp["ref"], {k: net[v] for k, v in pl["pads"].items()})
    for z in lay["zones"]:
        zone_local(net[z["net"]], f"VREG_{tag}_{z['net']}", [(ox + x, oy + y) for x, y in z["pts"]],
                   z["priority"] + 10, z["clearance"])
    for t in lay["tracks"]:
        track(net[t["net"]], (ox + t["a"][0], oy + t["a"][1]), (ox + t["b"][0], oy + t["b"][1]), t["w"])
    for v in lay["vias"]:
        via(net[v["net"]], (ox + v["at"][0], oy + v["at"][1]), v["d"], v["drill"])
    # VREG_VIN pin -> under-chip via to the In4 3.3 V plane (inside the pad ring, clear of the EP)
    num = symlib.load("MCU_RaspberryPi", part)[0]["VREG_VIN"][0]
    vin = [p for p in refs[ref].Pads() if p.GetNumber() == num][0]
    vx, vy = vin.GetPosition().x / 1e6, vin.GetPosition().y / 1e6
    inward = 1.0 if vy < oy else -1.0
    track("V3V3", (vx, vy), (vx, vy + inward * 1.15), 0.2)
    via("V3V3", (vx, vy + inward * 1.15), 0.45, 0.2)


def support(tag, u, x, y, bootref, runref, swdref, usb=False, swd_dy=8, part="RP2350A", ref=None):
    """Flash, crystal, core regulator (vreg), decoupling and buttons for one RP2350."""
    # decoupling: one 100 nF per supply pin group (three above the chip, left of the regulator; three below)
    for i in range(3):
        C(f"C{u}{i + 1}", "100nF", "V3V3", "GND", x - 6 + i * 2.4, y - 6.2)
    for i in range(3):
        C(f"C{u}{i + 4}", "100nF", "V3V3", "GND", x + 1.6 + i * 2.4, y + 6.2)
    C(f"C{u}7", "100nF", "V3V3", "GND", x - 6, y + 6.2)
    C(f"C{u}8", "100nF", f"{tag}_1V1", "GND", x - 3.6, y + 6.2)
    C(f"C{u}9", "100nF", f"{tag}_1V1", "GND", x - 1.2, y + 6.2)
    vreg(tag, u, ref, part)
    # QSPI flash
    ic(f"F{u}", "Package_SO", "SOIC-8_5.3x5.3mm_P1.27mm", ("Memory_Flash", "W25Q128JVS"), x + 12, y - 2, mpn="W25Q128JVSIQ", mapping={
        "~{CS}": f"{tag}_QSS", "DO/IO_{1}": f"{tag}_QSD1", "~{WP}/IO_{2}": f"{tag}_QSD2",
        "GND": "GND", "DI/IO_{0}": f"{tag}_QSD0", "CLK": f"{tag}_QSCK",
        "~{HOLD}/~{RESET}/IO_{3}": f"{tag}_QSD3", "VCC": "V3V3"})
    C(f"C{u}22", "100nF", "V3V3", "GND", x + 12, y - 6.5)
    # crystal 12 MHz with 1k series on XOUT
    add(f"Y{u}", "Crystal", "Crystal_SMD_3225-4Pin_3.2x2.5mm", x - 12, y, 90, "12MHz", mpn="ABM8-272-T3")
    conn(f"Y{u}", {"1": f"{tag}_XIN", "3": f"{tag}_XB", "2": "GND", "4": "GND"})
    R(f"R{u}1", "1k", f"{tag}_XB", f"{tag}_XOUT", x - 12, y + 4)
    C(f"C{u}23", "15pF", f"{tag}_XIN", "GND", x - 14.5, y - 3.5)
    C(f"C{u}24", "15pF", f"{tag}_XB", "GND", x - 14.5, y + 3.5)
    # BOOTSEL (QSPI_SS through 1k to a button), RUN pull-up + reset button
    R(f"R{u}2", "1k", f"{tag}_QSS", f"{tag}_BOOT", x + 12, y + 3.0)
    add(bootref, "Button_Switch_SMD", "SW_SPST_B3U-1000P", x + 16, y + 9.5, 0, "BOOTSEL", mpn="B3U-1000P")
    conn(bootref, {"1": f"{tag}_BOOT", "2": "GND"})
    R(f"R{u}3", "10k", "V3V3", f"{tag}_RUN", x + 15, y + 3.0)
    if runref:                      # UI reset is a side-push switch on the board edge instead (pinhole)
        add(runref, "Button_Switch_SMD", "SW_SPST_B3U-1000P", x + 16, y + 14.5, 0, "RESET", mpn="B3U-1000P")
        conn(runref, {"1": f"{tag}_RUN", "2": "GND"})
    # SWD
    add(swdref, "Connector_PinHeader_1.27mm", "PinHeader_1x03_P1.27mm_Vertical_SMD_Pin1Left", x - 19, y + swd_dy, 0, "SWD", spec="1x03 1.27 mm SMD header")
    conn(swdref, {"1": f"{tag}_SWCLK", "2": "GND", "3": f"{tag}_SWDIO"})


# --------------------------------------------------------------------------------------
# MCUs
# --------------------------------------------------------------------------------------
UI_X, UI_Y = 102.0, 42.0
NET_X, NET_Y = 52.0, 44.0
rp2350("UI", "U1", UI_X, UI_Y, UI_GPIO, usb="UI_USB", part="RP2350B")
support("UI", 1, UI_X, UI_Y, "SW1", None, "J3", usb=True, swd_dy=-9, part="RP2350B", ref="U1")
rp2350("NET", "U2", NET_X, NET_Y, NET_GPIO, usb="NET_USB_MCU")
support("NET", 2, NET_X, NET_Y, "SW3", "SW4", "J4", swd_dy=4, part="RP2350A", ref="U2")

# --------------------------------------------------------------------------------------
# Power: USB-C -> BQ25798 -> VSYS -> 5 V buck -> 3.3 V buck
# --------------------------------------------------------------------------------------
add("J1", "Connector_USB", "USB_C_Receptacle_HRO_TYPE-C-31-M-12", 0, 0, 90, "USB-C", mpn="TYPE-C-31-M-12")
conn("J1", {"A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND",
            "A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS",
            "A5": "CC1", "B5": "CC2", "A6": "USB_P", "B6": "USB_P", "A7": "USB_N", "B7": "USB_N"})
place_edge("J1", "right", 16)
# USB-C port 1 is dual-role: TUSB320 CC controller (I2C 0x60 on the charger bus, INT shared with the
# charger's open-drain CHG_INT). Unpowered it still presents Rd, so a flat device charges from any
# USB-C source. In host mode the BQ25798's OTG boost supplies VBUS (firmware).
ic("U10", "Package_DFN_QFN", "Texas_X2QFN-12_1.6x1.6mm_P0.4mm", ("Interface_USB", "TUSB320"), 137, 21,
   {"CC1": "CC1", "CC2": "CC2", "VBUS_DET": "VBUS_DET", "ADDR": "GND", "~{INT}/OUT3": "CHG_INT",
    "SDA/OUT1": "I2C_SDA", "SCL/OUT2": "I2C_SCL", "GND": "GND", "~{EN}": "GND", "VDD": "V3V3"},
   value="TUSB320", mpn="TUSB320LAIRWBR")    # PORT open = dual-role; ID open (state read over I2C)
R("R100", "887k", "VBUS", "VBUS_DET", 140.5, 21)      # datasheet RVBUS 887k (855-920k)
C("C100", "100nF", "V3V3", "GND", 133.5, 21)
ic("U3", "Package_TO_SOT_SMD", "SOT-23-6", ("Power_Protection", "USBLC6-2SC6"), 140, 8, {
    "I/O1": "USB_P", "GND": "GND", "I/O2": "USB_N", "VBUS": "VBUS"}, value="USBLC6-2SC6", mpn="USBLC6-2SC6")
R("RUD1", "27", "USB_P", "UI_USB_P", 132, 14)
R("RUD2", "27", "USB_N", "UI_USB_N", 132, 16)

# BQ25798 charger (2S pack on BAT)
ic("U5", "Package_DFN_QFN", "Texas_RQM0029A_VQFN-29_4x4mm_P0.4mm", ("Battery_Management", "BQ25798"),
   28, 26, {"STAT": "CHG_STAT", "VBUS": "VBUS", "BTST1": "BTST1", "REGN": "REGN", "D+": "USB_P",
            "D-": "USB_N", "VAC2": "VBUS", "VAC1": "VBUS", "SCL": "I2C_SCL", "SDA": "I2C_SDA",
            "TS": "TS", "ILIM_HIZ": "ILIM", "BATP": "VBATP", "BTST2": "BTST2", "~{INT}": "CHG_INT",
            "BAT": "VBAT", "SYS": "VSYS", "SW2": "SW2", "GND": "GND", "SW1": "SW1", "PMID": "PMID",
            "~{CE}": "GND", "ACDRV1": "GND", "ACDRV2": "GND", "PROG": "PROG", "SDRV": "SDRV", "~{QON}": "QON"},
   mpn="BQ25798RQMR")   # ACDRV to GND: no input FETs. QON = power button (via D50).
# Charger layout (real board mm, fixed=True), after the BQ25798 datasheet layout guide: L5 straight above
# the SW1/SW2 pins with its own switch-node pours; PMID caps on a strip from the PMID pin; BTST caps beside
# the switch pours; REGN cap at its pin; VBUS pour along the left pins (a corridor for the REGN cap); VSYS
# strip from the SYS pin to its caps, then a VSYS area up to the 5 V buck; BAT pour from the BAT pins around
# to the ship FET Q50; VBAT_PACK pour from J2 to Q50's drain. Pours are named PWR_*: the autorouter sees them
# (other nets keep off), so they stay solid.
add("L5", "Inductor_SMD", "L_Bourns_SRP7028A_7.3x6.6mm", 28.0, 23.5, 0, "2.2uH", mpn="SRP7028A-2R2M", fixed=True)
conn("L5", {"1": "SW1", "2": "SW2"})


def Cf(ref, val, a, b, x, y, size="0402", rot=0):
    """C() in real board coordinates."""
    C(ref, val, a, b, x, y / SY, size, rot)


def Rf(ref, val, a, b, x, y, rot=0):
    R(ref, val, a, b, x, y / SY, rot)


Cf("C52", "10uF", "PMID", "GND", 22.6, 29.0, "0805", 90)        # PMID pad (1) down on the PMID strip
Cf("C53", "10uF", "PMID", "GND", 20.6, 29.0, "0805", 90)
Cf("C54", "47nF", "BTST1", "SW1", 24.75, 28.25, "0402", 0)      # pad 2 on the SW1 pour
Cf("C55", "47nF", "BTST2", "SW2", 31.25, 28.25, "0402", 180)    # pad 2 on the SW2 pour
Cf("C50", "10uF", "VBUS", "GND", 18.6, 31.85, "0805", 180)       # VBUS pad (1) on the VBUS pour
Cf("C51", "10uF", "VBUS", "GND", 18.6, 33.95, "0805", 180)
Cf("C56", "4.7uF", "REGN", "GND", 23.9, 32.12, "0603", 180)     # REGN pad (1) next to pin 5
Cf("C57", "10uF", "VSYS", "GND", 33.6, 29.0, "0805", 90)        # VSYS pad (1) down on the VSYS strip
Cf("C58", "10uF", "VSYS", "GND", 35.6, 29.0, "0805", 90)
Cf("C59", "10uF", "VBAT", "GND", 34.55, 33.0, "0805", 0)        # VBAT pad (1) on the BAT column
Cf("C510", "10uF", "VBAT", "GND", 34.55, 35.2, "0805", 0)
track("REGN", (26.10, 32.12), (24.9, 32.12), 0.2)             # REGN pin 5 -> C56
R("R50", "5.23k", "REGN", "TS", 40, 19)
R("R51", "30.1k", "TS", "GND", 40, 21)
R("R52", "47k", "REGN", "ILIM", 40, 23)
R("R53", "47k", "ILIM", "GND", 40, 25)
R("R54", "4.7k", "V3V3", "I2C_SDA", 44, 19)
R("R55", "4.7k", "V3V3", "I2C_SCL", 44, 21)
R("R56", "10k", "V3V3", "CHG_INT", 44, 23)
R("R57", "10k", "V3V3", "CHG_STAT", 44, 25)
R("R58", "8.2k", "PROG", "GND", 40, 27)          # datasheet Table 7-1: 2s, 750 kHz (needs the 2.2 uH L5)
Rf("R59", "100", "VBATP", "VBAT_PACK", 16.95, 28.6, 180)   # datasheet: 100R from BATP to the pack + side
# Ship FET (datasheet 7.3.12, Figure 7-15): N-FET between the pack and BAT, gate on SDRV. Firmware
# "power off" sets SDRV_CTRL = 10 (ship mode): the FET disconnects the pack (no drain at all). Pressing the
# power button (QON low for 1 s, or 15 ms with WKUP_DLY) or plugging in USB turns it back on; holding it
# 10 s power-cycles the whole system (tRST). Drain tab towards J2 (PWR_VBAT_PACK), sources into PWR_VBAT.
add("Q50", "Package_SON", "VSON-8_3.3x3.3mm_P0.65mm_TI_Q3A", 15, 37, 90, "CSD17581Q3A", mpn="CSD17581Q3A", fixed=True)
SYMBOL["Q50"] = (LOCAL_LIB, "NMOS_SON8_Q3A")
conn("Q50", {"1": "VBAT", "2": "VBAT", "3": "VBAT", "4": "SDRV", "5": "VBAT_PACK"})
Cf("C512", "10nF", "QON", "GND", 27.8, 35.75)   # QON filter: 200k internal pull-up x 10 nF = 2 ms
add("J2", "Connector_AMASS", "AMASS_XT30PW-M_1x02_P2.50mm_Horizontal", 0, 0, 90, "BATTERY 2S", mpn="XT30PW-M")
conn("J2", {"1": "VBAT_PACK", "2": "GND"})
place_edge("J2", "left", 26)
add("J5", "Connector_JST", "JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical", 10, 46, 0, "NTC", mpn="B2B-PH-K-S")
conn("J5", {"1": "TS", "2": "GND"})
track("QON", (27.8, 34.02), (27.8, 35.35), 0.15)                # QON pin 12 -> C512 (straight down)
track("QON", (27.8, 35.35), (27.32, 35.75), 0.15)
track("GND", (28.0, 30.42), (28.0, 29.4), 0.2)                  # GND pin 27 (between SW1 and SW2) -> via
via("GND", (28.0, 29.4), 0.35, 0.15)

# 5 V buck (TPS62933 at 62, 14.8): input caps on VIN/GND with a local GND pour, L6 below-right on a SW5 pour,
# BST cap at the pin, output caps beside L6 on the V5 pour.
ic("U6", "Package_TO_SOT_SMD", "SOT-583-8", ("Regulator_Switching", "TPS62933"), 62, 12,
   {"EN": "VSYS", "VIN": "VSYS", "GND": "GND", "SW": "SW5", "BST": "BST5", "SS": "SS5", "FB": "FB5"},
   mpn="TPS62933DRLR")   # RT open: 500 kHz
add("L6", "Inductor_SMD", "L_Bourns_SRP7028A_7.3x6.6mm", 66.0, 20.2, 0, "4.7uH", mpn="SRP7028A-4R7M", fixed=True)
conn("L6", {"1": "SW5", "2": "V5"})
Cf("C60", "10uF", "VSYS", "GND", 59.55, 15.2, "0805", 270)      # VSYS pad (1) up, GND down
Cf("C61", "10uF", "VSYS", "GND", 57.45, 15.2, "0805", 270)
Cf("C62", "100nF", "BST5", "SW5", 64.0, 14.75, "0402", 270)    # BST5 up, SW5 (2) down onto the SW5 pour
Cf("C63", "10nF", "SS5", "GND", 64.6, 13.2)
Rf("R61", "10k", "FB5", "GND", 64.6, 12.2)
Rf("R60", "52.3k", "V5", "FB5", 64.6, 11.2, 180)
Cf("C64", "22uF", "V5", "GND", 72.3, 18.2, "0805")
Cf("C65", "22uF", "V5", "GND", 72.3, 20.3, "0805")
Cf("C66", "22uF", "V5", "GND", 72.3, 22.4, "0805")

# 3.3 V buck (AP63203 at 90, 12.35): C70 across VIN/GND right under the chip, L7 at the SW pin, BST cap at
# the pin, output caps on a 3.3 V pour with plane vias.
ic("U7", "Package_TO_SOT_SMD", "TSOT-23-6", ("Regulator_Switching", "AP63203WU"), 90, 10,
   {"FB": "V3V3", "EN": "V5", "IN": "V5", "GND": "GND", "SW": "SW3", "BST": "BST3"}, mpn="AP63203WU-7")
add("L7", "Inductor_SMD", "L_Bourns_SRN6045TA", 95.9, 12.35, 0, "4.7uH", mpn="SRN6045TA-4R7M", fixed=True)
conn("L7", {"1": "SW3", "2": "V3V3"})
Cf("C70", "10uF", "V5", "GND", 90.0, 15.2, "0805")
Cf("C71", "100nF", "BST3", "SW3", 91.35, 9.95)
Cf("C72", "22uF", "V3V3", "GND", 101.2, 10.3, "0805")
Cf("C73", "22uF", "V3V3", "GND", 101.2, 12.4, "0805")
Cf("C74", "22uF", "V3V3", "GND", 101.2, 14.5, "0805")
for vx, vy in ((99.45, 11.35), (99.45, 13.45)):                  # 3.3 V output pour -> In4 plane
    via("V3V3", (vx, vy), 0.6, 0.3)
R("R70", "4.7k", "V3V3", "PWR_LED", 98, 4)      # ~0.3 mA, always on: keep standby drain low
add("D1", "LED_SMD", "LED_0603_1608Metric", 101, 4, 0, "PWR", spec="LED green 0603")
conn("D1", {"1": "GND", "2": "PWR_LED"})

# --------------------------------------------------------------------------------------
# Peripherals
# --------------------------------------------------------------------------------------
# HDMI (internal link to the panel; mouth faces the hinge/top edge). Standard HDMI-A pin order.
add("J6", "Connector_Video", "HDMI_A_Molex_208658-1001_Horizontal", 0, 0, 90, "HDMI to panel", mpn="2086581001")
conn("J6", {"1": "HD_D2P", "2": "GND", "3": "HD_D2N", "4": "HD_D1P", "5": "GND", "6": "HD_D1N",
            "7": "HD_D0P", "8": "GND", "9": "HD_D0N", "10": "HD_CKP", "11": "GND", "12": "HD_CKN",
            "17": "GND", "18": "V5_PANEL", "SH": "GND"})   # +5V pin 18: sinks need it to see a source
place_edge("J6", "top", 116)
for i, (a, b) in enumerate([("TMDS_D0P", "HD_D0P"), ("TMDS_D0N", "HD_D0N"), ("TMDS_CKP", "HD_CKP"),
                            ("TMDS_CKN", "HD_CKN"), ("TMDS_D2P", "HD_D2P"), ("TMDS_D2N", "HD_D2N"),
                            ("TMDS_D1P", "HD_D1P"), ("TMDS_D1N", "HD_D1N")]):
    R(f"R8{i}", "270", a, b, 102 + i * 2.2, 28)
# 5 V power out to the panel (separate from HDMI)
add("J7", "Connector_JST", "JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical", 72, 4, 0, "PANEL 5V", mpn="B2B-PH-K-S")
conn("J7", {"1": "V5_PANEL", "2": "GND"})

# Panel 5 V load switch: the display (3.1 W) is switched off for standby. PANEL_EN low (pull-down)
# keeps it off through reset; firmware should stop HSTX before switching the panel off.
ic("U9", "Package_TO_SOT_SMD", "SOT-23-6", ("Power_Management", "TPS22917DBV"), 76, 9,
   {"VIN": "V5", "GND": "GND", "ON": "PANEL_EN", "CT": "PANEL_CT", "VOUT": "V5_PANEL"},
   value="TPS22917", mpn="TPS22917DBVR")
C("C67", "1uF", "V5", "GND", 76, 12.5, "0402")
C("C68", "10uF", "V5_PANEL", "GND", 79.8, 9, "0805")
C("C69", "1nF", "PANEL_CT", "GND", 72.8, 9)       # CT: slows turn-on to limit panel inrush
R("R99", "100k", "PANEL_EN", "GND", 79.8, 12.5)
add("J8", "Connector_JST", "JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical", 81, 4, 0, "AUX 5V", mpn="B2B-PH-K-S")
conn("J8", {"1": "V5", "2": "GND"})

# microSD (SPI mode)
add("J9", "Connector_Card", "microSD_HC_Hirose_DM3AT-SF-PEJM5", 0, 0, 90, "microSD", mpn="DM3AT-SF-PEJM5")
conn("J9", {"1": "SD_NC2", "2": "SD_CS", "3": "SD_MOSI", "4": "V3V3", "5": "SD_SCK", "6": "GND",
            "7": "SD_MISO", "8": "SD_NC1", "9": "SD_DET", "10": "GND", "SH": "GND"})
place_edge("J9", "right", 52)
R("R90", "10k", "V3V3", "SD_NC1", 124, 41)
R("R91", "10k", "V3V3", "SD_NC2", 124, 43)
R("R92", "10k", "V3V3", "SD_CS", 124, 45)
C("C90", "100nF", "V3V3", "GND", 124, 47)

# Wi-Fi: Raspberry Pi RM2 (CYW43439, onboard antenna), wired like the Pico 2 W (RM2 datasheet Table 1/2).
# Rotated 180 so the antenna end sits flush on the front board edge; its RF keep-out (in the footprint)
# hangs off the board. Firmware: CYW43 pins WL_ON=23, DATA=24, CS=25, CLK=26 (NET MCU).
add("U8", LOCAL_LIB, "RaspberryPi_RM2", 85, BH - 8.25, 180, "RM2", mpn="RMC20452T", fixed=True)
SYMBOL["U8"] = (LOCAL_LIB, "RaspberryPi_RM2")
conn("U8", {"1": "GND", "4": "GND", "7": "GND", "11": "GND", "15": "GND", "21": "GND",
            "3": "WL_CLK", "5": "WL_DATA", "6": "WL_DOUT", "9": "WL_CS", "10": "WL_IRQ",
            "12": "WL_ON", "13": "WL_ON", "14": "V3V3", "16": "V3V3"})
R("R96", "470", "WL_DATA", "WL_DOUT", 87.5, 49.5)
R("R97", "10k", "WL_DATA", "WL_IRQ", 90, 49.5)
C("C80", "100nF", "V3V3", "GND", 80.5, 49.5)
C("C81", "10uF", "V3V3", "GND", 83.5, 49.5, "0805")

# Keyboard matrix header (matches keyboard.kicad_pcb J1: ROW0-5 then COL0-13)
# right-angle pins stick out past the front edge (pin 1 at the right end); cable to keyboard J1
add("J11", "Connector_PinHeader_2.54mm", "PinHeader_1x20_P2.54mm_Horizontal", 61, BH - 4.5, 270, "KB_MATRIX", spec="1x20 2.54 mm right-angle header", fixed=True)
conn("J11", {str(i + 1): n for i, n in enumerate([f"ROW{r}" for r in range(6)] + [f"COL{c}" for c in range(14)])})

# Printer UART / expansion / status
add("J12", "Connector_JST", "JST_SH_SM06B-SRSS-TB_1x06-1MP_P1.00mm_Horizontal", 140, 64, 0, "PRINTER", mpn="SM06B-SRSS-TB")
conn("J12", {"MP": "GND", "1": "V5", "2": "PRN_TX", "3": "PRN_RX", "4": "PRN_RTS", "5": "PRN_CTS", "6": "GND"})
add("J13", "Connector_PinHeader_1.27mm", "PinHeader_1x10_P1.27mm_Vertical", 120, 62, 90, "EXPANSION", spec="1x10 1.27 mm header")
conn("J13", {"1": "V3V3", "2": "GND", **{str(3 + i): f"EXP{g}" for i, g in enumerate(EXP_GPIO)}, "9": "GND", "10": "V3V3"})

# UI reset on the right edge, side-actuated, behind a pinhole in the case wall. Double-tap = USB update
# mode (pico_bootsel_via_double_reset in the UI firmware).
# System reset: SW2 pulls both RUN pins low through D51 (dual Schottky, common cathode), so one press
# resets the UI and NET MCUs together; each RUN keeps its own 10k pull-up and SW4 still resets NET alone.
add("SW2", "Button_Switch_SMD", "Panasonic_EVQPUJ_EVQPUA", 0, 0, 270, "RESET", mpn="EVQ-PUJ02K")
conn("SW2", {"1": "SYS_RST", "2": "GND"})
place_edge("SW2", "right", 34)
add("D51", "Package_TO_SOT_SMD", "SOT-23", 144, 36, 0, "BAT54C", mpn="BAT54C", fixed=True)
SYMBOL["D51"] = ("Diode", "BAT54C")
conn("D51", {"1": "UI_RUN", "2": "NET_RUN", "3": "SYS_RST"})

# Power button: right wall, above the reset pinhole, finger-pressed through a printed plunger in the case.
# It pulls the charger's QON (exit ship mode / 10 s system power cycle) and UI GPIO37 (short presses:
# sleep, wake, soft power-off) low through D50. QON's internal pull-up reaches 3.8 V, so the diode keeps
# it off the 3.3 V GPIO; with the system off (ship mode) the GPIO side is unpowered and blocks too.
add("SW5", "Button_Switch_SMD", "Panasonic_EVQPUJ_EVQPUA", 0, 0, 270, "POWER", mpn="EVQ-PUJ02K")
conn("SW5", {"1": "PWR_KEY", "2": "GND"})
place_edge("SW5", "right", 25.55)
add("D50", "Package_TO_SOT_SMD", "SOT-23", 144, 26, 0, "BAT54C", mpn="BAT54C", fixed=True)
SYMBOL["D50"] = ("Diode", "BAT54C")
conn("D50", {"1": "QON", "2": "UI_PWR_KEY", "3": "PWR_KEY"})
R("R130", "10k", "V3V3", "UI_PWR_KEY", 113, 53.2 / SY)

# NET MCU USB for factory/recovery flashing: 27R series, internal JST-SH 4-pin (pin 1 VBUS not connected:
# the board powers itself; connect GND, D-, D+ from a PC)
R("RNU1", "27", "NET_USB_MCU_P", "NET_USB_P", 44, 36)
R("RNU2", "27", "NET_USB_MCU_N", "NET_USB_N", 44, 38)
# USB-C port 2 (right wall, below the microSD): the NET MCU's own USB, device-only (5.1k Rd), data only.
# Its VBUS is isolated (ESD clamp only) so two plugged-in sources can never back-feed each other.
add("J14", "Connector_USB", "USB_C_Receptacle_HRO_TYPE-C-31-M-12", 0, 0, 90, "USB-C NET", mpn="TYPE-C-31-M-12")
conn("J14", {"A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND",
             "A4": "VBUS2", "A9": "VBUS2", "B4": "VBUS2", "B9": "VBUS2",
             "A5": "CC3", "B5": "CC4", "A6": "NET_USB_P", "B6": "NET_USB_P", "A7": "NET_USB_N", "B7": "NET_USB_N"})
place_edge("J14", "right", 65.5)
R("RCC3", "5.1k", "CC3", "GND", 131, 55)
R("RCC4", "5.1k", "CC4", "GND", 131, 57)
ic("U11", "Package_TO_SOT_SMD", "SOT-23-6", ("Power_Protection", "USBLC6-2SC6"), 136, 54, {
    "I/O1": "NET_USB_P", "GND": "GND", "I/O2": "NET_USB_N", "VBUS": "VBUS2"}, value="USBLC6-2SC6", mpn="USBLC6-2SC6")

# 64 GB eMMC 5.1 (JEDEC 153-ball FBGA) below the UI MCU, 4-bit bus on GPIO30-36. VCC and VCCQ both 3.3 V.
# Ball map + pull-up / VDDi values: Kimtigo KM110SS1064GxA datasheet (CMD 4.7-100k, DAT 10-100k, VDDi 1 uF).
# Fab: the 0.5 mm-pitch balls use via-in-pad (filled + capped), placed by fanout.py.
EMMC_X, EMMC_Y = 99.6, 70.5                      # real board coords: right of the RM2, below the UI MCU
add("U12", "Package_BGA", "LFBGA-153_11.5x13mm_Layout14x14_P0.5mm", EMMC_X, EMMC_Y, 0, "eMMC 64GB",
    mpn="KM110SS1064GxA-DDD00WT", fixed=True)
SYMBOL["U12"] = (LOCAL_LIB, "eMMC_FBGA153")
import sys as _s  # noqa: E402
_s.path.insert(0, KICAD)
import projsyms  # noqa: E402
emmc_nets = {"A3": "EMMC_DAT0", "A4": "EMMC_DAT1", "A5": "EMMC_DAT2", "B2": "EMMC_DAT3",
             "B3": "EMMC_DAT4", "B4": "EMMC_DAT5", "B5": "EMMC_DAT6", "B6": "EMMC_DAT7",
             "M5": "EMMC_CMD", "M6": "EMMC_CLK", "K5": "EMMC_RST", "C2": "EMMC_VDDI"}
emmc_nets.update({b: "V3V3" for b, n in projsyms.EMMC_PWR.items() if n in ("VCC", "VCCQ")})
emmc_nets.update({b: "GND" for b in projsyms.EMMC_GND})
conn("U12", emmc_nets)
# passives: top row, right column, bottom row around the BGA (real coordinates)
emmc_parts = [("R", "R110", "10k", "V3V3", "EMMC_CMD"), ("R", "R111", "10k", "V3V3", "EMMC_DAT0"),
              ("R", "R112", "10k", "V3V3", "EMMC_DAT1"), ("R", "R113", "10k", "V3V3", "EMMC_DAT2"),
              ("R", "R114", "10k", "V3V3", "EMMC_DAT3"), ("R", "R115", "10k", "V3V3", "EMMC_RST"),
              ("R", "R116", "47k", "V3V3", "EMMC_DAT4"), ("R", "R117", "47k", "V3V3", "EMMC_DAT5"),
              ("R", "R118", "47k", "V3V3", "EMMC_DAT6"), ("R", "R119", "47k", "V3V3", "EMMC_DAT7"),
              ("C", "C110", "100nF", "V3V3", "GND"), ("C", "C111", "100nF", "V3V3", "GND"),
              ("C", "C113", "100nF", "V3V3", "GND"), ("C", "C114", "100nF", "V3V3", "GND"),
              ("C", "C116", "1uF", "EMMC_VDDI", "GND"),
              ("C6", "C112", "4.7uF", "V3V3", "GND"), ("C6", "C115", "4.7uF", "V3V3", "GND")]
slots = [(95.0 + i * 2.2, 61.7) for i in range(5)] + [(108.0, 63.5 + i * 1.7) for i in range(6)] + \
        [(111.0, 63.5 + i * 1.9) for i in range(6)]
for (kind, ref, val, a_, b_), (x, y) in zip(emmc_parts, slots):
    if kind == "R":
        R(ref, val, a_, b_, x, y / SY)
    else:
        C(ref, val, a_, b_, x, y / SY, "0603" if kind == "C6" else "0402")
R("R95", "1k", "UI_LED", "UI_LEDK", 126, 59.5)
add("D2", "LED_SMD", "LED_0603_1608Metric", 129, 59.5, 0, "UI", spec="LED green 0603")
conn("D2", {"1": "GND", "2": "UI_LEDK"})

# Beeper: piezo driven straight from GPIO26 (PWM) through 100R
add("BZ1", "Buzzer_Beeper", "Buzzer_Murata_PKMCS0909E", 128, 30, 0, "Piezo", mpn="PKMCS0909E4000-R1")
conn("BZ1", {"1": "BUZZ_R", "2": "GND"})
R("R98", "100", "BUZZ", "BUZZ_R", 128, 36)

# Mounting holes (M2.5); case.py reads their positions from mainboard.json
HOLES = [(4, 4), (BW - 4, 4), (4, BH - 4), (BW - 4, BH - 4)]
for i, (x, y) in enumerate(HOLES):
    add(f"H{i + 1}", "MountingHole", "MountingHole_2.7mm_M2.5", x, y, 0, "M2.5", fixed=True)

# Fiducials for SMT assembly
for i, (x, y) in enumerate([(10, 3), (138, 3), (4, 56 * SY)]):
    add(f"FID{i + 1}", "Fiducial", "Fiducial_1mm_Mask2mm", x, y, 0, "Fiducial", fixed=True)
    refs[f"FID{i + 1}"].Reference().SetVisible(False)
    fplib.keepout_circle(board, x, y, 1.8)

def silk_text(text, x, y, size, thick, bold=False):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetLayer(pcbnew.F_SilkS)
    t.SetPosition(mm(x, y))
    t.SetTextSize(mm(size, size))
    t.SetTextThickness(FromMM(thick))
    board.Add(t)


silk_text("Pico COMP", 40, 2.6, 1.6, 0.25)
silk_text("mainboard v1.0   \u00a9 2026 Aditya Kale", 112, BH - 1.8, 1.0, 0.15)

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


def zone(layer, net, name=""):
    z = pcbnew.ZONE(board)
    z.SetZoneName(name)
    z.SetLayer(layer)
    z.SetNet(N(net))
    z.SetIsRuleArea(False)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in [(0.5, 0.5), (BW - 0.5, 0.5), (BW - 0.5, BH - 0.5), (0.5, BH - 0.5)]:
        ol.Append(FromMM(x), FromMM(y))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetMinThickness(FromMM(0.2))
    # pcbnew's zone default is 0.5 mm: under the 0.5 mm-pitch eMMC BGA that cuts the plane into islands
    # and leaves its GND/3V3 via-in-pad balls unconnected
    z.SetLocalClearance(FromMM(0.2))
    z.SetThermalReliefGap(FromMM(0.25))
    z.SetThermalReliefSpokeWidth(FromMM(0.3))
    board.Add(z)


zone(pcbnew.In1_Cu, "GND")
zone(pcbnew.In4_Cu, "V3V3")
zone(pcbnew.B_Cu, "GND", "POUR_GND_B")


def power_pour(net, clip, priority, layer=pcbnew.F_Cu):
    clip = (clip[0], clip[1] * SY, clip[2], clip[3] * SY)       # clip given in the 68 mm design frame
    """Solid-connected F.Cu pour covering this net's pads inside `clip` (x0, y0, x1, y1), +1 mm.
    Carries the current that fine-pitch pins can only reach with a necked-down trace."""
    pts = []
    for fp in refs.values():
        for p in fp.Pads():
            if p.GetNetname() == net:
                c = p.GetPosition()
                if clip[0] <= c.x / 1e6 <= clip[2] and clip[1] <= c.y / 1e6 <= clip[3]:
                    bb = p.GetBoundingBox()
                    pts += [(bb.GetLeft() / 1e6, bb.GetTop() / 1e6), (bb.GetRight() / 1e6, bb.GetBottom() / 1e6)]
    x0 = max(min(x for x, _ in pts) - 1.0, clip[0], 0.6)
    y0 = max(min(y for _, y in pts) - 1.0, clip[1], 0.6)
    x1 = min(max(x for x, _ in pts) + 1.0, clip[2], BW - 0.6)
    y1 = min(max(y for _, y in pts) + 1.0, clip[3], BH - 0.6)
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(N(net))
    z.SetAssignedPriority(priority)
    z.SetZoneName(f"POUR_{net}")
    ol = z.Outline()
    ol.NewOutline()
    for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
        ol.Append(FromMM(x), FromMM(y))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetLocalClearance(FromMM(0.2))
    z.SetMinThickness(FromMM(0.25))
    board.Add(z)


# Power pours with explicit outlines (real mm; see the charger / buck notes above). Priorities: switch nodes and
# the local GND / PMID / VSYS / BAT copper of each stage above the generic areas; VREG_* (RP2350) above all.
PWR = [
    ("SW1", 9, [(27.67, 30.0), (27.67, 28.6), (26.75, 26.0), (26.75, 25.0), (23.8, 25.0), (23.8, 27.6), (24.8, 27.6),
                (24.8, 28.9), (27.15, 28.9), (27.43, 29.25), (27.43, 30.0)]),
    ("SW2", 9, [(28.33, 30.0), (28.33, 28.6), (29.25, 26.0), (29.25, 25.0), (32.2, 25.0), (32.2, 27.6), (31.2, 27.6),
                (31.2, 28.9), (28.85, 28.9), (28.57, 29.25), (28.57, 30.0)]),
    ("PMID", 9, [(27.22, 30.05), (27.22, 29.45), (27.0, 29.3), (19.75, 29.3), (19.75, 30.5), (25.6, 30.5), (26.0, 30.25),
                 (26.98, 30.25), (26.98, 30.05)]),
    ("VBUS", 3, [(19.6, 30.75), (26.0, 30.75), (26.0, 31.45), (21.4, 31.45), (21.4, 33.1), (26.0, 33.1), (26.0, 33.6),
                 (26.7, 33.6), (26.7, 34.3), (19.6, 34.3)]),
    ("VSYS", 6, [(28.8, 30.0), (29.02, 30.0), (29.02, 30.25), (38.8, 30.25), (38.8, 22.0), (56.5, 22.0), (56.5, 15.3),
                 (61.62, 15.3), (61.62, 9.0), (36.6, 9.0), (36.6, 29.35), (29.15, 29.35), (28.8, 29.6)]),
    ("VBAT", 7, [(29.9, 30.75), (34.8, 30.75), (34.8, 41.0), (13.0, 41.0), (13.0, 37.85), (15.6, 37.85), (15.6, 39.3),
                 (17.6, 39.3), (17.6, 37.3), (33.3, 37.3), (33.3, 31.5), (29.9, 31.5)]),
    ("VBAT_PACK", 7, [(11.3, 21.5), (15.9, 21.5), (15.9, 28.05), (16.75, 28.05), (16.75, 29.15), (15.9, 29.15),
                      (15.9, 37.0), (11.3, 37.0)]),
    ("GND", 8, [(56.6, 15.45), (61.62, 15.45), (61.62, 17.5), (56.6, 17.5)]),            # 5 V buck input loop
    ("SW5", 9, [(62.4, 15.45), (63.6, 15.45), (63.7, 14.95), (64.35, 14.95), (64.35, 15.6), (64.75, 16.0),
                (64.75, 18.6), (61.85, 18.6), (61.85, 17.7), (62.4, 17.2)]),
    ("V5", 5, [(67.3, 23.4), (71.95, 23.4), (71.95, 17.4), (89.5, 17.4), (89.5, 12.0), (86.0, 12.0), (86.0, 16.4),
               (67.3, 16.4)]),
    ("GND", 8, [(90.45, 13.0), (91.85, 13.0), (91.85, 16.0), (90.45, 16.0)]),             # 3.3 V buck input loop
    ("SW3", 9, [(91.85, 9.75), (93.2, 9.75), (93.2, 12.75), (91.6, 12.75), (91.6, 12.0), (91.85, 11.9)]),
    ("V3V3", 7, [(96.85, 9.5), (100.8, 9.5), (100.8, 15.3), (96.85, 15.3)]),
]
for i, (n, pri, pts) in enumerate(PWR):
    zone_local(n, f"PWR_{n}_{i}", pts, pri, 0.2)
for vx in (57.3, 58.8, 60.3):                                     # 5 V buck input-loop GND pour -> In1 plane
    via("GND", (vx, 17.0), 0.6, 0.3)
for vx in (90.85, 91.5):                                          # 3.3 V buck input-loop GND pour -> In1 plane
    via("GND", (vx, 14.04), 0.45, 0.2)
# VBUS trunk: USB-C J1 (right edge) to the charger's VBUS pour (left), up to 1.9 A (ILIM). 1.2 mm on In3
# (~0.1 V drop at 1.9 A over its ~125 mm), two vias at J1 (one per VBUS pad pair), three into the pour.
# Laid down before fan-out and autorouting, which keep out of it.
for y in (13.55, 18.45):
    track("VBUS", (143.6, y), (142.3, y), 0.5)
VBUS_TRUNK = [(142.3, 13.55), (142.3, 18.45), (140.85, 20.0), (42.0, 20.0), (23.0, 30.0), (21.6, 31.1),
              (20.75, 31.95), (20.75, 32.75)]
for a, b in zip(VBUS_TRUNK, VBUS_TRUNK[1:]):
    track("VBUS", a, b, 1.2, pcbnew.In3_Cu)
for v in ((142.3, 13.55), (142.3, 18.45), (21.6, 31.1), (20.75, 31.95), (20.75, 32.75)):
    via("VBUS", v, 0.6, 0.3)

ds = board.GetDesignSettings()
ds.m_TrackMinWidth = FromMM(0.127)
ds.m_ViasMinSize = FromMM(0.3)       # 0.3 / 0.15 mm via-in-pad under the eMMC BGA
ds.m_MinThroughDrill = FromMM(0.15)
ds.m_MinClearance = FromMM(0.127)
ds.m_CopperEdgeClearance = FromMM(0.3)
nc = ds.m_NetSettings.GetDefaultNetclass()
nc.SetClearance(FromMM(0.127))     # 5 mil: standard for 6-layer fabs (JLC-class minimum is 0.09 mm)
nc.SetTrackWidth(FromMM(0.127))
nc.SetViaDiameter(FromMM(0.45))    # 0.45 / 0.2 mm vias (6-layer fab minimum is typically 0.3 / 0.15)
nc.SetViaDrill(FromMM(0.2))
pw = pcbnew.NETCLASS("Power")
pw.SetClearance(FromMM(0.15))      # must fit between the BQ25798's 0.2 mm pads at 0.4 mm pitch
pw.SetTrackWidth(FromMM(0.25))     # current is carried by the power pours
pw.SetViaDiameter(FromMM(0.6))
pw.SetViaDrill(FromMM(0.3))
ds.m_NetSettings.SetNetclass("Power", pw)
for pat in ("VBUS", "VBAT", "VBAT_PACK", "VSYS", "V5", "V5_PANEL", "SW1", "SW2", "SW5", "SW3", "PMID"):
    ds.m_NetSettings.SetNetclassPatternAssignment(pat, "Power")
# Differential pairs for interactive routing (Route > Differential Pair). Width/gap are starting values
# for ~100 ohm (TMDS) / ~90 ohm (USB) on an outer layer over the In1 GND plane: confirm them with the
# fab's 6-layer stack-up in KiCad's calculator before routing.
# 1.6 mm 6-layer with ~0.1 mm L1-L2 prepreg (IPC-2141 estimate): 0.132/0.20 = ~100 ohm, 0.162/0.20 = ~90 ohm
for name, w, gap, pats in (("HDMI_TMDS", 0.132, 0.2, ("TMDS_*", "HD_D*", "HD_CK*")),
                           ("USB", 0.162, 0.2, ("USB_P", "USB_N", "UI_USB_*"))):
    dp = pcbnew.NETCLASS(name)
    dp.SetClearance(FromMM(0.15))
    dp.SetTrackWidth(FromMM(w))
    dp.SetDiffPairWidth(FromMM(w))
    dp.SetDiffPairGap(FromMM(gap))
    dp.SetViaDiameter(FromMM(0.45))
    dp.SetViaDrill(FromMM(0.2))
    ds.m_NetSettings.SetNetclass(name, dp)
    for pat in pats:
        ds.m_NetSettings.SetNetclassPatternAssignment(pat, name)

board.Save(OUT)


def bbox(ref):
    b = refs[ref].GetBoundingBox(False)
    return [round(v / 1e6, 3) for v in (b.GetLeft(), b.GetTop(), b.GetRight(), b.GetBottom())]


# Data for gen_sch.py (symbols) and the FreeCAD case (connector/hole positions, PCB frame: y down)
RM2_X, RM2_Y = 85, BH - 8.25
json.dump({"board": [BW, BH], "holes": HOLES,
           "rf_keepout": [RM2_X - 17.75, BH - 5.0, RM2_X + 17.75, BH + 13.5],
           "connectors": {r: {"bbox": bbox(r), "value": refs[r].GetValue()}
                          for r in ("J1", "J2", "J6", "J9", "J11", "J12", "J13", "J7", "J8", "J5", "U8", "SW2", "SW5", "J14")},
           "symbols": SYMBOL},
          open(os.path.join(KICAD, "mainboard.json"), "w"), indent=1)
print(f"{len(refs)} footprints, {len(_nets)} nets, {BW:.0f} x {BH:.0f} mm -> {OUT}")
