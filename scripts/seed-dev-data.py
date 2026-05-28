#!/usr/bin/env python3
"""
seed-dev-data.py
----------------
Loads all demo seed data into the B2BAgg Dataverse Dev environment.

Load order: Region -> Supplier -> CanonicalProduct -> SupplierOffer

Auth: uses client credentials (AZURE_CLIENT_ID + AZURE_CLIENT_SECRET +
AZURE_TENANT_ID env vars). Falls back to device code flow when client
secret is missing or blank.

Idempotent: each entity is matched by its natural key before creating.

Usage:
    pip install -r requirements-seed.txt
    # with client creds:
    export DATAVERSE_URL=https://YOUR-DATAVERSE-ORG.crm.dynamics.com/
    export AZURE_CLIENT_ID=...
    export AZURE_CLIENT_SECRET=...
    export AZURE_TENANT_ID=...
    python seed-dev-data.py

    # device code (interactive):
    export DATAVERSE_URL=https://YOUR-DATAVERSE-ORG.crm.dynamics.com/
    python seed-dev-data.py
"""

import csv
import os
import sys
from pathlib import Path

import msal
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env.local")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATAVERSE_URL = os.getenv("DATAVERSE_URL", "https://YOUR-DATAVERSE-ORG.crm.dynamics.com/").rstrip("/")
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "")

AUTHORITY = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}" if AZURE_TENANT_ID else "https://login.microsoftonline.com/common"
SCOPE = [f"{DATAVERSE_URL}/.default"]

DATA_DIR = Path(__file__).parent.parent / "data" / "seed"

# Counters across all entity types
counters = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def get_token() -> str:
    """Return a Bearer token, using client creds or device code fallback."""
    if AZURE_CLIENT_ID and AZURE_CLIENT_SECRET and AZURE_TENANT_ID:
        app = msal.ConfidentialClientApplication(
            AZURE_CLIENT_ID,
            authority=AUTHORITY,
            client_credential=AZURE_CLIENT_SECRET,
        )
        result = app.acquire_token_for_client(scopes=SCOPE)
    else:
        print("[auth] Client credentials not set — falling back to device code flow.")
        if not AZURE_CLIENT_ID:
            raise ValueError(
                "AZURE_CLIENT_ID must be set even for device code auth. "
                "Set it to the App Registration's client ID."
            )
        app = msal.PublicClientApplication(AZURE_CLIENT_ID, authority=AUTHORITY)
        flow = app.initiate_device_flow(scopes=SCOPE)
        if "user_code" not in flow:
            raise RuntimeError(f"Could not initiate device flow: {flow}")
        print(flow["message"])
        result = app.acquire_token_by_device_flow(flow)

    if "access_token" not in result:
        raise RuntimeError(f"Failed to acquire token: {result.get('error_description', result)}")
    return result["access_token"]


# ---------------------------------------------------------------------------
# Dataverse API helpers
# ---------------------------------------------------------------------------

class DataverseClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.api = f"{self.base_url}/api/data/v9.2"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            "Content-Type": "application/json",
        }

    def get(self, entity_set: str, filter_expr: str = "", select: str = "") -> list:
        url = f"{self.api}/{entity_set}"
        params = {}
        if filter_expr:
            params["$filter"] = filter_expr
        if select:
            params["$select"] = select
        resp = requests.get(url, headers=self.headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("value", [])

    def create(self, entity_set: str, payload: dict) -> str:
        """Create a record and return its GUID."""
        url = f"{self.api}/{entity_set}"
        resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
        resp.raise_for_status()
        location = resp.headers.get("OData-EntityId", "")
        # Extract GUID from location header: ...entity_set(guid)
        guid = ""
        if "(" in location:
            guid = location.split("(")[-1].rstrip(")")
        return guid

    def patch(self, entity_set: str, guid: str, payload: dict) -> None:
        url = f"{self.api}/{entity_set}({guid})"
        resp = requests.patch(url, headers=self.headers, json=payload, timeout=30)
        resp.raise_for_status()


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------

def upsert_record(client: DataverseClient, entity_set: str, filter_expr: str,
                  payload: dict, label: str) -> str | None:
    """
    Check if a record matching filter_expr already exists.
    - If not found: create it, return its GUID.
    - If found: patch it with the payload, return its GUID.
    Returns None on error.
    """
    try:
        pk_field = _pk_field(entity_set)
        existing = client.get(entity_set, filter_expr=filter_expr, select=pk_field)
        if existing:
            guid = existing[0][pk_field]
            client.patch(entity_set, guid, payload)
            counters["updated"] += 1
            print(f"  [updated]  {label}")
            return guid
        else:
            guid = client.create(entity_set, payload)
            counters["created"] += 1
            print(f"  [created]  {label}")
            return guid
    except requests.HTTPError as exc:
        counters["errors"] += 1
        print(f"  [ERROR]    {label}: {exc.response.status_code} {exc.response.text[:200]}", file=sys.stderr)
        return None
    except Exception as exc:
        counters["errors"] += 1
        print(f"  [ERROR]    {label}: {exc}", file=sys.stderr)
        return None


def _pk_field(entity_set: str) -> str:
    mapping = {
        "b2b_regions": "b2b_regionid",
        "b2b_suppliers": "b2b_supplierid",
        "b2b_canonicalproducts": "b2b_canonicalproductid",
        "b2b_supplierofferssets": "b2b_supplieroffersetid",
    }
    # Fallback: entity_set name without trailing 's' + 'id'
    return mapping.get(entity_set, entity_set.rstrip("s") + "id")


# ---------------------------------------------------------------------------
# Climate zone and tier mappings
# ---------------------------------------------------------------------------

CLIMATE_ZONE_VALUES = {
    "1": 1,   # Nord
    "2": 2,   # Center
    "3": 3,   # South
    "4": 4,   # Caucasus
    "5": 5,   # FarEast
}

TIER_VALUES = {
    "1": 1,   # Gold
    "2": 2,   # Silver
    "3": 3,   # Bronze
}

SEASON_VALUES = {
    "1": 1,   # Summer
    "2": 2,   # WinterStudded
    "3": 3,   # WinterFriction
    "4": 4,   # AllSeason
}


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

def seed_regions(client: DataverseClient) -> dict[str, str]:
    """Seed b2b_region records. Returns {name: guid} mapping."""
    print("\n=== Seeding Regions ===")
    region_map: dict[str, str] = {}
    csv_path = DATA_DIR / "region.csv"
    if not csv_path.exists():
        print(f"  [SKIP] {csv_path} not found", file=sys.stderr)
        return region_map

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["b2b_name"].strip()
            climate_raw = row["b2b_climate_zone"].strip()
            federal_district = row["b2b_federal_district"].strip()

            payload = {
                "b2b_name": name,
                "b2b_climatezone": CLIMATE_ZONE_VALUES.get(climate_raw, 2),
                "b2b_federal_district": federal_district,
            }
            filter_expr = f"b2b_name eq '{_esc(name)}'"
            guid = upsert_record(client, "b2b_regions", filter_expr, payload, name)
            if guid:
                region_map[name] = guid
    return region_map


def seed_suppliers(client: DataverseClient) -> dict[str, str]:
    """Seed b2b_supplier records. Returns {name: guid} mapping."""
    print("\n=== Seeding Suppliers ===")
    supplier_map: dict[str, str] = {}
    csv_path = DATA_DIR / "supplier.csv"
    if not csv_path.exists():
        print(f"  [SKIP] {csv_path} not found", file=sys.stderr)
        return supplier_map

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["b2b_name"].strip()
            tier_raw = row["b2b_tier"].strip()
            trust_score = float(row["b2b_trust_score"])
            feed_endpoint = row["b2b_feed_endpoint"].strip()
            is_active = row["b2b_is_active"].strip().lower() == "true"

            payload = {
                "b2b_name": name,
                "b2b_tier": TIER_VALUES.get(tier_raw, 3),
                "b2b_trustscore": trust_score,
                "b2b_feedendpoint": feed_endpoint,
                "b2b_active": is_active,
            }
            filter_expr = f"b2b_name eq '{_esc(name)}'"
            guid = upsert_record(client, "b2b_suppliers", filter_expr, payload, name)
            if guid:
                supplier_map[name] = guid
    return supplier_map


def seed_canonical_products(client: DataverseClient) -> dict[str, str]:
    """Seed b2b_canonicalproduct records. Returns {name: guid} mapping."""
    print("\n=== Seeding Canonical Products ===")
    product_map: dict[str, str] = {}
    csv_path = DATA_DIR / "canonicalproduct.csv"
    if not csv_path.exists():
        print(f"  [SKIP] {csv_path} not found", file=sys.stderr)
        return product_map

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["b2b_name"].strip()
            season_raw = row["b2b_season"].strip()

            payload = {
                "b2b_name": name,
                "b2b_brand": row["b2b_brand"].strip(),
                "b2b_model": row["b2b_model"].strip(),
                "b2b_season": SEASON_VALUES.get(season_raw, 1),
                "b2b_width": int(row["b2b_width"]),
                "b2b_profile": int(row["b2b_profile"]),
                "b2b_diameter": int(row["b2b_diameter"]),
                "b2b_loadindex": int(row["b2b_load_index"]),
                "b2b_speedindex": row["b2b_speed_index"].strip(),
                "b2b_ean": row["b2b_ean"].strip(),
            }
            filter_expr = f"b2b_ean eq '{_esc(row['b2b_ean'].strip())}'"
            guid = upsert_record(client, "b2b_canonicalproducts", filter_expr, payload, name)
            if guid:
                product_map[name] = guid
    return product_map


def seed_supplier_offers(client: DataverseClient,
                         supplier_map: dict[str, str],
                         product_map: dict[str, str]) -> None:
    """Seed b2b_supplieroffer records, wiring FK lookups by name."""
    print("\n=== Seeding Supplier Offers ===")
    csv_path = DATA_DIR / "supplieroffer.csv"
    if not csv_path.exists():
        print(f"  [SKIP] {csv_path} not found", file=sys.stderr)
        return

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            supplier_name = row["b2b_supplier_name"].strip()
            canonical_name = row["b2b_canonical_name"].strip()
            raw_sku = row["b2b_raw_sku"].strip()

            supplier_guid = supplier_map.get(supplier_name)
            product_guid = product_map.get(canonical_name)

            if not supplier_guid:
                print(f"  [WARN] Supplier not found: '{supplier_name}' — skipping {raw_sku}", file=sys.stderr)
                counters["skipped"] += 1
                continue
            if not product_guid:
                print(f"  [WARN] Canonical product not found: '{canonical_name}' — skipping {raw_sku}", file=sys.stderr)
                counters["skipped"] += 1
                continue

            payload = {
                "b2b_rawname": row["b2b_raw_name"].strip(),
                "b2b_rawsku": raw_sku,
                "b2b_price": float(row["b2b_price"]),
                "b2b_currency": 1,  # USD choice value
                "b2b_stock": int(row["b2b_stock"]),
                "b2b_warehousecity": row["b2b_warehouse_city"].strip(),
                "b2b_leaddays": int(row["b2b_lead_time_days"]),
                # FK lookups — use @odata.bind syntax
                "b2b_supplier@odata.bind": f"/b2b_suppliers({supplier_guid})",
                "b2b_canonicalproduct@odata.bind": f"/b2b_canonicalproducts({product_guid})",
            }
            # Idempotency key: supplier + raw_sku
            filter_expr = (
                f"b2b_rawsku eq '{_esc(raw_sku)}' and "
                f"_b2b_supplier_value eq {supplier_guid}"
            )
            label = f"{supplier_name} / {raw_sku}"
            upsert_record(client, "b2b_supplierofferssets", filter_expr, payload, label)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _esc(value: str) -> str:
    """Escape single quotes for OData $filter strings."""
    return value.replace("'", "''")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("B2BAgg Dev Data Seeder")
    print(f"Target: {DATAVERSE_URL}")
    print("Acquiring token...")

    try:
        token = get_token()
    except Exception as exc:
        print(f"[FATAL] Auth failed: {exc}", file=sys.stderr)
        sys.exit(1)

    client = DataverseClient(DATAVERSE_URL, token)

    # Seed in FK-dependency order
    region_map = seed_regions(client)
    supplier_map = seed_suppliers(client)
    product_map = seed_canonical_products(client)
    seed_supplier_offers(client, supplier_map, product_map)

    # Summary
    total = counters["created"] + counters["updated"] + counters["skipped"] + counters["errors"]
    print(
        f"\n=== Done ===\n"
        f"  Created : {counters['created']}\n"
        f"  Updated : {counters['updated']}\n"
        f"  Skipped : {counters['skipped']}\n"
        f"  Errors  : {counters['errors']}\n"
        f"  Total   : {total}"
    )
    if counters["errors"] > 0:
        sys.exit(2)


if __name__ == "__main__":
    main()
