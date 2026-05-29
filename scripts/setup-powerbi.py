#!/usr/bin/env python3
"""
setup-powerbi.py — Provision Power BI workspace + push dataset for B2BAgg.

Usage:
    python3 scripts/setup-powerbi.py

Pre-requisites:
    pip3 install requests
    az login (az account get-access-token must succeed)
"""

import subprocess
import json
import sys
import requests
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WORKSPACE_NAME = "B2BAgg-Analytics"
PBI_BASE = "https://api.powerbi.com/v1.0/myorg"

# ---------------------------------------------------------------------------
# Dataset schema
# ---------------------------------------------------------------------------
DATASET_SCHEMA = {
    "name": "B2BAgg Market Data",
    "tables": [
        {
            "name": "SupplierOffers",
            "columns": [
                {"name": "OfferId",      "dataType": "string"},
                {"name": "RawSku",       "dataType": "string"},
                {"name": "SupplierName", "dataType": "string"},
                {"name": "ProductName",  "dataType": "string"},
                {"name": "Brand",        "dataType": "string"},
                {"name": "Model",        "dataType": "string"},
                {"name": "Width",        "dataType": "Int64"},
                {"name": "Profile",      "dataType": "Int64"},
                {"name": "Diameter",     "dataType": "Int64"},
                {"name": "Season",       "dataType": "string"},
                {"name": "Warehouse",    "dataType": "string"},
                {"name": "Region",       "dataType": "string"},
                {"name": "Stock",        "dataType": "Int64"},
                {"name": "Price",        "dataType": "Double"},
                {"name": "Year",         "dataType": "Int64"},
                {"name": "Country",      "dataType": "string"},
                {"name": "LeadDays",     "dataType": "Int64"},
                {"name": "SyncedAt",     "dataType": "DateTime"},
            ],
        },
        {
            "name": "Orders",
            "columns": [
                {"name": "OrderId",      "dataType": "string"},
                {"name": "OrderName",    "dataType": "string"},
                {"name": "TotalAmount",  "dataType": "Double"},
                {"name": "Status",       "dataType": "string"},
                {"name": "CreatedOn",    "dataType": "DateTime"},
                {"name": "LineCount",    "dataType": "Int64"},
            ],
        },
        {
            "name": "Suppliers",
            "columns": [
                {"name": "SupplierId",   "dataType": "string"},
                {"name": "SupplierName", "dataType": "string"},
                {"name": "OfferCount",   "dataType": "Int64"},
                {"name": "TotalStock",   "dataType": "Int64"},
                {"name": "AvgPrice",     "dataType": "Double"},
            ],
        },
        {
            "name": "Regions",
            "columns": [
                {"name": "RegionCode",   "dataType": "string"},
                {"name": "RegionName",   "dataType": "string"},
                {"name": "TotalStock",   "dataType": "Int64"},
                {"name": "OfferCount",   "dataType": "Int64"},
            ],
        },
    ],
}

# ---------------------------------------------------------------------------
# Mock data — 24 SupplierOffers rows
# Warehouse → Region mapping:
#   Moscow       → ЦФО   Saint Petersburg → СЗФО
#   Yekaterinburg → УрФО  Novosibirsk     → СФО
#   Kazan        → ПФО   Krasnodar        → ЮФО
# ---------------------------------------------------------------------------
SYNCED_AT = "2026-05-28T06:00:00Z"

