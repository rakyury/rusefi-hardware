# WBO input checkpoint — deferred for compact redesign

The main GDI6 chat relayed the user's explicit new decision: a compact PCB and
enclosure comparable to EMU PRO. Long-distance routing on the old 245 × 165 mm
floorplan was therefore stopped. This checkpoint preserves reusable work; it
does **not** integrate the candidate into the active PCB or its generator.

Active PCB remains commit `6a308e0f0f79400f8cb79df5cc634a757d96bdd5`, SHA-256
`638900cd40914d65b20f752ccf2698f53bb84e6ac96d56a0a211c24fb287576f`, with
2085 native unconnected items. No project rules, exclusions, placement, netlist,
BOM or pricing changed in this checkpoint.

## Preserved candidates and verification boundaries

- `route_wbo_ref_input.py`: U5603.1 to C5617.1, plus C5617.2 to the existing
  REF ground via at (168,79.0625). Two B.Cu 0.25 mm tracks. Native count
  2085 → 2083; full DRC has no findings on either new object; local DRC has
  the same 123 violation signatures before/after. All 4627 previous board
  objects, including zone fills, are unchanged. Four native tests passed.
- `route_wbo_input_feed.py`: 26 B.Cu tracks, no vias, connecting the actual
  LM76003 output capacitor bank C5211.1 (already connected to L5200.2) to
  C5661.1, PGFB U5604.6 and REF input U5603.1. Main branch is 91.902491 mm,
  0.5 mm wide; two branches are 0.25 mm. Copper/voltage-domain and hole
  preflight passed. Six native tests passed. **Full/scoped DRC of this long
  candidate was not completed before the floorplan freeze.**
- Combined candidate: 28 tracks, no vias, native count 2085 → 2080. Native
  track/pad traversal proves L5200.2 reaches Cin, IN1/2, EN3, PGFB6, REF1 and
  C5617.1. C5617.2 reaches a via connected to the In1 ground plane.
  This connectivity proof is not an electrical qualification or DRC pass.

The two modules are intentionally not called by `build_board.py`. Their guarded
coordinates apply only to this baseline; replan them after compact placement.
Exact route coordinates and baseline islands are stored beside this document.
The local combined PCB is retained in `output/gdi6_wbo_input_20261028/`.
The full native board test suite passed: 73 tests in 108.908 seconds; the
unabridged log includes the existing SWIG teardown warnings, with exit code 0.

## Still required

C5660.2 and R5660.2 require a quiet Kelvin return to Cout ground; R5660.1
also remains disconnected from SET. A B.Cu path that joins the existing EP
return early is not acceptable as a Kelvin return. A ground through-via would
join the plane early as well. Searches did not find an acceptable short path
in the current placement; relocate the SET components as part of the new
compact layout. Remaining WBO supply distribution also needs review.

No working-LDO, stable-loop, thermal, EMC, engine or manufacturing claim follows
from these checks. Relevant pin/layout contract: [ADI LT3042 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/lt3042.pdf),
OUT10, OUTS9; SET resistor/capacitor ground must reference the load ground.

## Compact placement handoff

Read-only screening identifies four J601–J604 connectors, each approximately
46.55 × 37.55 mm bounding box, as major constraints: four in a row occupy
186.2 mm before enclosure tolerances. Other large blocks include the MCU
(27.41 × 27.41 mm), two GDI inductors (17.65 × 20.65 mm), and eight large
electrolytics (16.55 × 16.55 mm bounding boxes). These are geometric screening
figures, not a packing proof or internal enclosure dimensions. Preserve the
6 DI, 6 PI, 2 HPFP scope while reviewing connector placement, power loops,
thermal paths and component distribution across sides/boards with enclosure CAD.

Exact large power references: L202/L302 (10 µH), L201/L301 (6.8 µH,
15.65 × 13.45 mm). C205/C206/C305/C306 are the 1300 µF / 50 V input-side
capacitors; C207/C209/C307/C309 are the 470 µF VBOOST capacitors. Do not
classify all eight as boost capacitors. MCU is U101 (STM32F767).
