# Power6GDI common rules

Active user scope as of 2026-10-25 is the strict six-cylinder hardware redesign:
read `docs/SCOPE_2026_10_25_SPORT_GDI6.md` before numerical channel assumptions.
The project and its directory were renamed from Power8GDI to Power6GDI on 2026-11-05; KiCad library, sheet and file identifiers still carry the historical `Power8GDI_` prefix until the schematic set is regenerated.
Continue the existing PyQt6 client; reuse the user's Racing Dash VM and CAN
implementation as requested, with revision provenance and validation.
The analysis package is `docs/research/2026-10-25-sport-ecu/README_RU.md`.

Safety-critical high-energy automotive ECU. Work on `power8gdi-rev-a` or feature branches derived from it. Do not rewrite rusEFI/Proteus/GDI4 upstream sources. Verify manufacturer datasheets, component variants, MCU AF/DMA/GPIO, actual TE connector footprints and STEP. Explicitly distinguish conceptual floorplan from routed PCB and offline demo firmware from hardware-tested ECU. No manufacturing/engine ready claim without ERC/DRC, real circuit measurements, thermal/EMC and fault injection signoff. 4D = 3 input axes plus scalar output; [Z][Y][X] storage. Python configurator based on rakyury/racing_dash architecture, not its proprietary assets. Do not modify another specialist's owned files without coordination. GitHub Issues are disabled, so workstreams Markdown briefs serve as task tracker.
