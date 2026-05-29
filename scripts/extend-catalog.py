#!/usr/bin/env python3
"""
extend-catalog.py
=================
One-shot, idempotent transform that upgrades the canonical catalog for the SKU
Resolution Engine (MVP2). It:

  1. Adds the homologation columns to data/seed/canonicalproduct.csv:
        b2b_homologation, b2b_runflat, b2b_extraload, b2b_canonical_key
     (existing 30 rows default to None / false / false).
  2. Appends the homologation "twin" products that demonstrate the trap
     (Latitude Sport 3 base + BMW/Mercedes/Porsche variants, Pilot Sport 4 S,
      a run-flat PremiumContact 6).
  3. Recomputes b2b_canonical_key for every row using the SAME function the
     Azure Function uses (azure/functions/sku_matcher.canonical_key), so a
     seeded key is byte-identical to what normalize-sku computes at runtime.
  4. Appends the "trap" supplier offers to data/seed/supplieroffer.csv
     (left UNbound — empty b2b_canonical_name — so the Normalize SKU flow
      resolves them live during the demo).
  5. Emits azure/functions/catalog.json — a self-contained catalog snapshot so
     the normalize-sku endpoint works in standalone/local tests without a flow.

Idempotent: keyed on b2b_name (products) and supplier+raw_sku (offers); re-runs
overwrite computed columns and never duplicate rows.

Usage:  python3 scripts/extend-catalog.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SEED = REPO / "data" / "seed"
FUNC = REPO / "azure" / "functions"
sys.path.insert(0, str(FUNC))

from sku_matcher import ParsedTire, canonical_key  # noqa: E402

CANON_CSV = SEED / "canonicalproduct.csv"
OFFER_CSV = SEED / "supplieroffer.csv"
CATALOG_JSON = FUNC / "catalog.json"

CANON_FIELDS = [
    "b2b_name", "b2b_brand", "b2b_model", "b2b_season",
    "b2b_width", "b2b_profile", "b2b_diameter", "b2b_load_index",
    "b2b_speed_index", "b2b_ean",
    "b2b_homologation", "b2b_runflat", "b2b_extraload", "b2b_canonical_key",
]

# season: 1=Summer 2=WinterStudded 3=WinterFriction 4=AllSeason (seed map)
# The homologation twin family — identical size/model, different OEM approval.
TWINS = [
    # name, brand, model, season, W, P, D, load, speed, ean, homolog, runflat, extraload
    ("Michelin Latitude Sport 3 245/45 R20 103W XL RunFlat",
     "Michelin", "Latitude Sport 3", 1, 245, 45, 20, 103, "W", "3528700111017", "None", "true", "true"),
    ("Michelin Latitude Sport 3 245/45 R20 103W XL RunFlat * (BMW)",
     "Michelin", "Latitude Sport 3", 1, 245, 45, 20, 103, "W", "3528700111024", "Star_BMW", "true", "true"),
    ("Michelin Latitude Sport 3 245/45 R20 103W XL RunFlat MO (Mercedes)",
     "Michelin", "Latitude Sport 3", 1, 245, 45, 20, 103, "W", "3528700111031", "MO_Mercedes", "true", "true"),
    ("Michelin Latitude Sport 3 245/45 R20 103W XL RunFlat N0 (Porsche)",
     "Michelin", "Latitude Sport 3", 1, 245, 45, 20, 103, "W", "3528700111048", "N0_Porsche", "true", "true"),
    ("Michelin Pilot Sport 4 S 245/35 R20 95Y XL",
     "Michelin", "Pilot Sport 4 S", 1, 245, 35, 20, 95, "Y", "3528700222017", "None", "false", "true"),
    ("Continental PremiumContact 6 225/45 R17 94Y XL SSR RunFlat",
     "Continental", "PremiumContact 6", 1, 225, 45, 17, 94, "Y", "4019238222017", "None", "true", "true"),
]

# Trap supplier offers — canonical_name intentionally EMPTY (unbound).
# cols: supplier, canonical_name, raw_name, raw_sku, price, currency, stock, city, lead
TRAP_OFFERS = [
    ("Rosshinaopt", "", "MICHELIN Latitude Sport 3 245/45 R20 103W XL Run on Flat *",
     "ML-LS3-24545R20-RFT-S", "318.00", "USD", "14", "Moscow", "3"),
    ("Rosshinaopt", "", "Michelin Latitude Sport 3 245/45R20 103W XL RunFlat",
     "ML-LS3-24545R20-RFT", "239.00", "USD", "9", "Moscow", "3"),
    ("TyreCenter SPB", "", "МИШЛЕН Latitude Sport 3 245/45R20 103W XL RunFlat MO",
     "23-LS3-MERC", "305.00", "USD", "6", "Saint Petersburg", "4"),
    ("Koleso.ru", "", "Michelin Latitude Sport 3 245/45 R20 103W XL Run Flat *",
     "KOL-LS3-BMW-20", "322.50", "USD", "5", "Novosibirsk", "5"),
    ("Rosshinaopt", "", "MICHELIN Pilot Sport 4 S 245/35R20 95Y XL",
     "MPS4S-24535R20", "281.00", "USD", "11", "Moscow", "2"),
    ("TyreCenter SPB", "", "МИШЛЕН PS4 S 245/35 R20 95Y",
     "PS4S-CYR-2035", "274.00", "USD", "8", "Saint Petersburg", "3"),
    ("Koleso.ru", "", "Continental PremiumContact 6 225/45R17 94Y XL SSR",
     "CPC6-RFT-2245", "142.00", "USD", "19", "Novosibirsk", "4"),
    ("Rosshinaopt", "", "Michelin Latitude Sport 3 245/45 R20 103W XL",
     "LS3-NOSPEC-20", "235.00", "USD", "4", "Moscow", "3"),
]


def _to_int(v):
    try:
        return int(v) if str(v).strip() else None
    except ValueError:
        return None


def _row_key(row: dict) -> str:
    p = ParsedTire(
        brand=row.get("b2b_brand", ""),
        model=row.get("b2b_model", ""),
        width=_to_int(row.get("b2b_width")),
        profile=_to_int(row.get("b2b_profile")),
        diameter=_to_int(row.get("b2b_diameter")),
        load_index=_to_int(row.get("b2b_load_index")),
        speed_index=row.get("b2b_speed_index", "") or "",
        homologation=row.get("b2b_homologation", "None") or "None",
        runflat=str(row.get("b2b_runflat", "")).strip().lower() in ("1", "true", "yes"),
        extraload=str(row.get("b2b_extraload", "")).strip().lower() in ("1", "true", "yes"),
    )
    return canonical_key(p)


def extend_canonical() -> list[dict]:
    rows = list(csv.DictReader(CANON_CSV.open(encoding="utf-8")))
    by_name = {r["b2b_name"]: r for r in rows}

    # ensure new columns exist on every existing row (defaults)
    for r in rows:
        r.setdefault("b2b_homologation", "None")
        r.setdefault("b2b_runflat", "false")
        r.setdefault("b2b_extraload", "false")
        if not r.get("b2b_homologation"):
            r["b2b_homologation"] = "None"

    # add / overwrite twin rows
    for t in TWINS:
        (name, brand, model, season, w, p, d, load, speed, ean,
         homolog, runflat, extraload) = t
        rec = by_name.get(name, {})
        rec.update({
            "b2b_name": name, "b2b_brand": brand, "b2b_model": model,
            "b2b_season": str(season), "b2b_width": str(w), "b2b_profile": str(p),
            "b2b_diameter": str(d), "b2b_load_index": str(load),
            "b2b_speed_index": speed, "b2b_ean": ean,
            "b2b_homologation": homolog, "b2b_runflat": runflat,
            "b2b_extraload": extraload,
        })
        if name not in by_name:
            rows.append(rec)
            by_name[name] = rec

    # recompute canonical key for everyone
    for r in rows:
        r["b2b_canonical_key"] = _row_key(r)

    with CANON_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CANON_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in CANON_FIELDS})

    print(f"canonicalproduct.csv: {len(rows)} rows ({len(TWINS)} twins ensured)")
    return rows


def append_trap_offers() -> None:
    existing = list(csv.reader(OFFER_CSV.open(encoding="utf-8")))
    header = existing[0]
    seen = {(r[0], r[3]) for r in existing[1:] if len(r) > 3}  # (supplier, raw_sku)

    added = 0
    with OFFER_CSV.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        for o in TRAP_OFFERS:
            key = (o[0], o[3])
            if key in seen:
                continue
            w.writerow(list(o))
            added += 1
    print(f"supplieroffer.csv: +{added} trap offers (header cols: {len(header)})")


def emit_catalog_json(rows: list[dict]) -> None:
    catalog = [{
        "id": r["b2b_name"],            # slug id for standalone use; flow passes real GUIDs
        "name": r["b2b_name"],
        "brand": r.get("b2b_brand", ""),
        "model": r.get("b2b_model", ""),
        "width": _to_int(r.get("b2b_width")),
        "profile": _to_int(r.get("b2b_profile")),
        "diameter": _to_int(r.get("b2b_diameter")),
        "load_index": _to_int(r.get("b2b_load_index")),
        "speed_index": r.get("b2b_speed_index", ""),
        "homologation": r.get("b2b_homologation", "None") or "None",
        "runflat": str(r.get("b2b_runflat", "")).strip().lower() in ("1", "true", "yes"),
        "extraload": str(r.get("b2b_extraload", "")).strip().lower() in ("1", "true", "yes"),
    } for r in rows]
    CATALOG_JSON.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"catalog.json: {len(catalog)} products → {CATALOG_JSON.relative_to(REPO)}")


def main() -> None:
    rows = extend_canonical()
    append_trap_offers()
    emit_catalog_json(rows)
    print("done.")


if __name__ == "__main__":
    main()
