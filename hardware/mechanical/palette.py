"""Material palette shared by render_export.py (renders) and bake_colors.py (FreeCAD file colours)."""

# material -> (rgb, specular, shininess)
MAT = {
    "case": ((0.30, 0.31, 0.33), 0.20, 25), "deck": ((0.22, 0.23, 0.25), 0.15, 20),
    "plate": ((0.10, 0.10, 0.11), 0.30, 40), "steel": ((0.72, 0.73, 0.75), 0.80, 80),
    "cap": ((0.90, 0.88, 0.82), 0.25, 30), "capmod": ((0.55, 0.56, 0.58), 0.25, 30),
    "legend": ((0.15, 0.15, 0.16), 0.10, 10), "glass": ((0.03, 0.03, 0.04), 0.90, 120),
    "screen": ((0.06, 0.05, 0.03), 0.60, 90), "sticker": ((0.85, 0.82, 0.70), 0.10, 10),
    "pcb": ((0.06, 0.32, 0.14), 0.35, 40), "copper": ((0.80, 0.55, 0.30), 0.70, 60),
    "silk": ((0.95, 0.95, 0.95), 0.10, 10), "ic": ((0.09, 0.09, 0.10), 0.30, 40),
    "cap_smd": ((0.72, 0.60, 0.42), 0.20, 20), "metal": ((0.78, 0.78, 0.80), 0.80, 90),
    "switch": ((0.18, 0.18, 0.19), 0.25, 25), "cell": ((0.15, 0.33, 0.70), 0.40, 50),
    "rubber": ((0.06, 0.06, 0.06), 0.05, 5), "cable": ((0.08, 0.08, 0.09), 0.20, 20),
    "bms": ((0.10, 0.40, 0.18), 0.30, 30), "amber": ((1.0, 0.62, 0.12), 0.0, 1),
}
MODIFIERS = {"Esc", "Tab", "Ctrl", "Shift", "Alt", "Fn", "Enter", "Bksp", "Del", "Up", "Down", "Left", "Right"}
LID_OBJS = ("Lid", "LidBack", "DisplayPanel", "DisplayActiveArea", "HotkeySticker", "ScreenText")


def material(o, group):
    n, lab = o.Name, o.Label
    if group == "Case":
        return {"Base": "case", "Lid": "case", "Deck": "deck", "KeyPlate": "plate",
                "HingePin": "steel", "HotkeySticker": "sticker"}.get(n, "rubber" if n.startswith("Bumper") else "case")
    if group == "Display":
        return {"DisplayActiveArea": "screen", "ScreenText": "amber"}.get(n, "glass")
    if group == "Battery":
        return "bms" if n == "BMS" else "cell"
    if group == "Keycaps":
        if n.endswith("_legend"):
            return "legend"
        return "capmod" if lab.split()[1] in MODIFIERS else "cap"
    if group == "Fasteners":
        return "rubber" if n.startswith("Foot") else "steel"
    if group == "Cables":
        return "cable"
    if group in ("Mainboard", "Keyboard"):
        if n.endswith("_copper"):
            return "copper"
        if n.endswith("_silkscreen"):
            return "silk"
        if n.endswith("_soldermask") or n in ("MainPCB", "KeyboardPCB"):
            return "pcb"
        ref = lab.split()[0]
        if ref.startswith("C"):
            return "cap_smd"
        if ref.startswith("SW") and group == "Keyboard":
            return "switch"
        if ref.startswith("ST"):
            return "switch"
        if ref in ("J1", "J6", "J9") and group == "Mainboard":
            return "metal"
        if ref.startswith("U8"):
            return "metal"
        return "ic"
    return "case"
