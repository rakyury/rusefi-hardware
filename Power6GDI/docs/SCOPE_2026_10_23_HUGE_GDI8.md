# Current scope: Huge-derived GDI8 ECU

The user's 23 October review supersedes the GDI6 PDF channel counts. The current
target is 8 onboard GDI channels, 2 HPFP valve channels, 8 high-impedance PI
channels, and 8 ignition channels that can operate the selected stock BMW G42
M240i/B58 coils. A generic B58 label is not an electrical coil specification;
passive-coil and active-coil variants must not be connected interchangeably.

The user explicitly confirmed **four motor H-bridges**, including two spares,
after the channel reductions. SENT, LIN, and two onboard wideband controllers
remain in scope. There are **zero onboard EGT channels**; EGT moves to a separate
module to simplify wiring. CAN is the proposed connection to that module;
no particular EGT protocol or compatibility is claimed yet.

Keep the existing 24 low-side outputs (8 PI + 4 VVT + 8 AUX PWM + 4 service).
Do not expand to 12 PI, 12 ignition, or 28 low-side outputs from the superseded
PDF proposal. Huge is the reference for circuit capability and reuse, not an
instruction to copy every optional feature. Retained reference input features
still require resource/connector review.

The machine-readable target is `hardware/target_profile.json`. Load currents,
GDI boost/profile, ignition dwell, thermal ratings and physical qualification
remain open until supported by component information and measurements.

## Active engineering sequence

1. Ignition: verify G42 coil family, implement appropriate eight-channel stage.
2. GDI: protected bank feeds, two pump commands, hardware permission gates.
3. WBO: replace unfinished CJ125 candidate with traced Hellen WBO architecture.
4. Integration: four motor bridges, LIN commander options, power/resource budget.
5. PCB: rebuild from the actual final netlist, preserve reviewed power loops,
   route remaining nets and repair root causes of ERC/DRC findings.
6. Independent QA: netlist-to-board coverage, electrical defaults, pin mapping,
   actual full DRC and explicit unresolved physical-test gates.

Three specialist agents are active initially, each in a dedicated worktree.
Dependent power/PCB/QA assignments will reuse available worker slots. Firmware,
map and configurator work is unchanged in this schematic/PCB revision.

The checkpoint before this revision is commit `647a4c0`. Earlier PCB reports do
not describe the updated circuit; new reports must identify their input hashes.
