"""Reproducible planning estimate; no supplier API calls, carts or procurement actions.

Run from any cwd. --selection accepts the selection agent's final JSON; the compact
snapshot retained here is enough to rebuild without a sibling worktree.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def money(value):
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def tier_price(tiers, quantity):
    eligible = [(int(q), Decimal(str(p))) for q, p in tiers if int(q) <= quantity]
    if not eligible:
        raise ValueError(f"Quantity {quantity} below first published price break")
    return max(eligible, key=lambda t: t[0])


def purchase(required, offer):
    """Smallest cash outlay among requirement/MOQ and higher published breaks.

    Stock is reported separately: a backorder catalog price is not an available kit.
    Do not optimize across other MPNs, packaging types or manufacturers.
    """
    if required <= 0:
        raise ValueError("Required purchase must be positive")
    tiers = offer["tiers"]
    minimum = max(int(offer.get("minimum_order_quantity", 1)), int(tiers[0][0]))
    multiple = int(offer.get("order_multiple", 1))
    if multiple < 1:
        raise ValueError("Order multiple must be positive")
    rounded = lambda n: math.ceil(max(n, minimum) / multiple) * multiple
    minimum_needed = rounded(required)
    candidates = {minimum_needed} | {rounded(q) for q, _ in tiers if q >= minimum_needed}
    choices = []
    for q in candidates:
        breakpoint, price = tier_price(tiers, q)
        choices.append((price * q, q, breakpoint, price))
    cost, q, breakpoint, price = min(choices)
    stock = offer.get("stock_units")
    return {
        "purchase_qty": q,
        "minimum_order_quantity": minimum,
        "order_multiple": multiple,
        "applied_price_break": breakpoint,
        "unit_price_usd": float(price),
        "catalog_subtotal_usd": money(cost),
        "buy_up_qty": q - minimum_needed,
        "moq_rounding_qty": minimum_needed - required,
        "stock_covers_purchase": None if stock is None else stock >= q,
    }


def load_catalog():
    catalog = {}
    baseline = read(PROJECT / "procurement/price_evidence_2026_10_25.json")
    for p in baseline["components"]:
        if not p.get("listed_unit_price_breaks"):
            continue
        s = p["source"]
        offer = {
            "mpn": p["priced_orderable_mpn"], "supplier": s["supplier"],
            "url": s["url"], "observed_on": s["observed_on"],
            "evidence": s["evidence_kind"],
            "crawl_note": s.get("web_source_crawl_age_as_reported"),
            "stock_units": p.get("stock", {}).get("reported_units"),
            "packaging": p["packaging_used_for_price"],
            "tiers": [[t["minimum_quantity"], t["unit_price_usd"]] for t in p["listed_unit_price_breaks"]],
            "note": " ".join(p.get("caveats", [])),
            "currency": "USD",
        }
        catalog[offer["mpn"]] = offer
    for path in sorted(HERE.glob("catalog_additions*.json")):
        doc = read(path)
        if doc["currency"] != "USD":
            raise ValueError("Currency conversion is not part of this estimate")
        for p in doc["parts"]:
            offer = dict(p)
            offer.setdefault("observed_on", doc["observed_on"])
            offer.setdefault("currency", "USD")
            catalog[offer["mpn"]] = offer
    return catalog


def compact_selection(selection_path):
    raw = Path(selection_path).read_bytes()
    d = json.loads(raw.decode("utf-8-sig"))
    if d.get("is_costing_snapshot"):
        return d
    fields = ["reference", "selection_id", "orderable_mpn", "manufacturer", "package",
              "source_value", "assembly_class", "status", "qualification", "gaps", "source_urls"]
    return {
        "is_costing_snapshot": True,
        "source_path": "Power8GDI/procurement/selection/bom_selection.json",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_generated_date": d.get("generated_date"),
        "counts": d["counts"],
        "bom_snapshot": d["bom_snapshot"],
        "references": [{k: r.get(k) for k in fields} for r in d["references"]],
        "purchase_released": False,
    }


def group_selection(snapshot):
    grouped = defaultdict(list)
    seen = set()
    for r in snapshot["references"]:
        ref = r["reference"]
        if ref in seen:
            raise ValueError(f"Duplicate fitted reference {ref}")
        seen.add(ref)
        if r["assembly_class"] not in {"SURFACE_MOUNT", "THROUGH_HOLE"}:
            raise ValueError(f"Non-fitted assembly class in selection: {ref}")
        # Combine repeated exact MPNs across different electrical contexts so the
        # same purchase is not charged twice or denied a combined quantity break.
        key = (r["manufacturer"], r["orderable_mpn"]) if r["orderable_mpn"] else ("UNRESOLVED", r["selection_id"])
        grouped[key].append(r)
    if len(seen) != snapshot["counts"]["fitted_refs"]:
        raise ValueError("Fitted count mismatch")
    return sorted(grouped.values(), key=lambda rows: (rows[0]["orderable_mpn"] or "~" + rows[0]["selection_id"]))


def classify(rows):
    r = rows[0]
    ref = r["reference"]
    mpn = r["orderable_mpn"] or ""
    package = r["package"] or ""
    value = r["source_value"] or ""
    if ref.startswith("R"):
        if "WSLP" in mpn or "shunt" in value.lower() or "0R01" in value:
            return "resistor_shunt"
        if any(x in mpn for x in ("ERA-", "RNCF", "PNM", "TNPW")) or "0.1%" in value:
            return "resistor_precision"
        return "resistor_standard"
    if ref.startswith("C"):
        if "Elec" in package or "Radial" in package or "lowESR" in value:
            return "capacitor_electrolytic"
        if package in {"1206", "1210", "1812", "2220"}:
            return "capacitor_large_mlcc"
        return "capacitor_small"
    if ref.startswith("L"):
        return "inductor_power"
    if ref.startswith("D"):
        if "LED" in value.upper() or package in {"0603", "0805"}:
            return "led"
        return "diode_power" if any(x in package for x in ("TO-", "SMB", "SMC")) else "diode_signal"
    if ref.startswith("Q"):
        return "transistor"
    if ref.startswith("Y"):
        return "oscillator"
    if ref.startswith("J"):
        return "connector"
    if ref.startswith("U"):
        if mpn.startswith("LT3042"):
            return "ic_lt3042_automotive"
        return "ic_logic" if "74" in mpn or "LVC" in mpn else "ic_other"
    return "other"


def attrition(rows, boards, cfg):
    fitted = len(rows) * boards
    if all(r["assembly_class"] == "THROUGH_HOLE" for r in rows):
        policy = "tht"
    elif all(r["reference"].startswith(("R", "C")) and r["package"] in {"0402", "0603", "0805"} for r in rows):
        policy = "small_passives"
    else:
        policy = "other_smt"
    return max(cfg[f"{policy}_attrition_min_per_mpn"], math.ceil(fitted * cfg[f"{policy}_attrition_fraction"])), policy


def cost_bom(snapshot, inputs, catalog):
    groups = []
    for index, rows in enumerate(group_selection(snapshot), 1):
        first = rows[0]
        mpn = first["orderable_mpn"]
        offer = catalog.get(mpn)
        category = classify(rows)
        g = {
            "cost_group_id": f"COST-{index:03d}", "mpn": mpn,
            "manufacturer": first["manufacturer"],
            "selection_ids": sorted({r["selection_id"] for r in rows}),
            "refs": sorted(r["reference"] for r in rows),
            "quantity_per_board": len(rows),
            "packages": sorted({r["package"] for r in rows}),
            "values": sorted({r["source_value"] for r in rows}),
            "selection_statuses": sorted({r["status"] for r in rows}),
            "selection_gaps": sorted({gap for r in rows for gap in (r.get("gaps") or [])}),
            "assembly_classes": sorted({r["assembly_class"] for r in rows}),
            "allowance_category": category,
            "price_status": "CATALOG_PRICE" if offer else ("NO_PRICE" if mpn else "NO_MPN_OR_PRICE"),
            "source_url": offer["url"] if offer else None,
            "price_offer": offer,
            "batches": {},
        }
        for boards in (1, 10):
            fitted = len(rows) * boards
            extra, policy = attrition(rows, boards, inputs["assembly"])
            b = {"fitted_qty": fitted, "attrition_qty": extra, "attrition_policy": policy,
                 "minimum_required_with_attrition": fitted + extra}
            if offer:
                b.update(purchase(fitted + extra, offer))
                b.update({"allowance_low_usd": 0.0, "allowance_base_usd": 0.0, "allowance_high_usd": 0.0})
                b["fitted_value_at_purchase_price_usd"] = money(Decimal(str(b["unit_price_usd"])) * fitted)
                b["inventory_and_attrition_value_usd"] = money(Decimal(str(b["unit_price_usd"])) * (b["purchase_qty"] - fitted))
            else:
                b.update({"purchase_qty": fitted + extra, "minimum_order_quantity": None, "order_multiple": None,
                          "applied_price_break": None, "unit_price_usd": None, "catalog_subtotal_usd": None,
                          "buy_up_qty": 0, "moq_rounding_qty": 0, "stock_covers_purchase": None,
                          "fitted_value_at_purchase_price_usd": None, "inventory_and_attrition_value_usd": None})
                for label, unit in zip(("low", "base", "high"), inputs["allowance_unit_usd"][category]):
                    b[f"allowance_{label}_unit_usd"] = unit
                    b[f"allowance_{label}_usd"] = money(Decimal(str(unit)) * b["purchase_qty"])
            b["unused_inventory_before_attrition_qty"] = b["purchase_qty"] - fitted
            g["batches"][str(boards)] = b
        groups.append(g)
    return {
        "schema_version": 1, "generated_on": inputs["estimate_date"], "currency": "USD",
        "source_selection_sha256": snapshot["source_sha256"], "source_counts": snapshot["counts"],
        "price_observation_dates": sorted({g["price_offer"]["observed_on"] for g in groups if g["price_offer"]}),
        "purchase_released": False, "groups": groups,
        "coverage": {"purchase_groups": len(groups),
                     "catalog_priced_groups": sum(g["price_status"] == "CATALOG_PRICE" for g in groups),
                     "catalog_priced_fitted_refs": sum(g["quantity_per_board"] for g in groups if g["price_offer"]),
                     "allowance_groups": sum(g["price_offer"] is None for g in groups),
                     "allowance_fitted_refs": sum(g["quantity_per_board"] for g in groups if not g["price_offer"]),
                     "unresolved_mpn_refs": sum(g["quantity_per_board"] for g in groups if not g["mpn"])},
    }


def build_summary(bom, inputs, process):
    tariff = process["assembly_tariff"]
    cfg = inputs["assembly"]
    services = inputs["services"]
    groups = bom["groups"]
    feeder_count = sum("SURFACE_MOUNT" in g["assembly_classes"] for g in groups)
    # Planning route: all line items consigned; domestic sourcing can reduce this
    # only after exact assembly-library availability is confirmed.
    line_count = len(groups)
    batches = []
    for boards in (1, 10):
        key = str(boards)
        fabricated = 5 if boards == 1 else 10
        quote = next(q for q in process["pcb_calculator"]["quotes"] if q["fabricated_boards"] == fabricated)
        items = []
        def add(id_, description, low, base=None, high=None, evidence="ENGINEERING_ALLOWANCE", formula=None, url=None):
            items.append({"id": id_, "description": description,
                          "low_usd": money(low), "base_usd": money(low if base is None else base),
                          "high_usd": money(low if high is None else high),
                          "evidence_kind": evidence, "formula": formula, "source_url": url})
        known = sum(g["batches"][key]["catalog_subtotal_usd"] or 0 for g in groups)
        unknown = [sum(g["batches"][key][f"allowance_{label}_usd"] for g in groups) for label in ("low", "base", "high")]
        add("component_catalog_subtotal", "Детали с опубликованной ценой, закупка с MOQ и запасом", known,
            evidence="CATALOG_SNAPSHOT_NOT_FULL_BOM_PRICE", formula="sum(purchase_qty * applicable_tier_price), exact MPN only")
        add("unknown_component_allowance", "Резерв на детали без подтверждённой цены / MPN", *unknown,
            formula="sum(planned_purchase_qty * engineering_unit_budget); catalog prices remain null")
        add("pcb", f"Пустые платы: {fabricated} шт., сборка {boards} шт.", quote["total_usd"],
            evidence="PUBLIC_CALCULATOR_NO_GERBER_REVIEW", url=process["pcb_calculator"]["url"],
            formula=f"{fabricated} blanks at observed 245x165mm,4L,2oz/1oz,ENIG specification")
        for id_, desc, field in [("assembly_setup", "Подготовка двухстороннего монтажа", "setup_per_order_usd"),
                                ("stencils", "Трафареты, двухсторонний Standard", "stencils_per_order_usd"),
                                ("assembly_fixture", "Монтажная оснастка", "rigid_fixture_for_1_to_29_boards_usd"),
                                ("hand_solder_setup", "Подготовка ручной пайки", "hand_solder_labor_per_order_usd")]:
            add(id_, desc, tariff[field], evidence="PUBLISHED_TARIFF_BENCHMARK", formula=field, url=tariff["url"])
        add("feeders", "Загрузка питателей по уникальным SMT позициям", feeder_count * tariff["feeder_per_unique_part_usd"],
            evidence="PUBLISHED_TARIFF_WITH_PLANNING_COUNT", formula=f"{feeder_count} unique SMT MPN/groups *1.53; unresolved groups provisional", url=tariff["url"])
        smt_joints = boards * cfg["smt_solder_lands_per_board"]
        _, smt_rate = tier_price(tariff["smt_joint_tiers"], smt_joints)
        smt_cost = max(Decimal(str(cfg["minimum_assembly_charge_per_board_usd"])) * boards, smt_joints * smt_rate)
        add("smt", "SMT пайка по физическим паяным площадкам", smt_cost, evidence="PUBLISHED_TARIFF_WITH_PHYSICAL_LAND_COUNT",
            formula=f"max({smt_joints} joints *{smt_rate}, {boards} *0.48 minimum)", url=tariff["url"])
        tht_joints = boards * cfg["tht_solder_lands_per_board"]
        _, tht_rate = tier_price(tariff["manual_joint_tiers"], tht_joints)
        add("tht", "Ручная пайка выводных компонентов", tht_joints * tht_rate, evidence="PUBLISHED_TARIFF_WITH_PHYSICAL_LAND_COUNT",
            formula=f"{tht_joints} joints *{tht_rate}", url=tariff["url"])
        xrays = boards * cfg["xray_packages_per_board"]
        _, xray_rate = tier_price(tariff["xray_component_tiers"], xrays)
        add("xray", "Рентген скрытых соединений", xrays * xray_rate, evidence="PUBLISHED_TARIFF_WITH_PLANNING_COUNT",
            formula=f"{xrays} packages *{xray_rate}", url=tariff["url"])
        area = process["pcb_calculator"]["specification"]["width_mm"] * process["pcb_calculator"]["specification"]["height_mm"] / 100
        add("packing", "Упаковка и подтверждение размещения", boards * (tariff["packing_fixed_usd"] + tariff["packing_per_area_cm2_usd"] * area) + cfg["placement_confirmation_per_order_usd"],
            evidence="PUBLISHED_TARIFF_WITH_PER_BOARD_PACKING_ASSUMPTION", formula=f"{boards}*(0.50+0.00003*{area})+0.45", url=tariff["url"])
        cons = process["consignment"]
        consign_cost = math.ceil(line_count / cons["overseas_items_block"]) * cons["overseas_fee_per_block_usd"] + cons["overseas_handling_usd"]
        add("consignment", "Приём зарубежного комплекта деталей", consign_cost, evidence="PUBLISHED_TERMS_WITH_PLANNED_ROUTE",
            formula=f"ceil({line_count}/50)*70+15, one consolidated shipment; no second turnkey surcharge", url=cons["url"])
        for id_, desc, field in [("panel_process", "Резерв на техполя/панель и уточнение процесса", "panel_and_process_reserve_per_order_usd"),
                                ("part_handling", "Резерв на переупаковку лент и подготовку деталей", "packing_reeling_and_handling_reserve_per_order_usd"),
                                ("programming_setup", "Подготовка программирования", "programming_setup_per_order_usd"),
                                ("test_setup", "Подготовка электрической проверки партии", "electrical_test_setup_per_order_usd")]:
            add(id_, desc, *services[field], formula=field)
        add("programming", "Программирование готовым тестовым образом", *[boards * x for x in services["programming_per_board_usd"]], formula=f"{boards} * per-board programming allowance")
        add("electrical_test", "Электрическая проверка и пробное включение", *[boards * x for x in services["electrical_test_per_board_usd"]], formula=f"{boards} * per-board electrical test allowance")
        subtotal = [money(sum(i[f"{label}_usd"] for i in items)) for label in ("low", "base", "high")]
        add("contingency", "Резерв неопределённости закупки и производства", *[subtotal[i] * services["contingency_fraction"][i] for i in range(3)],
            formula="manufacturing subtotal before logistics/first fixture *5%/15%/30%")
        add("logistics", "Бюджет доставки деталей и готовых плат", *services["logistics_one_board_order_usd" if boards == 1 else "logistics_ten_board_order_usd"],
            formula="engineering shipping allowance; taxes/duties/brokerage excluded")
        repeat_totals = {f"{label}_usd": money(sum(i[f"{label}_usd"] for i in items)) for label in ("low", "base", "high")}
        add("first_fixture_nre", "Разовая подготовка проверочного жгута и адаптеров", *services["first_fixture_nre_per_project_usd"], formula="first-project NRE, excluded for repeat batch only if fixture reusable")
        totals = {f"{label}_usd": money(sum(i[f"{label}_usd"] for i in items)) for label in ("low", "base", "high")}
        totals["base_per_board_usd"] = money(totals["base_usd"] / boards)
        batches.append({"assembled_boards": boards, "fabricated_boards": fabricated, "unused_blanks": fabricated - boards,
                        "smt_placements": bom["source_counts"]["smt"] * boards, "tht_components": bom["source_counts"]["tht"] * boards,
                        "smt_solder_lands": smt_joints, "tht_solder_lands": tht_joints,
                        "feeder_count_estimate": feeder_count, "consignment_line_count": line_count,
                        "line_items": items, "totals": totals, "repeat_batch_without_fixture_nre": repeat_totals,
                        "catalog_inventory_and_attrition_value_usd": money(sum(g["batches"][key]["inventory_and_attrition_value_usd"] or 0 for g in groups)),
                        "catalog_stock_shortage_groups": [g["mpn"] for g in groups if g["batches"][key]["stock_covers_purchase"] is False],
                        "catalog_factory_stock_groups": [g["mpn"] for g in groups if g["price_offer"] and g["price_offer"].get("stock_location") == "Factory stock"],
                        "availability_status": "Cached source counts only; no stock reserved, no immediate delivery or complete kit availability confirmed.",
                        "cost_is_complete_factory_quote": False})
    return {"schema_version": 1, "generated_on": inputs["estimate_date"], "currency": "USD", "purchase_released": False,
            "status": inputs["status"], "source_selection_sha256": bom["source_selection_sha256"],
            "coverage": bom["coverage"], "price_observation_dates": bom["price_observation_dates"], "batches": batches,
            "exclusions": inputs["exclusions"], "assumptions_file": "estimate_inputs.json", "process_evidence_file": "process_evidence.json"}


def export_csv(bom):
    fields = ["cost_group_id", "mpn", "manufacturer", "refs", "quantity_per_board", "price_status", "source_url", "boards",
              "fitted_qty", "attrition_qty", "purchase_qty", "minimum_order_quantity", "order_multiple", "applied_price_break",
              "unit_price_usd", "catalog_subtotal_usd", "allowance_low_usd", "allowance_base_usd", "allowance_high_usd", "stock_covers_purchase"]
    with (HERE / "costed_bom.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for g in bom["groups"]:
            for boards, b in g["batches"].items():
                row = {k: g.get(k) for k in fields}
                row.update({k: b.get(k) for k in fields if k in b})
                row["refs"] = ", ".join(g["refs"])
                row["boards"] = boards
                writer.writerow(row)


def export_report(bom, summary, inputs):
    one, ten = summary["batches"]
    coverage = bom["coverage"]
    lines = [
        "# Бюджет изготовления GDI6: 1 и 10 собранных плат",
        "", f"Дата расчёта: {inputs['estimate_date']}. Валюта: USD. Закупка и производство не разрешены этим документом.",
        "",
        "Это параметризованная инженерная смета по текущему проекту. Публичный калькулятор подтвердил только пустые платы; поставщик не проверял Gerber/CPL, комплектуемость и цену полного PCBA. Нижний, базовый и верхний сценарии — бюджеты, а не гарантированный диапазон оферты.",
        "",
        "| Первый заказ | Нижний бюджет | Базовый бюджет | Верхний бюджет | Базовый на собранную плату |",
        "|---|---:|---:|---:|---:|",
    ]
    for b in summary["batches"]:
        t = b["totals"]
        lines.append(f"| {b['assembled_boards']} шт. | ${t['low_usd']:,.2f} | ${t['base_usd']:,.2f} | ${t['high_usd']:,.2f} | ${t['base_per_board_usd']:,.2f} |")
    lines += [
        "", "В суммы входят закупочные остатки, детали на потери монтажа, монтаж, программирование готовым тестовым образом, первичная электрическая проверка, логистический бюджет, резерв неопределённости и разовая проверочная оснастка. Налоги, пошлины и таможенное оформление не определены и не включены.",
        "", "## Состав базовой сметы", "",
        "| Статья | 1 собранная плата | 10 собранных плат |",
        "|---|---:|---:|",
    ]
    for a, b in zip(one["line_items"], ten["line_items"]):
        assert a["id"] == b["id"]
        description = "Пустые платы: партия 5 / 10 шт." if a["id"] == "pcb" else a["description"]
        lines.append(f"| {description} | ${a['base_usd']:,.2f} | ${b['base_usd']:,.2f} |")
    lines += [
        "", "## Что оплачивается, даже если не установлено", "",
        "Для одной собранной платы покупается стандартная партия из пяти пустых плат за $140.32: четыре остаются. Для десяти собираемых плат покупается десять пустых за $186.00. Одна пустая плата как отдельный заказ и минимальное число плат, принимаемых в PCBA, поставщиком не подтверждены.",
        "",
        "SDURB1020CT: на плате 2 шт.; выбранный опубликованный источник предлагает только катушку 800 шт. по $0.35583, поэтому в каждом независимом первом заказе учтено $284.66 за катушку. После установки остаётся 798 шт. для одной платы или 780 шт. для десяти, до фактических монтажных потерь. Цена $0.35583 не применялась к покупке только двух штук.",
        "",
        f"Стоимость купленных, но не установленных деталей с известными ценами, включая запас на монтаж: ${one['catalog_inventory_and_attrition_value_usd']:,.2f} / ${ten['catalog_inventory_and_attrition_value_usd']:,.2f}. Это часть уже включённой закупки, её нельзя ещё раз добавлять как расход. Часть остатков может перейти в следующую партию, если она останется доступной у сборщика.",
        "",
        f"Повторная отдельная партия с готовой проверочной оснасткой: базово ${one['repeat_batch_without_fixture_nre']['base_usd']:,.2f} за 1 шт. или ${ten['repeat_batch_without_fixture_nre']['base_usd']:,.2f} за 10 шт. Здесь вычтено только $400 оснастки. Детали, катушки и пустые платы из первого заказа не зачтены повторно автоматически: перенос остатков требует отдельного складского расчёта.",
        "", "## Полнота BOM и цен", "",
        f"Вход содержит {bom['source_counts']['fitted_refs']} устанавливаемых компонентов: {bom['source_counts']['smt']} SMT и {bom['source_counts']['tht']} THT. После объединения одинаковых MPN для общей закупки — {coverage['purchase_groups']} групп. Каталожные цены подтверждены для {coverage['catalog_priced_groups']} групп / {coverage['catalog_priced_fitted_refs']} позиций. Для {coverage['allowance_groups']} групп / {coverage['allowance_fitted_refs']} позиций использованы отдельные инженерные резервы. У {coverage['unresolved_mpn_refs']} позиций точный MPN ещё не выбран.",
        "",
        "Наличие MPN не означает его электрическую квалификацию или доступность. Неизвестная цена хранится как null; она не заменена нулём или ценой похожей детали. Точные границы заказа для части непрайсованных позиций ещё не известны. Их предварительный резерв предполагает доступную малую фасовку; если потребуется целая катушка, бюджет нужно пересчитать. Верхняя оценка не покрывает произвольный неизвестный MOQ. Все отмеченные подбором ограничения сохраняются в selection_gaps каждой закупочной группы.",
        "",
        "Основной ценовой срез наблюдался 25 октября 2026. Дополнительные записи имеют собственные даты наблюдения; возраст поискового кэша указан отдельно. Обновление расчёта 28 октября не делает эти данные живыми ценами или резервом склада.",
        "",
        "Выбранный склад не покрывает некоторые позиции. Это ограничение выбранного источника, а не утверждение об отсутствии товара у всех поставщиков. Нестоковая каталожная цена сохранена как бюджетная справка; возможность комплектации, альтернативные склады и дату поставки надо подтвердить перед заказом.",
        "", "## Методика", "",
        "1. Группировка по производителю и точному orderable MPN; дубли MPN в разных электрических контекстах объединяются. DNP и голые элементы платы не приобретаются.",
        "2. Запас на каждый MPN в каждой независимой партии: малые пассивы 0402/0603/0805 — большее из 20 шт. и 10%; прочие SMT — большее из 1 шт. и 10%; THT — большее из 1 шт. и 5%. Числа округляются вверх. Это плановые допуски на монтаж, не принятые поставщиком правила feeders/attrition. Фактический минимальный запас для каждого прохода стороны может быть выше.",
        "3. Требуемая закупка округляется по известным MOQ/multiple. Сравнивается стоимость точного количества с опубликованными более высокими ценовыми ступенями; большее количество покупается только если общий денежный расход меньше. Чужие MPN/валюты/катушки не смешиваются.",
        "4. Монтаж считается по 3210 SMT и 162 THT физическим паяным площадкам на плату. Число установок SMT-компонентов — 1034. Медным ответвлениям без пасты, монтажным отверстиям и частям одного трафаретного окна отдельная SMT-пайка не начисляется. Поставщик ещё не подтвердил собственное количество оплачиваемых соединений.",
        "5. Тариф Standard double-sided: подготовка $51.12, трафареты $16.42, питатель $1.53 на уникальную SMT-позицию, SMT-пайка $0.0016 на соединение, ручная пайка $0.0164 на соединение плюс $3.58 за заказ. Минимум $0.48 на плату — нижний порог SMT, а не дополнительная надбавка. Для рентгеновской проверки учитываются 20 IC со скрытыми площадками; итоговый объём кадров и выборку определяет сборщик.",
        "6. Закупочный маршрут в смете — детали по розничным каталогам плюс один консолидированный зарубежный комплект заказчика. Его публичный тариф: ceil(число позиций / 50) × $70 + $15. Это допущение маршрута, не подтверждение его приёма. Не добавлена одновременно вторая наценка turnkey/global sourcing.",
        "7. Резервы на детали без подтверждённой цены, упаковку, техполя, программирование, проверку, доставку и первый тестовый жгут перечислены в estimate_inputs.json. Это наши инженерные допущения, не цены производителя. Резерв неопределённости 5% / 15% / 30% считается по производственному подытогу до логистики и первого тестового жгута.",
        "", "## Ограничения электрической проверки", "",
        "Включена первичная проверка непрерывности, питания с ограничением тока, напряжений, связи и представительных эквивалентов нагрузок. Она не подтверждает работу B58Gen2DI/PI на двигателе, полные токовые и тепловые режимы, EMC, вибрацию или отказоустойчивость. Разработка прошивки, завершение PCB и квалификация платы в эту производственную смету не входят.",
        "", "## Исключения", "",
    ]
    lines += [f"- {s}" for s in inputs["exclusions"]]
    lines += [
        "", "## Первичные источники и воспроизведение", "",
        "- [JLCPCB: калькулятор PCB](https://cart.jlcpcb.com/quote) — 245 × 165 мм, 4 слоя, 1.6 мм, медь 2 oz / 1 oz, ENIG 1 µin, FR4 Tg155, зелёная маска, электротест. Без загрузки Gerber и без заказа; результат записан в process_evidence.json.",
        "- [JLCPCB: тариф монтажа](https://jlcpcb.com/help/article/pcb-assembly-price) — актуализация страницы 22 октября 2026; используется как тарифный ориентир, а не полный расчёт PCBA.",
        "- [JLCPCB: consignment](https://jlcpcb.com/help/article/consignment-part-terms-conditions) — дополнительные условия приёма зарубежного комплекта.",
        "- [JLCPCB: индивидуальные MOQ/attrition](https://jlcpcb.com/help/article/pcb-assembly-faqs-part-2) и [влияние двух сторон](https://jlcpcb.com/blog/reduce-pcb-assembly-cost-prototype).",
        "- Для каждой цены — конкретная ссылка, дата, возраст кэша, упаковка, ступени и склад в catalog_additions*.json и price_evidence_2026_10_25.json. Для позиций без цены используется estimate_inputs.json, а не фиктивная ссылка на цену.",
        "", "Пересчитать из сохранённого компактного среза:", "",
        "```text", "python Power8GDI/procurement/costing/build_estimate.py", "python -m unittest discover -s Power8GDI/procurement/costing -p test_estimate.py -v", "```", "",
        "Для нового подбора добавьте --selection Power8GDI/procurement/selection/bom_selection.json. Скрипт сохраняет hash входа, объединённую постатейную закупку и суммы; никаких сетевых запросов или заказов он не выполняет.",
        "", f"SHA256 исходного подбора: `{bom['source_selection_sha256']}`.", "",
    ]
    (PROJECT / "docs/COST_GDI6_ESTIMATE.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, default=HERE / "selection_snapshot.json")
    args = parser.parse_args()
    snapshot = compact_selection(args.selection)
    inputs, process = read(HERE / "estimate_inputs.json"), read(HERE / "process_evidence.json")
    bom = cost_bom(snapshot, inputs, load_catalog())
    summary = build_summary(bom, inputs, process)
    write(HERE / "selection_snapshot.json", snapshot)
    write(HERE / "costed_bom.json", bom)
    write(HERE / "estimate_summary.json", summary)
    export_csv(bom)
    export_report(bom, summary, inputs)
    print(json.dumps({"coverage": bom["coverage"], "batches": [{"boards": b["assembled_boards"], **b["totals"]} for b in summary["batches"]]}, indent=2))


if __name__ == "__main__":
    main()
