# Pico-COMP Architecture

## Two-MCU split
| MCU | Role |
|-----|------|
| **MCU1 – "UI"** (RP2350) | DVI/HSTX display, text UI, all apps (editor, spreadsheet, DB, scheduler, todo, games, BASIC), printer/IO (USB host, SD, serial), beeper |
| **MCU2 – "NET"** (RP2350) | Wi-Fi/networking (email, IM, sync web page, SSH, Gemini...), power management (charging, gauge, sleep), keyboard matrix scan |

MCU1 and MCU2 talk over a UART link (framed packets, see `firmware/common/link.h`). MCU2 owns the keyboard and forwards key events to MCU1; MCU2 also gates power to MCU1 for standby.

## Open decisions / design choices
- CPU architecture: all RISC-V (Hazard3) on both RP2350s; ARM cores unused.
- Wi-Fi: Raspberry Pi RM2 module (CYW43439, onboard antenna, gSPI over PIO) on the NET MCU, wired like the Pico 2 W except the clock on GPIO26. It sits at the main board's front edge under the plastic palm rest; RF keep-outs on both PCBs.
- Display: 7" IPS HDMI LCD, 1024x600 (~1.7:1 active area; the 1.27:1 vendor figure is the module including its driver board), 164.9 x 124.27 mm, 380 g, 220 cd/m2, capacitive touch (USB; unused, leave unconnected), manual backlight switch, visible area 154.08 x 85.92 mm (listing; resellers also quote a generic 6-7 W rating, so budget up to ~3.5 W until measured). Vendor spec: **0.62 A @ 5 V = 3.1 W**, recommends a 5 V / 3 A supply. The full-size keyboard is kept, so the case stays 250 x 140 mm with larger bezels. (A vendor Raspberry Pi image for the related 10.1" Waveshare model used `hdmi_cvt 1024 600 60 6 0 0 0`; confirm the 7" board accepts the same timing.)
- Video: HSTX cannot generate 1024x600 (~510 Mbps per TMDS lane), so UI outputs **720x400 DVI** (80x25 text with a 9x16 font, closest to the panel's aspect ratio, ~283 MHz HSTX clock, needs a modest overclock/voltage) with **640x480** (80x30 with 8x16, 252 MHz, a standard Pico DVI mode) as fallback; the panel's scaler fills the screen. Verify the board accepts these DVI timings (no audio).
- **Battery life:** display 3.1 W + MCUs/Wi-Fi ~1 W = ~4 W, so a 44 Wh pack (4x3000 mAh) gives roughly 10 h of continuous use; 4 days works for a few hours of use per day. Use the backlight switch, blank the screen aggressively, and rely on instant resume. Standby (display off) is achievable.
- Storage: SD card on MCU1 (SPI/SDIO); settings in flash.
- Power: custom **2S2P** pack, see `hardware-plan.md`.

## Layout
- `firmware/ui`, `firmware/net` – one Pico SDK target each; `firmware/common` shared protocol/keymap.
- `hardware/kicad` – KiCad projects (generated schematic + PCB per board); `hardware/mechanical` – FreeCAD assembly, printable parts, keycaps; `hardware/placement.py` – where the boards sit in the case.
- GPIO map for both MCUs: `firmware/common/pins.h`.
