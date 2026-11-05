# WBO regulator-to-MCU feed and Kelvin repair — 2026-10-28

Baseline: `9c013c8161191fdf2b0e532e693fe38bc08ace15`.
PCB SHA256: `aa587f27ac9df7b35d8866f7716df9e7f06637fb603a7da4a8d693ec9f6cb392`.

The regulator output island was disconnected from MCU VDD. Add a feed from C5662.1 to C5612.1 and the previously connected U5602.1. Correct the local OUTS shortcut at the same time. [ADI LT3042 RevC pp13–15](https://www.analog.com/media/en/technical-documentation/data-sheets/lt3042.pdf) identifies **OUT pin10 / OUTS pin9**, requires sensing at the output capacitor, and specifies at least4.7uF effective output capacitance with ESR/ESL limits. Initial coordination accidentally reversed the pin numbers; manufacturer verification corrected them before any source/PCB changes. Existing netlist assigns both to WBO1_3V3 and is unchanged.

## Physical topology

Existing OUT10→C5662.1 power track remains. Remove only the0.5mm shortcut OUTS9→OUT10 (UUID356b15fb-c05f-4989-8f07-b7abc7518ed0). Replace it with a separate0.20mm B.Cu sense path to C5662.1. The generator verifies polygon overlap at1nm conservative accuracy: sense and all relevant power copper meet only within the Cout pad. All same-net B.Cu pads except OUTS/Cout are included in this check.

Power feed:12 B.Cu segments0.40mm, length25.441809mm, one via0.65/0.30mm at(177.10295,68.975), then one F.Cu segment0.25mm/2.5mm to C5612.1. Sense:3 B.Cu segments0.20mm, length3.817691mm. Total16tracks+1via added,1shortcut removed. Coordinates, widths, UUIDs and removed signature are in routes.json. Source guards accept exactly one original shortcut by geometry, allowing reproducible rebuild UUIDs, and reject altered/duplicate/partial paths before mutation.

Declared outer copper is70um. A nominal20C trace-only calculation gives approximately23.1mOhm from OUT10 through the existing output-cap connection, new feed and existing capacitor-to-MCU link: about4.62mV at the LDO's200mA rating envelope. Via/solder resistance and thermal/transient performance are excluded; this is not a measured current budget or hardware qualification. See trace_drop_estimate.json.

## Validation

Pinned native KiCad9.0.9 image sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729.

- Complete native connectivity **2088→2087**. Native OUT10→VDD connectivity holds after removing sense tracks and disconnecting OUTS on a disposable copy; OUTS→Cout also independently connects.
- Full DRC: no findings on17newUUIDs. Reported clearance504/width199 are capped samples; inherited dangling via14/track4 remain. No silk/library mismatch findings.
- Full-obstacle scoped x157..184/y62..93 before/after has identical123violation signatures, no new signatures. Native command/hash reports are included.
- Root structured full-board comparison permits only the exact old shortcut removal,17additions and one GND filled-polygon change. All other old objects, pads, footprints, nets and zone settings remain unchanged.
- In1 GND loses1.046481mm2 locally around the supply via; remote polygon arithmetic changes are below0.000001mm2. All other zone fills remain identical. See zone_delta.json; this is not an unchanged-fill claim.
- The initial full suite exposed detached-object lifetime errors in the new KiCad test fixture. Keeping boards and detached/planned SWIG objects alive fixes the fixture; no assertions or PCB geometry were relaxed.
- **57native board tests +18strict costing tests PASS**. Pad/net audit1092positions/3464assignments/zeroerrors;20shuntpaste apertures preserved.22artifact hashes verified. Financial JSON/BOM/netlist/schematic unchanged, only costing PCB hash updated.

The regulator's Cout/Cset ground returns and remaining input/distribution connections are still incomplete. This commit proves the requested OUT-to-MCU feed and separate sense topology, not a functioning or stable regulator. C5662 effective capacitance/ESR/ESL and hardware load/transient/thermal tests remain release gates. The PCB still has2087unconnected items and inherited DRC/ERC findings; manufacturing release remains blocked. Main GDI6 chat owns PDF/Excel delivery updates after integration.
