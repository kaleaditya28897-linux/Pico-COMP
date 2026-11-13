#!/bin/sh
# Production outputs for both boards: Gerbers, drill, pick-and-place, BOM, IPC-356, ODB++,
# schematic PDF, assembly drawings and STEP, zipped per board in hardware/fab/.
# Refuses to export a board unless ERC has no errors and DRC (with schematic parity) is clean.
# Run: sh hardware/kicad/fab.sh [mainboard] [keyboard]   (default: both)
set -e
cd "$(dirname "$0")"
OUT=../fab
mkdir -p "$OUT"
LAYERS6="F.Cu,In1.Cu,In2.Cu,In3.Cu,In4.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"
LAYERS2="F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"

for b in ${@:-mainboard keyboard}; do
  d="$OUT/$b"
  rm -rf "$d"; mkdir -p "$d/gerber" "$d/assembly" "$d/reports"
  kicad-cli sch erc --severity-error --exit-code-violations -o "$d/reports/erc.rpt" $b.kicad_sch >/dev/null \
    || { echo "$b: ERC errors, see $d/reports/erc.rpt"; exit 1; }
  kicad-cli pcb drc --schematic-parity --refill-zones --severity-error --severity-warning --exit-code-violations \
    -o "$d/reports/drc.rpt" $b.kicad_pcb >/dev/null \
    || { echo "$b: DRC violations, see $d/reports/drc.rpt"; exit 1; }
  if [ $b = mainboard ]; then L=$LAYERS6; else L=$LAYERS2; fi
  kicad-cli pcb export gerbers --layers "$L" --subtract-soldermask --use-drill-file-origin -o "$d/gerber/" $b.kicad_pcb >/dev/null
  kicad-cli pcb export drill --format excellon --excellon-separate-th --generate-map --map-format pdf \
    --drill-origin plot -o "$d/gerber/" $b.kicad_pcb >/dev/null
  kicad-cli pcb export pos --format csv --units mm --side both --exclude-fp-th -o "$d/assembly/$b-cpl.csv" $b.kicad_pcb >/dev/null
  kicad-cli pcb export pos --format csv --units mm --side both -o "$d/assembly/$b-cpl-incl-tht.csv" $b.kicad_pcb >/dev/null
  kicad-cli sch export bom --fields 'Reference,Value,Footprint,MPN,Spec,${QUANTITY}' \
    --labels 'Designators,Value,Footprint,MPN,Spec,Qty' --group-by 'Value,Footprint,MPN,Spec' \
    --exclude-dnp -o "$d/assembly/$b-bom.csv" $b.kicad_sch >/dev/null
  kicad-cli pcb export ipc2581 -o "$d/$b-ipc2581.xml" $b.kicad_pcb >/dev/null 2>&1 || true
  kicad-cli pcb export ipcd356 -o "$d/gerber/$b-netlist.ipc" $b.kicad_pcb >/dev/null
  kicad-cli pcb export odb -o "$d/$b-odb.zip" $b.kicad_pcb >/dev/null 2>&1 || true
  kicad-cli sch export pdf -o "$d/$b-schematic.pdf" $b.kicad_sch >/dev/null
  kicad-cli pcb export pdf --layers "F.Fab,Edge.Cuts" --mode-single -o "$d/assembly/$b-assembly-top.pdf" $b.kicad_pcb >/dev/null
  kicad-cli pcb export pdf --layers "B.Fab,Edge.Cuts" --mode-single --mirror -o "$d/assembly/$b-assembly-bottom.pdf" $b.kicad_pcb >/dev/null
  kicad-cli pcb export step --subst-models --force -o "$d/$b.step" $b.kicad_pcb >/dev/null
  kicad-cli pcb export step --subst-models --force -o $b.step $b.kicad_pcb >/dev/null
  (cd "$d" && rm -f ../$b-gerbers.zip && zip -qr ../$b-gerbers.zip gerber)
  echo "$b: outputs in hardware/fab/$b, Gerber zip hardware/fab/$b-gerbers.zip"
done
