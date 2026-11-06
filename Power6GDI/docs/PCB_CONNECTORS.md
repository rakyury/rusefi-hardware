# TE34 connector evidence and boundary

This is an engineering candidate, not a released footprint or harness design.
Exact source links, revisions and downloaded byte hashes are in
`hardware/design/board/source_provenance.json`.

The selected candidate is TE **6437288-1**, SUPERSEAL1.0,34positions, upper lock,
key1, right-angle through-hole header, mating with **4-1437290-0**. Key2 uses
6437288-2 and4-1437290-1. Four copies of key1 are provisionally placed; labels
alone do not prevent cross-mating. The original two-row conceptual connector
envelope is not the real TE land pattern and must not be used for board fit.

## Manufacturer dimensions

TE customer drawing **C-9-1437287-8 RevA1, sheet2/3**, recommended PWB pattern,
is viewed from the component side. With origin between the mounting holes and
the mating face toward+Y, dimensions in millimetres are:

| Row | Pins left to right | X positions | Y |
|---|---|---|---|
| Rear | 1..9 | -12,-9,-6,-3,0,3,6,9,12 | -14.5 |
| Second | 10..17 | -10.5,-7.5,-4.5,-1.5,1.5,4.5,7.5,10.5 | -12 |
| Third | 18..25 | same as second | -9 |
| Front | 26..34 | same as rear | -6.5 |

Signal drill1.3mm, drawing tolerance+0.2/-0. Mounting holes3.3±0.1mm at
X±19.25,Y0 (38.5mm centres). Horizontal pitch3mm; inner rows offset1.5mm.
Row separations2.5/3/2.5mm. Overall flange width45.5mm reference; depth36.5mm.
The selected2.2mm copper land diameter is an engineering choice (0.45mm nominal
annulus), **not** a TE copper-pad prescription. Actual finished-hole plating,
solder process and land dimensions require fabrication review.

Numbering comes from the rear/wire-side view of mating housing4-1437290-0 on
TE **C-2-1437285-3 RevP, sheet3/4**. This view looks in the same direction as
the header mating-face view. The header front/top orthographic projections
preserveX, and sectionA-A bends pins inY/Z without crossingX; upper contacts
bend to the farthest rear row. This projection was independently reviewed by
the integration lead. A physical pin1/cavity1 continuity check and independent
footprint signoff remain mandatory before fabrication. A temporary mirrored
interpretation was corrected before this checkpoint.

The mounting note calls for JISB1122 cross-recessed pan-head tapping screws,
zinc-plated type2,3×L withL=6.5+board thickness. It does not specify anM3 tapped
housing thread. Housing/PCB-edge/fastener interference is not yet qualified.

## Harness versus logic

`board/connectors.kicad_sch` containsJ601..604 and136real electrical pins. The
CSV remains the functional request; unsupported physical circuits receive
`HARNESS_` net names. This prevents a same-named MCU GPIO such asIGN1 from
being silently wired to a vehicle harness output. `connector_aliases.csv`
explicitly joins only reviewed interfaces. IGN outputs join the buffered
MIC4427 candidate **after DNP series links**, not the raw MCU nets.

OnlyVBAT_MAIN_1 joinsVBAT_MAIN_FUSED; onlyPGND_MAIN_1 joinsGND. Other mainfeeds
and grounds remain independent pending current sharing/ground-tree design.
GDI high/low aliases remain blocked: referenceH1/H2 andH3/H4 are shared highside
banks, not four independent high outputs. Injector/pump pair mapping needs
microcode, load and loom review. No blanket per-contact current rating is
assumed from a reseller description.

## References not transferable

The repository `superseal-igbt` design embeds a **26position6473423-1** footprint;
it is not the34position part. Proteus AMPSEAL23/35 and other Hellen connectors
also cannot establish this footprint. None of those upstream designs is edited.
The actual TE STEP model RevC is available in local build/reference evidence;
model-to-footprint alignment, enclosure fit and contact numbering still need
verification. It is not attached with an invented transform.
