# D5604 custom footprint — independent parsed delta review

Read-only comparison on 2026-10-28 of root worktree candidate against
`98208688a45204fe52cf7921d42b3367e5539ce5`. No shared files changed.

**Result: scoped change confirmed.** This supersedes the earlier proposed
tiny-segment transfer to Fab: both edited strokes remain on B.SilkS.

Candidate PCB SHA256:
`0ab109350b42bd0286b5aaaa88ac83b4ddd04a17f6802320568667b6ebe970c4`.
The checked-in-path candidate and
`output/gdi6_d5604_20261028/Power8GDI_Review.kicad_pcb` are byte-identical.

Parsed S-expression comparison found changes only inside D5604. Its FPID is
now `Power8GDI_Board:SOT-23_D5604_J5600_Clearance`. Ordering of several graphic
nodes changed during save; comparing by UUID proves only these objects changed:

- `978c2cab-ac72-476d-b19a-12a3efedb6cd`: tiny stroke moved to the shortened
  outline endpoint; both x coordinates changed from -0.76 to +0.32 locally.
- `ff66319e-48d5-4711-b40a-848a9af9af5b`: top stroke endpoint shortened,
  x=-0.76 to +0.32 locally.

All footprint object UUID sets are retained. The D5604 pin-1 polygon
`15023252-879b-4440-a82c-14ebdc76fd29` is exactly identical as a parsed object.
All pad objects across the PCB are exactly identical, including copper,
mask/paste layer membership and pad attributes. The 2359 segments, 295 vias,
16 zones and 800 board net definitions are exactly identical as parsed lists.
Every board object outside D5604 is unchanged.

Custom library comparison against
`output/gdi6_d5604_20261028/SOT-23.source.kicad_mod` found only the footprint
name and the three x-coordinate scalar edits in the two silk lines above.
All other library nodes, including pads, mask/paste and marker, are identical.
Custom library SHA256:
`20779c9f31f36b07777cc272acaf79dfd5a828ee9ce7ad0ee3ce65dd3855366d`.

`core.net` SHA256 at review:
`abd9c0533019b9811a75fa73c46c1a9d9b97511d5f858edb2b88ae1e98a87462`.
Parsed XML comparison found exactly four text changes:

1. Generation date.
2. D5604 component `footprint`.
3. D5604 component `fields/field[@name='Footprint']`.
4. The corresponding `Power8GDI_WBO:WBO_D604_mapped` libpart Footprint field.

That libpart is referenced only by D5604. These are the expected three XML
representations of the one footprint change, not separate component changes.
The entire `nets` subtree is identical. All 1092 component MPN fields are
identical; every component except D5604 is wholly identical as parsed XML.
No connectivity, value, pin or order-code delta was found.

Method: `git show 9820868:<path>` supplied baseline data; committed `sexpr`
parser and Python ElementTree parsed strings without saving files. Python
bytecode generation was disabled. This review did not run native DRC; the
integrator owns that independent result and subsequent provenance updates.