SAMPLE_OFFERS = [
    # --- RosshinaOpt (Moscow / Kazan) ---
    {"OfferId": "off-001", "RawSku": "MPS4-22545R17", "SupplierName": "RosshinaOpt",
     "ProductName": "Michelin Pilot Sport 4 225/45 R17", "Brand": "Michelin", "Model": "Pilot Sport 4",
     "Width": 225, "Profile": 45, "Diameter": 17, "Season": "Summer",
     "Warehouse": "Moscow", "Region": "ЦФО", "Stock": 48, "Price": 127.50,
     "Year": 2023, "Country": "France", "LeadDays": 2, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-002", "RawSku": "MXM4-20555R16", "SupplierName": "RosshinaOpt",
     "ProductName": "Michelin X-Ice North 4 205/55 R16", "Brand": "Michelin", "Model": "X-Ice North 4",
     "Width": 205, "Profile": 55, "Diameter": 16, "Season": "Winter",
     "Warehouse": "Moscow", "Region": "ЦФО", "Stock": 72, "Price": 98.00,
     "Year": 2023, "Country": "France", "LeadDays": 2, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-003", "RawSku": "MEE-21560R16", "SupplierName": "RosshinaOpt",
     "ProductName": "Michelin Energy Saver 215/60 R16", "Brand": "Michelin", "Model": "Energy Saver",
     "Width": 215, "Profile": 60, "Diameter": 16, "Season": "Summer",
     "Warehouse": "Moscow", "Region": "ЦФО", "Stock": 15, "Price": 82.75,
     "Year": 2022, "Country": "France", "LeadDays": 2, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-004", "RawSku": "MPE7-22545R18", "SupplierName": "RosshinaOpt",
     "ProductName": "Michelin Primacy 4+ 225/45 R18", "Brand": "Michelin", "Model": "Primacy 4+",
     "Width": 225, "Profile": 45, "Diameter": 18, "Season": "Summer",
     "Warehouse": "Kazan", "Region": "ПФО", "Stock": 32, "Price": 141.00,
     "Year": 2024, "Country": "France", "LeadDays": 3, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-005", "RawSku": "MXM4-19565R15", "SupplierName": "RosshinaOpt",
     "ProductName": "Michelin X-Ice North 4 195/65 R15", "Brand": "Michelin", "Model": "X-Ice North 4",
     "Width": 195, "Profile": 65, "Diameter": 15, "Season": "Winter",
     "Warehouse": "Kazan", "Region": "ПФО", "Stock": 56, "Price": 88.50,
     "Year": 2023, "Country": "France", "LeadDays": 3, "SyncedAt": SYNCED_AT},

    # --- TyreCenter SPB (Saint Petersburg / Yekaterinburg) ---
    {"OfferId": "off-006", "RawSku": "CCS6-20555R16", "SupplierName": "TyreCenter SPB",
     "ProductName": "Continental ContiSportContact 6 205/55 R16", "Brand": "Continental", "Model": "ContiSportContact 6",
     "Width": 205, "Profile": 55, "Diameter": 16, "Season": "Summer",
     "Warehouse": "Saint Petersburg", "Region": "СЗФО", "Stock": 40, "Price": 115.00,
     "Year": 2023, "Country": "Germany", "LeadDays": 2, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-007", "RawSku": "CWC7-21560R16", "SupplierName": "TyreCenter SPB",
     "ProductName": "Continental WinterContact TS 870 215/60 R16", "Brand": "Continental", "Model": "WinterContact TS 870",
     "Width": 215, "Profile": 60, "Diameter": 16, "Season": "Winter",
     "Warehouse": "Saint Petersburg", "Region": "СЗФО", "Stock": 68, "Price": 102.00,
     "Year": 2023, "Country": "Germany", "LeadDays": 2, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-008", "RawSku": "CPC7-22545R17", "SupplierName": "TyreCenter SPB",
     "ProductName": "Continental PremiumContact 7 225/45 R17", "Brand": "Continental", "Model": "PremiumContact 7",
     "Width": 225, "Profile": 45, "Diameter": 17, "Season": "Summer",
     "Warehouse": "Saint Petersburg", "Region": "СЗФО", "Stock": 12, "Price": 119.90,
     "Year": 2024, "Country": "Germany", "LeadDays": 2, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-009", "RawSku": "CVC5-19565R15", "SupplierName": "TyreCenter SPB",
     "ProductName": "Continental VikingContact 7 195/65 R15", "Brand": "Continental", "Model": "VikingContact 7",
     "Width": 195, "Profile": 65, "Diameter": 15, "Season": "Winter",
     "Warehouse": "Yekaterinburg", "Region": "УрФО", "Stock": 84, "Price": 94.50,
     "Year": 2023, "Country": "Germany", "LeadDays": 4, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-010", "RawSku": "CCC5-20555R17", "SupplierName": "TyreCenter SPB",
     "ProductName": "Continental CrossContact H/T 205/55 R17", "Brand": "Continental", "Model": "CrossContact H/T",
     "Width": 205, "Profile": 55, "Diameter": 17, "Season": "Summer",
     "Warehouse": "Yekaterinburg", "Region": "УрФО", "Stock": 29, "Price": 108.00,
     "Year": 2023, "Country": "Germany", "LeadDays": 4, "SyncedAt": SYNCED_AT},

    # --- Koleso.ru (Novosibirsk / Krasnodar) ---
    {"OfferId": "off-011", "RawSku": "BT005-22545R17", "SupplierName": "Koleso.ru",
     "ProductName": "Bridgestone Turanza T005 225/45 R17", "Brand": "Bridgestone", "Model": "Turanza T005",
     "Width": 225, "Profile": 45, "Diameter": 17, "Season": "Summer",
     "Warehouse": "Novosibirsk", "Region": "СФО", "Stock": 36, "Price": 111.00,
     "Year": 2023, "Country": "Japan", "LeadDays": 5, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-012", "RawSku": "BLM005-19565R15", "SupplierName": "Koleso.ru",
     "ProductName": "Bridgestone Blizzak LM005 195/65 R15", "Brand": "Bridgestone", "Model": "Blizzak LM005",
     "Width": 195, "Profile": 65, "Diameter": 15, "Season": "Winter",
     "Warehouse": "Novosibirsk", "Region": "СФО", "Stock": 92, "Price": 86.00,
     "Year": 2023, "Country": "Japan", "LeadDays": 5, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-013", "RawSku": "BPO-21560R16", "SupplierName": "Koleso.ru",
     "ProductName": "Bridgestone Potenza Sport 215/60 R16", "Brand": "Bridgestone", "Model": "Potenza Sport",
     "Width": 215, "Profile": 60, "Diameter": 16, "Season": "Summer",
     "Warehouse": "Novosibirsk", "Region": "СФО", "Stock": 8, "Price": 123.50,
     "Year": 2024, "Country": "Japan", "LeadDays": 5, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-014", "RawSku": "BT6-22545R18", "SupplierName": "Koleso.ru",
     "ProductName": "Bridgestone Turanza 6 225/45 R18", "Brand": "Bridgestone", "Model": "Turanza 6",
     "Width": 225, "Profile": 45, "Diameter": 18, "Season": "Summer",
     "Warehouse": "Krasnodar", "Region": "ЮФО", "Stock": 44, "Price": 135.00,
     "Year": 2024, "Country": "Japan", "LeadDays": 3, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-015", "RawSku": "BLM5-20555R16", "SupplierName": "Koleso.ru",
     "ProductName": "Bridgestone Blizzak LM-5 205/55 R16", "Brand": "Bridgestone", "Model": "Blizzak LM-5",
     "Width": 205, "Profile": 55, "Diameter": 16, "Season": "Winter",
     "Warehouse": "Krasnodar", "Region": "ЮФО", "Stock": 60, "Price": 92.00,
     "Year": 2023, "Country": "Japan", "LeadDays": 3, "SyncedAt": SYNCED_AT},

    # --- Cross-supplier price comparison rows ---
    {"OfferId": "off-016", "RawSku": "CCS6-20555R16-B", "SupplierName": "RosshinaOpt",
     "ProductName": "Continental ContiSportContact 6 205/55 R16", "Brand": "Continental", "Model": "ContiSportContact 6",
     "Width": 205, "Profile": 55, "Diameter": 16, "Season": "Summer",
     "Warehouse": "Moscow", "Region": "ЦФО", "Stock": 18, "Price": 118.00,
     "Year": 2023, "Country": "Germany", "LeadDays": 2, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-017", "RawSku": "BT005-22545R17-B", "SupplierName": "TyreCenter SPB",
     "ProductName": "Bridgestone Turanza T005 225/45 R17", "Brand": "Bridgestone", "Model": "Turanza T005",
     "Width": 225, "Profile": 45, "Diameter": 17, "Season": "Summer",
     "Warehouse": "Saint Petersburg", "Region": "СЗФО", "Stock": 22, "Price": 114.50,
     "Year": 2023, "Country": "Japan", "LeadDays": 2, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-018", "RawSku": "MPS4-22545R17-B", "SupplierName": "Koleso.ru",
     "ProductName": "Michelin Pilot Sport 4 225/45 R17", "Brand": "Michelin", "Model": "Pilot Sport 4",
     "Width": 225, "Profile": 45, "Diameter": 17, "Season": "Summer",
     "Warehouse": "Krasnodar", "Region": "ЮФО", "Stock": 11, "Price": 131.00,
     "Year": 2023, "Country": "France", "LeadDays": 3, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-019", "RawSku": "MXM4-20555R16-B", "SupplierName": "TyreCenter SPB",
     "ProductName": "Michelin X-Ice North 4 205/55 R16", "Brand": "Michelin", "Model": "X-Ice North 4",
     "Width": 205, "Profile": 55, "Diameter": 16, "Season": "Winter",
     "Warehouse": "Yekaterinburg", "Region": "УрФО", "Stock": 45, "Price": 101.00,
     "Year": 2023, "Country": "France", "LeadDays": 4, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-020", "RawSku": "CVC5-19565R15-B", "SupplierName": "RosshinaOpt",
     "ProductName": "Continental VikingContact 7 195/65 R15", "Brand": "Continental", "Model": "VikingContact 7",
     "Width": 195, "Profile": 65, "Diameter": 15, "Season": "Winter",
     "Warehouse": "Moscow", "Region": "ЦФО", "Stock": 37, "Price": 97.00,
     "Year": 2023, "Country": "Germany", "LeadDays": 2, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-021", "RawSku": "BLM005-20555R16-B", "SupplierName": "TyreCenter SPB",
     "ProductName": "Bridgestone Blizzak LM005 205/55 R16", "Brand": "Bridgestone", "Model": "Blizzak LM005",
     "Width": 205, "Profile": 55, "Diameter": 16, "Season": "Winter",
     "Warehouse": "Yekaterinburg", "Region": "УрФО", "Stock": 53, "Price": 89.00,
     "Year": 2023, "Country": "Japan", "LeadDays": 4, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-022", "RawSku": "MPE7-19565R15", "SupplierName": "Koleso.ru",
     "ProductName": "Michelin Primacy 4 195/65 R15", "Brand": "Michelin", "Model": "Primacy 4",
     "Width": 195, "Profile": 65, "Diameter": 15, "Season": "Summer",
     "Warehouse": "Novosibirsk", "Region": "СФО", "Stock": 27, "Price": 95.00,
     "Year": 2024, "Country": "France", "LeadDays": 5, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-023", "RawSku": "CPC7-19565R15", "SupplierName": "Koleso.ru",
     "ProductName": "Continental PremiumContact 7 195/65 R15", "Brand": "Continental", "Model": "PremiumContact 7",
     "Width": 195, "Profile": 65, "Diameter": 15, "Season": "Summer",
     "Warehouse": "Krasnodar", "Region": "ЮФО", "Stock": 33, "Price": 107.00,
     "Year": 2024, "Country": "Germany", "LeadDays": 3, "SyncedAt": SYNCED_AT},

    {"OfferId": "off-024", "RawSku": "BPO-22545R18", "SupplierName": "RosshinaOpt",
     "ProductName": "Bridgestone Potenza Sport 225/45 R18", "Brand": "Bridgestone", "Model": "Potenza Sport",
     "Width": 225, "Profile": 45, "Diameter": 18, "Season": "Summer",
     "Warehouse": "Moscow", "Region": "ЦФО", "Stock": 19, "Price": 148.00,
     "Year": 2024, "Country": "Japan", "LeadDays": 2, "SyncedAt": SYNCED_AT},
]

