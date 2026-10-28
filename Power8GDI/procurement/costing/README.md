# GDI6 cost model

This directory owns pricing and cost planning, not electrical part approval.
The selection source is `../selection/bom_selection.json`. No procurement action
is performed by any script here.

Files:

- `catalog_additions*.json`: exact catalog offers, with observation date, cache age,
  source URL, packaging, price breaks, MOQ/multiple where published, and reported
  stock. Dates in filenames do not refresh older observations.
- `../price_evidence_2026_10_25.json`: inherited price evidence. Its old fitted
  quantities are deliberately ignored; only exact orderable part offers are read.
- `process_evidence.json`: observed blank-PCB calculator outputs and published
  assembly/consignment tariffs. These are not an accepted turnkey quote.
- `estimate_inputs.json`: physical land counts, explicit engineering allowances,
  attrition assumptions, exclusions and the estimate date.
- `selection_snapshot.json`: compact, reproducible selection input plus SHA256 of
  the full selection file. It is a pricing snapshot, not another selection source.
- `costed_bom.json` and `.csv`: per-purchase-group planned quantities and costs for
  one and ten boards. Repeated exact MPNs are combined before quantity discounts.
- `estimate_summary.json`: line items and low/base/high order budgets. Each value
  has an evidence type and formula. All amounts are USD; no currency conversion.
- `../../docs/COST_GDI6_ESTIMATE.md`: generated Russian report.

Rebuild with the final selection and then test:

```text
python Power8GDI/procurement/costing/build_estimate.py --selection Power8GDI/procurement/selection/bom_selection.json
python -m unittest discover -s Power8GDI/procurement/costing -p test_estimate.py -v
```

Omit `--selection` to reproduce the checked-in snapshot. The script works from any
working directory. It writes only this directory and the COST report.

## Important data distinctions

`price_status=CATALOG_PRICE` means that an exact-MPN published price exists, even
when the cited supplier has zero stock. It does not mean available or qualified.
For `NO_PRICE` / `NO_MPN_OR_PRICE`, `unit_price_usd` and `catalog_subtotal_usd` are
null. Their separately named `allowance_*` values are engineering budgets and have
no invented price-source URLs. Supplier MOQ is also null if unverified.

`purchase_qty` includes planned attrition, MOQ rounding and economical buy-up.
`unused_inventory_before_attrition_qty` is purchase minus fitted quantity, not a
guaranteed recoverable spare stock. Its value is already included in procurement
cash outlay and must not be added a second time. The two scenarios are independent
orders; inventory from one scenario is not silently reused in the other.

`repeat_batch_without_fixture_nre` subtracts only first-project test-fixture NRE.
It is not a complete inventory-aware repeat-order model. Taxes/duties/brokerage
remain unknown/excluded; they are not assumed zero. The upper planning scenario
is not a guaranteed cap when unknown delivery MOQ or specification changes remain.

Before replacing the snapshot, compare its counts and MPNs with the final hardware
BOM. Land-count provenance is separate from selection provenance because package
changes can alter the PCB independently. Re-run the physical land extractor when
that happens, then update `estimate_inputs.json` with the new source hash/count.
