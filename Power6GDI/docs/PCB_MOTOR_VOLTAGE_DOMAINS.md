# Motor and protected-battery voltage domains

`audit_battery_voltage_domains.py` discovers 44 exact nets from actual root XML pins, covering the four TLE9201 bridges and four LM74800 controllers (motor and GDI input protection). Renaming a net does not remove its classification. Changed device identities, pin functions or connected floating exposed pads fail the audit.

For LM74800, A/VSNS/SW, VS/C/OUT, DGATE/HGATE and CAP belong to battery or floating battery-referenced circuits. SW is the undivided switched VSNS feed before the OV ladder. CAP and gate drive limits are relative to VS/A/OUT, so a small gate-source voltage does not make those nets logic-level relative to ground. The isolated exposed-pad net remains electrically unconnected and receives the same physical obstacle target. See [TI LM7480-Q1](https://www.ti.com/lit/ds/symlink/lm7480-q1.pdf), Rev C Tables 6-1/7-1 and section 9.3.

For each TLE9201, VS pin 4 and OUT1/OUT2 pins 5/7 are power-domain nets. Logic VSO pin 2 is distinct and remains in the regulated-logic class. DIR/PWM/DIS/SPI are not pulled into the power class. See [Infineon TLE9201SG](https://www.infineon.com/dgdl/Infineon-TLE9201SG-DS-v01_00-en.pdf?fileId=db3a304345087709014518190f481cec), sections 2 and 4.

These nets receive the existing provisional battery clearance target of 0.3 mm in placement, explicit DRC rules and protected routing classes. This is a classification correction, not proof of transient, creepage or insulation qualification. It introduces no package or track exceptions; intrinsic pad gaps may therefore expose further open DRC findings. OV/EN divider nodes and all possible fault-derived potentials are outside this limited discovery. Full hardware qualification remains open.
