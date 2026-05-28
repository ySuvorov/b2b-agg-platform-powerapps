#!/usr/bin/env python3
"""
seed-via-az-token.py
====================
Loads all seed CSVs into Dataverse Dev using a token from az CLI.
No device code, no App Registration needed — just az login.

Usage:
    # Ensure az is logged in as <admin-upn>
    python3 scripts/seed-via-az-token.py

The script will call 'az account get-access-token' automatically.
"""

from __future__ import annotations

import csv
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parent.parent
SEED_DIR = REPO / "data" / "seed"

DV_URL = "https://YOUR-DATAVERSE-ORG.crm.dynamics.com"
API = f"{DV_URL}/api/data/v9.2"

# ── Entity set names (verified from Dataverse) ───────────────────────────────
# Dataverse auto-generates plural names; these were confirmed via API.
# If import fails with 404, re-run /tmp/get_entity_sets.py to verify.
ENTITY_SETS: dict[str, str] = {
    "b2b_region":           "b2b_regions",
    "b2b_supplier":         "b2b_suppliers",
    "b2b_canonicalproduct": "b2b_canonicalproducts",
    "b2b_supplieroffer":    "b2b_supplieroffersset",  # Dataverse sometimes appends 'set'
}

# Primary key logical names
PK: dict[str, str] = {
    "b2b_region":           "b2b_regionid",
    "b2b_supplier":         "b2b_supplierid",
    "b2b_canonicalproduct": "b2b_canonicalproductid",
    "b2b_supplieroffer":    "b2b_supplyofferid",
}


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_token() -> str:
    result = subprocess.run(
        ["az", "account", "get-access-token",
         "--resource", DV_URL,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"az get-access-token failed: {result.stderr}")
    token = result.stdout.strip()
    log.info(f"Token acquired via az CLI ({len(token)} chars)")
    return token


def make_session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {token}",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "Prefer": "return=representation",
    })
    return s


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_entity_set_name(s: requests.Session, logical_name: str) -> str:
    """Query Dataverse for the real EntitySetName."""
    r = s.get(
        f"{API}/EntityDefinitions(LogicalName='{logical_name}')",
        params={"$select": "EntitySetName,PrimaryIdAttribute"},
        timeout=20,
    )
    if r.status_code != 200:
        raise RuntimeError(f"EntityDefinitions lookup failed: {r.status_code} {r.text[:200]}")
    data = r.json()
    ENTITY_SETS[logical_name] = data["EntitySetName"]
    PK[logical_name] = data["PrimaryIdAttribute"]
    return data["EntitySetName"]


def record_exists(s: requests.Session, entity: str, filter_expr: str) -> dict | None:
    url = f"{API}/{ENTITY_SETS[entity]}"
    r = s.get(url, params={"$filter": filter_expr, "$top": 1, "$select": PK[entity]}, timeout=20)
    if r.status_code != 200:
        return None
    rows = r.json().get("value", [])
    return rows[0] if rows else None


def upsert(s: requests.Session, entity: str, payload: dict, match_field: str) -> str:
    """Create or update. Returns 'created' / 'updated' / 'error'."""
    existing = record_exists(
        s, entity, f"{match_field} eq '{payload[match_field]}'"
    )
    set_name = ENTITY_SETS[entity]
    if existing:
        pk_val = existing[PK[entity]]
        r = s.patch(f"{API}/{set_name}({pk_val})", json=payload, timeout=20)
        return "updated" if r.status_code in (200, 204) else f"error:{r.status_code}"
    else:
        r = s.post(f"{API}/{set_name}", json=payload, timeout=20)
        return "created" if r.status_code in (200, 201, 204) else f"error:{r.status_code}"


# ── Seed functions ────────────────────────────────────────────────────────────

