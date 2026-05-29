#!/usr/bin/env python3
"""
create-warehouse-table.py
=========================
Adds the warehouse grain to the B2BAgg model (audit M-4) and makes the whole
b2b_ schema a member of the B2BAgg_Core solution so `pac solution export`
captures it (audit H-3 / P2-1).

Idempotent; uses an az-CLI token (no MSAL / device code — see PROGRESS QUIRK #1).

What it does:
  1. Creates b2b_warehouse:
       b2b_name (primary), b2b_code (string), b2b_city (string),
       b2b_capacity (int) + lookup b2b_region (warehouse -> region)
  2. Adds lookup b2b_warehouse on b2b_supplieroffer (offer -> warehouse).
     (b2b_warehouse_city text is kept as a denormalized cache.)
  3. Adds EVERY b2b_ entity (incl. the SKU-engine tables created earlier
     outside any solution) to the B2BAgg_Core solution, with subcomponents,
     so the export is the source of truth again.

Usage:
    # az must be logged in as <admin-upn>
    python3 scripts/create-warehouse-table.py
"""
from __future__ import annotations

import logging
import subprocess
import sys
import time

import requests

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

DV_URL = "https://YOUR-DATAVERSE-ORG.crm.dynamics.com"
API = f"{DV_URL}/api/data/v9.2"
SOLUTION = "B2BAgg_Core"


def get_token() -> str:
    r = subprocess.run(["az", "account", "get-access-token", "--resource", DV_URL,
                        "--query", "accessToken", "-o", "tsv"],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"az get-access-token failed: {r.stderr}")
    return r.stdout.strip()


def make_session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {token}",
        "OData-MaxVersion": "4.0", "OData-Version": "4.0",
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "Prefer": "return=representation",
    })
    return s


def _lbl(t: str, lang: int = 1033) -> dict:
    return {"LocalizedLabels": [{"Label": t, "LanguageCode": lang}],
            "UserLocalizedLabel": {"Label": t, "LanguageCode": lang}}


def string_attr(ln, dn, max_length, required=False, description=""):
    return {"@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
            "LogicalName": ln, "SchemaName": ln, "DisplayName": _lbl(dn),
            "Description": _lbl(description),
            "RequiredLevel": {"Value": "ApplicationRequired" if required else "None"},
            "MaxLength": max_length, "Format": "Text", "IsPrimaryName": False}


def int_attr(ln, dn, min_val=0, max_val=1000000000, description=""):
    return {"@odata.type": "Microsoft.Dynamics.CRM.IntegerAttributeMetadata",
            "LogicalName": ln, "SchemaName": ln, "DisplayName": _lbl(dn),
            "Description": _lbl(description), "RequiredLevel": {"Value": "None"},
            "MinValue": min_val, "MaxValue": max_val, "Format": "None"}


def _base_entity(ln, dn, plural, description, primary="b2b_name",
                 primary_display="Name", primary_len=300):
    return {"@odata.type": "Microsoft.Dynamics.CRM.EntityMetadata",
            "LogicalName": ln, "SchemaName": ln, "DisplayName": _lbl(dn),
            "DisplayCollectionName": _lbl(plural), "Description": _lbl(description),
            "OwnershipType": "UserOwned", "IsActivity": False, "HasActivities": False,
            "HasNotes": False, "IsAuditEnabled": {"Value": True},
            "PrimaryNameAttribute": primary,
            "Attributes": [{"@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
                            "LogicalName": primary, "SchemaName": primary,
                            "DisplayName": _lbl(primary_display), "Description": _lbl(""),
                            "RequiredLevel": {"Value": "Recommended"},
                            "MaxLength": primary_len, "Format": "Text", "IsPrimaryName": True}]}


def entity_exists(s, ln) -> bool:
    return s.get(f"{API}/EntityDefinitions(LogicalName='{ln}')",
                 params={"$select": "LogicalName"}).status_code == 200


def attribute_exists(s, ent, attr) -> bool:
    return s.get(f"{API}/EntityDefinitions(LogicalName='{ent}')/Attributes(LogicalName='{attr}')",
                 params={"$select": "LogicalName"}).status_code == 200


def relationship_exists(s, schema) -> bool:
    return s.get(f"{API}/RelationshipDefinitions(SchemaName='{schema}')",
                 params={"$select": "SchemaName"}).status_code == 200


def create_entity(s, payload) -> None:
    r = s.post(f"{API}/EntityDefinitions", json=payload)
    if r.status_code not in (200, 201):
        log.error("Entity create failed: %s %s", r.status_code, r.text[:500]); r.raise_for_status()
    log.info("  created entity %s", payload["LogicalName"])


def add_attr(s, ent, payload) -> None:
    name = payload["LogicalName"]
    if attribute_exists(s, ent, name):
        log.info("    attr %s exists — skip", name); return
    r = s.post(f"{API}/EntityDefinitions(LogicalName='{ent}')/Attributes", json=payload)
    if r.status_code not in (200, 201):
        log.error("    attr %s failed: %s %s", name, r.status_code, r.text[:400]); r.raise_for_status()
    log.info("    + %s", name)


