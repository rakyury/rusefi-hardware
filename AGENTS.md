# Codex instructions for the Power8GDI fork

This repository is a fork of rusEFI hardware. **Do not modify original upstream board designs** as part of the Power8GDI project unless a separately reviewed, explicit change is needed.

When a task refers to Power8GDI:
1. Read `Power8GDI/AGENTS.md` and `Power8GDI/workstreams/ROADMAP.md`.
2. Use `Power8GDI/CODEX_START.md` as the canonical execution specification and the scoped workstreams `Power8GDI/workstreams/HW-01.md`, `GDI-02.md`, `FW-03.md`, `MAP-04.md`, `UI-05.md`, `CAD-06.md`, `QA-07.md`, `INT-08.md`.
3. Work on branches based on `power8gdi-rev-a`, preserve existing files and push reviewable commits/PRs. Never overwrite source designs without approval.
4. Eight worker roles exist. If parallel/subagent creation is available, delegate seven independent specialist workstreams to non-overlapping workers and retain an integration lead. If it is not available, explicitly report the unavailable capability, then complete independent tasks in order.
5. Treat this as an automotive high-energy safety-critical system: do not assert production, engine, thermal, EMC or fault-tolerance qualification without real measurements and test artifacts. KiCad ERC/DRC and simulation alone do not constitute hardware certification.
6. Do not ask the user repeated scoping questions; capture unresolved design decisions in a blocker register and proceed with conservative, reversible engineering defaults where possible.

The separate desktop client lives under `Power8GDI/configurator/` until moved into a dedicated repository in a reviewed PR.