def seed_regions(s: requests.Session) -> dict[str, str]:
    """Returns {name: id} map for region lookups."""
    log.info("Seeding b2b_region...")
    climate_map = {
        "1": 10000, "2": 10001, "3": 10002, "4": 10003, "5": 10004
    }
    region_ids: dict[str, str] = {}
    created = updated = errors = 0

    rows = list(csv.DictReader(open(SEED_DIR / "region.csv")))
    for row in rows:
        payload = {
            "b2b_name": row["b2b_name"],
            "b2b_federal_district": row.get("b2b_federal_district", ""),
        }
        cz = row.get("b2b_climate_zone", "").strip()
        if cz and cz in climate_map:
            payload["b2b_climate_zone"] = climate_map[cz]

        result = upsert(s, "b2b_region", payload, "b2b_name")
        if result == "created":
            created += 1
        elif result == "updated":
            updated += 1
        else:
            errors += 1
            log.warning(f"  Region '{row['b2b_name']}': {result}")

    # Fetch IDs for lookup
    r = s.get(f"{API}/{ENTITY_SETS['b2b_region']}",
              params={"$select": f"b2b_name,{PK['b2b_region']}", "$top": 50}, timeout=20)
    for rec in r.json().get("value", []):
        region_ids[rec["b2b_name"]] = rec[PK["b2b_region"]]

    log.info(f"  Regions: created={created}, updated={updated}, errors={errors}")
    return region_ids


def seed_suppliers(s: requests.Session, region_ids: dict[str, str]) -> dict[str, str]:
    """Returns {name: id} map."""
    log.info("Seeding b2b_supplier...")
    tier_map = {"1": 10000, "2": 10001, "3": 10002}
    supplier_ids: dict[str, str] = {}
    created = updated = errors = 0

    rows = list(csv.DictReader(open(SEED_DIR / "supplier.csv")))
    for row in rows:
        payload: dict[str, Any] = {
            "b2b_name": row["b2b_name"],
            "b2b_feed_endpoint": row.get("b2b_feed_endpoint", ""),
            "b2b_is_active": row.get("b2b_is_active", "true").lower() == "true",
        }
        tier = row.get("b2b_tier", "").strip()
        if tier in tier_map:
            payload["b2b_tier"] = tier_map[tier]
        score = row.get("b2b_trust_score", "").strip()
        if score:
            payload["b2b_trust_score"] = float(score)

        result = upsert(s, "b2b_supplier", payload, "b2b_name")
        if result == "created":
            created += 1
        elif result == "updated":
            updated += 1
        else:
            errors += 1
            log.warning(f"  Supplier '{row['b2b_name']}': {result}")

    # Fetch IDs
    r = s.get(f"{API}/{ENTITY_SETS['b2b_supplier']}",
              params={"$select": f"b2b_name,{PK['b2b_supplier']}", "$top": 50}, timeout=20)
    for rec in r.json().get("value", []):
        supplier_ids[rec["b2b_name"]] = rec[PK["b2b_supplier"]]

    log.info(f"  Suppliers: created={created}, updated={updated}, errors={errors}")
    return supplier_ids


def seed_canonical_products(s: requests.Session) -> dict[str, str]:
    """Returns {name: id} map."""
    log.info("Seeding b2b_canonicalproduct...")
    season_map = {"1": 10000, "2": 10001, "3": 10002, "4": 10003}
    product_ids: dict[str, str] = {}
    created = updated = errors = 0

    rows = list(csv.DictReader(open(SEED_DIR / "canonicalproduct.csv")))
    for row in rows:
        payload: dict[str, Any] = {
            "b2b_name": row["b2b_name"],
            "b2b_brand": row.get("b2b_brand", ""),
            "b2b_model": row.get("b2b_model", ""),
            "b2b_ean": row.get("b2b_ean", ""),
            "b2b_speed_index": row.get("b2b_speed_index", ""),
        }
        for int_field in ["b2b_width", "b2b_profile", "b2b_diameter", "b2b_load_index"]:
            val = row.get(int_field, "").strip()
            if val:
                try:
                    payload[int_field] = int(val)
                except ValueError:
                    pass
        season = row.get("b2b_season", "").strip()
        if season in season_map:
            payload["b2b_season"] = season_map[season]

        result = upsert(s, "b2b_canonicalproduct", payload, "b2b_name")
        if result == "created":
            created += 1
        elif result == "updated":
            updated += 1
        else:
            errors += 1
            log.warning(f"  Product '{row['b2b_name']}': {result}")

    # Fetch IDs
    r = s.get(f"{API}/{ENTITY_SETS['b2b_canonicalproduct']}",
              params={"$select": f"b2b_name,{PK['b2b_canonicalproduct']}", "$top": 50}, timeout=30)
    for rec in r.json().get("value", []):
        product_ids[rec["b2b_name"]] = rec[PK["b2b_canonicalproduct"]]

    log.info(f"  Products: created={created}, updated={updated}, errors={errors}")
    return product_ids