def add_lookup(s, schema, referencing, attr, display, referenced, required=False) -> None:
    if relationship_exists(s, schema):
        log.info("  rel %s exists — skip", schema); return
    payload = {"@odata.type": "Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata",
               "SchemaName": schema, "ReferencedEntity": referenced, "ReferencingEntity": referencing,
               "Lookup": {"@odata.type": "Microsoft.Dynamics.CRM.LookupAttributeMetadata",
                          "LogicalName": attr, "SchemaName": attr, "DisplayName": _lbl(display),
                          "RequiredLevel": {"Value": "ApplicationRequired" if required else "None"}},
               "AssociatedMenuConfiguration": {"Behavior": "UseCollectionName", "Group": "Details", "Order": 10000},
               "CascadeConfiguration": {"Assign": "NoCascade", "Delete": "RemoveLink", "Merge": "NoCascade",
                                        "Reparent": "NoCascade", "Share": "NoCascade", "Unshare": "NoCascade"}}
    r = s.post(f"{API}/RelationshipDefinitions", json=payload)
    if r.status_code not in (200, 201):
        log.error("  rel %s failed: %s %s", schema, r.status_code, r.text[:400]); r.raise_for_status()
    log.info("  created relationship %s", schema)


def add_entity_to_solution(s, logical_name) -> None:
    """Add an entity (with its subcomponents) to the B2BAgg_Core solution. Idempotent."""
    md = s.get(f"{API}/EntityDefinitions(LogicalName='{logical_name}')",
               params={"$select": "MetadataId"})
    if md.status_code != 200:
        log.warning("  %s: metadata lookup failed (%s) — skip", logical_name, md.status_code); return
    component_id = md.json()["MetadataId"]
    body = {"ComponentId": component_id, "ComponentType": 1,  # 1 = Entity
            "SolutionUniqueName": SOLUTION,
            "AddRequiredComponents": False, "DoNotIncludeSubcomponents": False}
    r = s.post(f"{API}/AddSolutionComponent", json=body)
    if r.status_code in (200, 204):
        log.info("  + %s -> %s", logical_name, SOLUTION)
    else:
        # already a member or benign race — log and continue
        log.info("  %s -> %s: %s %s", logical_name, SOLUTION, r.status_code, r.text[:160])


B2B_ENTITIES = [
    "b2b_region", "b2b_supplier", "b2b_canonicalproduct", "b2b_supplieroffer",
    "b2b_order", "b2b_orderline", "b2b_rfq", "b2b_skumap", "b2b_dataconflict",
    "b2b_warehouse",
]


def main() -> None:
    log.info("B2BAgg warehouse creator + solution-membership fixer — %s", DV_URL)
    s = make_session(get_token())
    who = s.get(f"{API}/WhoAmI")
    if who.status_code != 200:
        log.error("WhoAmI failed: %s %s", who.status_code, who.text[:200]); sys.exit(1)
    log.info("Authenticated UserId=%s", who.json().get("UserId"))

    # 1. warehouse entity
    if not entity_exists(s, "b2b_warehouse"):
        create_entity(s, _base_entity(
            "b2b_warehouse", "Warehouse", "Warehouses",
            "Physical stocking location. Carries the region grain for district/warehouse analytics "
            "and the Stock Redistribution Advisor.", primary_len=200))
        time.sleep(3)  # metadata propagation before adding columns/lookups
    else:
        log.info("b2b_warehouse exists — skip create")

    add_attr(s, "b2b_warehouse", string_attr("b2b_code", "Warehouse Code", 20,
             description="Short code, e.g. MSK-DC1."))
    add_attr(s, "b2b_warehouse", string_attr("b2b_city", "City", 100))
    add_attr(s, "b2b_warehouse", int_attr("b2b_capacity", "Capacity (units)",
             description="Nominal storage capacity in units — feeds the redistribution advisor."))

    # 2. lookups
    time.sleep(2)
    add_lookup(s, "b2b_warehouse_b2b_region", "b2b_warehouse", "b2b_region",
               "Region", "b2b_region", required=False)
    add_lookup(s, "b2b_supplieroffer_b2b_warehouse", "b2b_supplieroffer", "b2b_warehouse",
               "Warehouse", "b2b_warehouse", required=False)

    # 3. solution membership for the whole schema (the H-3 fix)
    log.info("Ensuring all b2b_ entities are members of %s …", SOLUTION)
    time.sleep(2)
    for ent in B2B_ENTITIES:
        add_entity_to_solution(s, ent)

    log.info("Done. Next: pac solution export %s + unpack into solutions/B2BAgg.Core/src.", SOLUTION)


if __name__ == "__main__":
    main()