SAMPLE_ORDERS = [
    {"OrderId": "ord-001", "OrderName": "ORD-2026-001", "TotalAmount": 3825.00,
     "Status": "Confirmed", "CreatedOn": "2026-05-01T09:00:00Z", "LineCount": 3},
    {"OrderId": "ord-002", "OrderName": "ORD-2026-002", "TotalAmount": 5100.00,
     "Status": "Delivered", "CreatedOn": "2026-05-05T14:30:00Z", "LineCount": 5},
    {"OrderId": "ord-003", "OrderName": "ORD-2026-003", "TotalAmount": 1270.00,
     "Status": "Draft", "CreatedOn": "2026-05-10T11:00:00Z", "LineCount": 2},
    {"OrderId": "ord-004", "OrderName": "ORD-2026-004", "TotalAmount": 7640.50,
     "Status": "Confirmed", "CreatedOn": "2026-05-15T16:00:00Z", "LineCount": 6},
    {"OrderId": "ord-005", "OrderName": "ORD-2026-005", "TotalAmount": 2550.00,
     "Status": "Delivered", "CreatedOn": "2026-05-20T08:45:00Z", "LineCount": 2},
    {"OrderId": "ord-006", "OrderName": "ORD-2026-006", "TotalAmount": 4080.00,
     "Status": "Cancelled", "CreatedOn": "2026-05-22T12:00:00Z", "LineCount": 4},
    {"OrderId": "ord-007", "OrderName": "ORD-2026-007", "TotalAmount": 9200.00,
     "Status": "Confirmed", "CreatedOn": "2026-05-27T10:00:00Z", "LineCount": 8},
]

