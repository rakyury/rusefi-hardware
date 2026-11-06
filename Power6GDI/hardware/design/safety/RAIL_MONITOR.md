# Independent 5 V undervoltage inhibit

U806 (TPS3808G01QDBVRQ1) runs from 3.3 V and senses 5 V through
R807=102k / R808=9.76k. Its open-drain RESET joins SAFETY_FAULT_N,
clearing U804 through U803 even while 3.3 V is held by capacitance.
Power-good sequencing alone did not provide that path.

Basis: [TI SBVS085J](https://www.ti.com/lit/gpn/TPS3808-Q1), sections 6,
7.3–7.6 and 8.3. SENSE must remain within VDD during normal operation;
the divided input avoids directly applying 5 V to a 3.3 V-powered supervisor.
The 0.405 V threshold has ±2% limits. Resistors include 0.1% tolerance and
25ppm/°C over a 100°C excursion; input current is budgeted at ±25nA.
Calculated falling bounds are 4.513–4.763 V. Maximum release including 3%
hysteresis is 4.906 V, below the calculated static 5 V minimum of 4.921 V.

C808=1nF gives approximately 8.91µs nominal filter time constant. CT is open:
release delay is 12–28ms. C807=100nF decouples U806. A new ARM edge is still
required after recovery. Static threshold margins are narrow: board noise,
fast collapse, loading and partial-power behavior need measurements. This
circuit does not guarantee an arbitrary fast transient is intercepted before
a driver's supply leaves its operating range. All other hardware inhibit,
UVLO and coil-current protections remain necessary.

## Positive permission output fanout after WBO inhibit correction

The actual root network contains six 100R + 10k LS enable branches, four
1k + 10k protected-feed enable branches, and R806=10k to ground. These draw
approximately 3.60mA at 3.408V before input currents. The two WBO NPN base
branches add approximately 1.1mA, plus component tolerance and leakage.
[TI SCES563C](https://www.ti.com/lit/ds/symlink/sn74lvc2g74-q1.pdf) specifies
U804 output drive at VCC=3V, including VOH>=2.4V at16mA. The static resistor
and base loads therefore leave current margin; input thresholds, total input
currents and transition/capacitance limits must still be checked. This is not
a measured partial-power or edge-timing result.