def seed_supplier_offers(
    s: requests.Session,
    supplier_ids: dict[str, str],
    product_ids: dict[str, str],
) -> None:
    log.info("Seeding b2b_supplieroffer...")
    created = updated = skipped = errors = 0
    set_name = ENTITY_SETS["b2b_supplieroffer"]

    rows = list(csv.DictReader(open(SEED_DIR / "supplieroffer.csv")))
    log.info(f"  {len(rows)} rows to process...")

    for i, row in enumerate(rows, 1):
        supplier_name = row.get("b2b_supplier_name", "").strip()
        product_name  = row.get("b2b_canonical_name", "").strip()

        sup_id = supplier_ids.get(supplier_name)
        prod_id = product_ids.get(product_name)

        if not sup_id:
            log.debug(f"  Row {i}: supplier '{supplier_name}' not found — skip")
            skipped += 1
            continue

        raw_sku = row.get("b2b_raw_sku", "").strip()
        payload: dict[str, Any] = {
            "b2b_name": f"{supplier_name} – {raw_sku}"[:300],
            "b2b_raw_name": row.get("b2b_raw_name", ""),
            "b2b_raw_sku": raw_sku,
            "b2b_currency": row.get("b2b_currency", "USD"),
            "b2b_warehouse_city": row.get("b2b_warehouse_city", ""),
            # Bind supplier lookup
            f"b2b_supplier@odata.bind": f"/{ENTITY_SETS['b2b_supplier']}({sup_id})",
        }
        if prod_id:
            payload[f"b2b_canonical_product@odata.bind"] = (
                f"/{ENTITY_SETS['b2b_canonicalproduct']}({prod_id})"
            )
        for int_field in ["b2b_stock", "b2b_lead_time_days"]:
            val = row.get(int_field, "").strip()
            if val:
                try:
                    payload[int_field] = int(val)
                except ValueError:
                    pass
        price = row.get("b2b_price", "").strip()
        if price:
            try:
                payload["b2b_price"] = float(price)
            except ValueError:
                pass

        # Check existence by supplier + raw_sku
        existing = None
        if sup_id and raw_sku:
            filt = (
                f"b2b_raw_sku eq '{raw_sku}' and "
                f"_b2b_supplier_value eq {sup_id}"
            )
            r = s.get(
                f"{API}/{set_name}",
                params={"$filter": filt, "$top": 1, "$select": PK["b2b_supplieroffer"]},
                timeout=20,
            )
            if r.status_code == 200:
                rows_found = r.json().get("value", [])
                existing = rows_found[0] if rows_found else None

        if existing:
            pk_val = existing[PK["b2b_supplieroffer"]]
            r = s.patch(f"{API}/{set_name}({pk_val})", json=payload, timeout=20)
            if r.status_code in (200, 204):
                updated += 1
            else:
                errors += 1
        else:
            r = s.post(f"{API}/{set_name}", json=payload, timeout=20)
            if r.status_code in (200, 201, 204):
                created += 1
            else:
                errors += 1
                if errors <= 3:
                    log.warning(f"  Offer row {i}: {r.status_code} {r.text[:150]}")

        if i % 25 == 0:
            log.info(f"  Progress: {i}/{len(rows)}")

    log.info(f"  Offers: created={created}, updated={updated}, skipped={skipped}, errors={errors}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    token = get_token()
    s = make_session(token)

    # Verify connectivity
    r = s.get(f"{API}/WhoAmI", timeout=15)
    if r.status_code != 200:
        log.error(f"Cannot connect to Dataverse: {r.status_code}")
        sys.exit(1)
    log.info(f"Connected to Dataverse (OrgId={r.json().get('OrganizationId')})")

    # Resolve real entity set names from the API
    log.info("Resolving entity set names...")
    for logical in ["b2b_region", "b2b_supplier", "b2b_canonicalproduct", "b2b_supplieroffer"]:
        set_name = get_entity_set_name(s, logical)
        log.info(f"  {logical} → /{set_name} (pk={PK[logical]})")

    # Seed in dependency order
    region_ids   = seed_regions(s)
    supplier_ids = seed_suppliers(s, region_ids)
    product_ids  = seed_canonical_products(s)
    seed_supplier_offers(s, supplier_ids, product_ids)

    log.info("")
    log.info("=== Seed complete ===")
    log.info(f"  Regions loaded:   {len(region_ids)}")
    log.info(f"  Suppliers loaded: {len(supplier_ids)}")
    log.info(f"  Products loaded:  {len(product_ids)}")


if __name__ == "__main__":
    main()
