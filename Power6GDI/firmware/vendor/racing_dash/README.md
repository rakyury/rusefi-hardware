# Pinned RacingDash native sources

These six files are unchanged Git-blob copies from RacingDash commit
`2c66c178083ae4bd0f2f0afe928ecd799af6347c`. See `PROVENANCE.json` for source
paths, Git object IDs and normalized SHA-256 hashes. No source in the original
checkout was changed.

The ECU-specific admission wrapper is outside this directory, in
`../../runtime/racing_dash_guard.*`. Do not edit vendor code silently: update
the pin/provenance and rerun compatibility tests when changing upstream.

These are host-tested building blocks. The native API alone does not enforce
the ECU admission, validity or actuator ownership contract. Full integration
status and remaining work are described in
`../../../docs/FW_RACINGDASH_REUSE_2026_10_25.md`.

No top-level upstream license was identified. This import records provenance
without inventing or changing source licensing; the repository owner must
resolve release licensing before external distribution.
