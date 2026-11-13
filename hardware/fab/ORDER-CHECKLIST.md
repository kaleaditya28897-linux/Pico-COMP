# Pico-COMP: what to order where (robu.in)

robu.in does PCB fab + assembly, metal laser cutting, 3D printing (resin, MJF, FDM, metal) and custom
Li-ion packs.

## Order now
| Service | Upload | Settings |
|---|---|---|
| PCB + assembly: main board | `hardware/fab/mainboard-gerbers.zip` + `mainboard/assembly/*-bom.csv`, `*-cpl.csv` | see `mainboard/ORDER.md` (6 layers, ENIG, filled + capped via-in-pad, turnkey) |
| PCB: keyboard | `hardware/fab/keyboard-gerbers.zip` (+ `keyboard/assembly/*-bom.csv`, `*-cpl.csv` if assembled) | see `keyboard/ORDER.md` |
| Metal laser cut: switch plate | `hardware/fab/keyboard/keyboard-plate.dxf` | 1.2 mm aluminium (black anodised optional) |
| 3D print: keycaps | `hardware/mechanical/keycaps/*.stl` (75 caps, not `*_legend`) | SLA resin; paint-fill the debossed legends. Test one Shift cap (stabilizer pegs) first |
| Battery pack | spec below | 2S2P 18650 |

### Battery pack spec
2S2P, 4x 18650 Li-ion (NMC), branded and matched, 3000 mAh each; 7.4 V nominal (8.4 V full / 6.0 V
cut-off), 44 Wh. Balancing BMS with over/under-voltage, over-current (trip ~6 A), short-circuit and
10k NTC protection. 2 A continuous / 4 A peak. XT30 female lead 100 mm 18 AWG; JST-PH 2-pin NTC lead.
Cells side by side in one flat layer, max 80 x 78 x 20 mm including BMS. **Ask for the final pack
dimensions.**

## Hold
- **Case prints** (`hardware/mechanical/print/`: base, deck, lid, lid_back): the base battery bay
  has ribs for loose cells. Change it to a pocket sized to the actual pack first. Measure the display
  before printing the lid. Recommended: MJF PA12 dyed black (or SLA tough resin).
- Small parts (switches, stabilizer kits, headers, jumpers, screws): later.