SAMPLE_SUPPLIERS = [
    {"SupplierId": "sup-001", "SupplierName": "RosshinaOpt",
     "OfferCount": 8, "TotalStock": 285, "AvgPrice": 110.34},
    {"SupplierId": "sup-002", "SupplierName": "TyreCenter SPB",
     "OfferCount": 9, "TotalStock": 371, "AvgPrice": 105.43},
    {"SupplierId": "sup-003", "SupplierName": "Koleso.ru",
     "OfferCount": 7, "TotalStock": 273, "AvgPrice": 106.93},
]

SAMPLE_REGIONS = [
    {"RegionCode": "CFO",  "RegionName": "ЦФО",  "TotalStock": 252, "OfferCount": 8},
    {"RegionCode": "SZFO", "RegionName": "СЗФО", "TotalStock": 142, "OfferCount": 5},
    {"RegionCode": "UFO",  "RegionName": "УрФО", "TotalStock": 211, "OfferCount": 4},
    {"RegionCode": "SFO",  "RegionName": "СФО",  "TotalStock": 163, "OfferCount": 4},
    {"RegionCode": "PFO",  "RegionName": "ПФО",  "TotalStock": 88,  "OfferCount": 2},
    {"RegionCode": "YUFO", "RegionName": "ЮФО",  "TotalStock": 148, "OfferCount": 5},
]

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
def get_pbi_token() -> str:
    result = subprocess.run(
        [
            "az", "account", "get-access-token",
            "--resource", "https://analysis.windows.net/powerbi/api",
            "--query", "accessToken",
            "-o", "tsv",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def pbi_get(token: str, path: str) -> dict:
    r = requests.get(
        f"{PBI_BASE}/{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def pbi_post(token: str, path: str, body: dict) -> dict:
    r = requests.post(
        f"{PBI_BASE}/{path}",
        json=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    if r.status_code == 409:
        # Already exists — return empty dict, caller handles
        return {"__conflict": True}
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Acquiring Power BI token …")
    token = get_pbi_token()
    print(f"  Token acquired ({len(token)} chars)")

    # ------------------------------------------------------------------
    # 1. Workspace
    # ------------------------------------------------------------------
    print(f"\nChecking workspace '{WORKSPACE_NAME}' …")
    groups = pbi_get(token, "groups")["value"]
    existing = next((g for g in groups if g["name"] == WORKSPACE_NAME), None)

    if existing:
        group_id = existing["id"]
        print(f"  Already exists: {group_id}")
    else:
        result = pbi_post(token, "groups?workspaceV2=True", {"name": WORKSPACE_NAME})
        if result.get("__conflict"):
            # Race or already there — re-fetch
            groups = pbi_get(token, "groups")["value"]
            existing = next((g for g in groups if g["name"] == WORKSPACE_NAME), None)
            group_id = existing["id"]
            print(f"  Found after conflict: {group_id}")
        else:
            group_id = result["id"]
            print(f"  Created: {group_id}")

    # ------------------------------------------------------------------
    # 2. Dataset
    # ------------------------------------------------------------------
    print(f"\nChecking dataset '{DATASET_SCHEMA['name']}' …")
    datasets = pbi_get(token, f"groups/{group_id}/datasets")["value"]
    existing_ds = next(
        (d for d in datasets if d["name"] == DATASET_SCHEMA["name"]), None
    )

    if existing_ds:
        dataset_id = existing_ds["id"]
        print(f"  Already exists: {dataset_id}")
    else:
        payload = {**DATASET_SCHEMA, "defaultMode": "Push"}
        result = pbi_post(token, f"groups/{group_id}/datasets", payload)
        if result.get("__conflict"):
            datasets = pbi_get(token, f"groups/{group_id}/datasets")["value"]
            existing_ds = next(
                (d for d in datasets if d["name"] == DATASET_SCHEMA["name"]), None
            )
            dataset_id = existing_ds["id"]
            print(f"  Found after conflict: {dataset_id}")
        else:
            dataset_id = result["id"]
            print(f"  Created: {dataset_id}")

    # ------------------------------------------------------------------
    # 3. Push rows
    # ------------------------------------------------------------------
    table_data = {
        "SupplierOffers": SAMPLE_OFFERS,
        "Orders":         SAMPLE_ORDERS,
        "Suppliers":      SAMPLE_SUPPLIERS,
        "Regions":        SAMPLE_REGIONS,
    }

    print("\nPushing data rows …")
    for table_name, rows in table_data.items():
        path = f"groups/{group_id}/datasets/{dataset_id}/tables/{table_name}/rows"
        pbi_post(token, path, {"rows": rows})
        print(f"  {table_name}: {len(rows)} rows pushed")

    # ------------------------------------------------------------------
    # 4. Summary
    # ------------------------------------------------------------------
    workspace_url = f"https://app.powerbi.com/groups/{group_id}"

    print("\n" + "=" * 60)
    print("=== Power BI Setup Complete ===")
    print(f"Workspace:    {WORKSPACE_NAME}")
    print(f"Workspace ID: {group_id}")
    print(f"Dataset:      {DATASET_SCHEMA['name']}")
    print(f"Dataset ID:   {dataset_id}")
    print(f"App URL:      {workspace_url}")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 5. Emit IDs as JSON for CI / downstream scripts
    # ------------------------------------------------------------------
    output = {
        "workspace_name": WORKSPACE_NAME,
        "workspace_id": group_id,
        "workspace_url": workspace_url,
        "dataset_name": DATASET_SCHEMA["name"],
        "dataset_id": dataset_id,
    }
    with open("powerbi/workspace-ids.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nIDs saved to powerbi/workspace-ids.json")


if __name__ == "__main__":
    main()
