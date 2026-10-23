# Passive ignition interface: insulation review

The existing four TE34 connectors remain the engineering candidate. No shared
pinout or connector substitution is made by the layout workstream. Comparing
250V working voltage with420V ignition peak alone does **not** establish either
failure or suitability. A one-minute dielectric test is also not a repetitive
ignition endurance rating.

TE's primary [6437288-1 product page](https://www.te.com/en/product-6437288-1.html)
links directly to [108-78140 RevA9](https://www.te.com/commerce/DocumentDelivery/DDEController?Action=srchrtrv&DocFormat=pdf&DocLang=English&DocNm=108-78140&DocType=Specification+Or+Standard&PartCntxt=6437288-1).
Sections3.3,3.5.6 and3.5.7 specify250VAC/DC working rating, insulation resistance
at500VDC, and a mated-contact dielectric test of1000VAC or1600VDC for one minute.
The last test covers neighboring contacts and contact-to-earth. Published current
ratings for wire>=0.85mm² are7/6/5/3A with all contacts loaded at ambient
<=60/80/100/125°C; a single contact has15/13/11/6A respectively.

No explicit repetitive420V ignition pulse lifetime envelope was found in that
specification. Consequently retain the candidate, require manufacturer evidence
or application-level pulse/environment qualification before release, and avoid
an unjustified extra connector just because the two voltage numbers differ.
If qualification fails, an alternate harness/connector becomes a concrete design
change; it is not resolved by silently renaming a net or leaving neighboring
cavities empty without checking every PCB land and terminal geometry.

Collector current must be reviewed using its real waveform and duty, shared
returns, adjacent loading, conductor size, terminal crimp and temperature. For
illustration only, a linear0..10A ramp lasting3ms at66.7Hz gives2.58A RMS;
a rectangular10A pulse with the same duty gives4.47A RMS. Neither example is a
qualified dwell waveform. Peak threshold and connector DC ratings are not a
complete thermal analysis. The single B34 ground contact must not carry the
entire bank return; the parent pinout provides multiple GND contacts but their
physical return paths and harness conductors still require explicit design.

## PCB isolation target and limitations

New HARNESS_IGN1..8 nets receive their own explicit preliminary rule:2.5mm
edge-to-edge copper clearance and1.5mm nominal trace width. This conservative
layout target is an engineering assumption for the420V clamp envelope, **not a
claim that a continuous-voltage IPC table is the governing automotive pulse
standard**. The actual required clearance/creepage depends on pulse waveform,
altitude, contamination, laminate, coating, manufacturing and lifetime criteria.
The width similarly requires current/thermal verification; it is not ampacity
certification.

The TE footprint's3mm pitch with2.2mm lands leaves0.8mm nominal between adjacent
same-row lands. D2PAK internal pin/land spacing also needs application review.
The blanket2.5mm target will intentionally expose these package/interface gaps
as DRC findings. Do not exclude them or reduce to the0.2mm logic rule simply to
obtain a clean report. Resolve the physical requirement with supplier evidence,
qualified coating/assembly process or a justified component/interface change.
The mated connector's dielectric test does not qualify exposed PCB solder lands.

No manufacturing approval, component rejection or engine qualification is inferred
from this preliminary clearance rule. The retained GDI donor copper has a separate
audited net map and provisional0.6mm rule; ignition is not assigned that rule.
