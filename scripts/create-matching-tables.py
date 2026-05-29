#!/usr/bin/env python3
"""
create-matching-tables.py
=========================
Creates / extends the Dataverse schema for the SKU Resolution Engine (MVP2).
Idempotent; uses an az-CLI token (no MSAL / device code — see PROGRESS QUIRK #1).

What it does:
  1. Adds homologation columns to b2b_canonicalproduct:
       b2b_homologation (local picklist), b2b_runflat (bool), b2b_extraload (bool),
       b2b_canonical_key (string 200)
  2. Creates b2b_skumap — the memo base (supplier + raw_sku → canonical):
       b2b_raw_sku, b2b_normalized_key, b2b_match_method (picklist),
       b2b_confidence (decimal), b2b_last_seen (datetime)
       + lookups b2b_supplier, b2b_canonical_product
       + alternate key (b2b_supplier + b2b_raw_sku) for idempotent upsert
  3. Creates b2b_dataconflict — the admin review queue:
       b2b_raw_name, b2b_raw_sku, b2b_ai_confidence (decimal),
       b2b_candidates_json (memo), b2b_status (picklist)
       + lookups b2b_supplier_offer, b2b_suggested_canonical, b2b_reviewed_by(systemuser)
  4. Adds b2b_match_method (picklist) + b2b_match_confidence (decimal) to b2b_supplieroffer.

Usage:
    # az must be logged in as <admin-upn>
    python3 scripts/create-matching-tables.py
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from typing import Any

import requests

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

DV_URL = "https://YOUR-DATAVERSE-ORG.crm.dynamics.com"
API = f"{DV_URL}/api/data/v9.2"
OPT = 10000  # publisher option-value prefix


# ── Auth ────────────────────────────────────────────────────────────────────────

def get_token() -> str:
    r = subprocess.run(
        ["az", "account", "get-access-token", "--resource", DV_URL,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, timeout=30,
    )
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


# ── Metadata builders (mirrors scripts/create-tables-api.py) ─────────────────────

def _lbl(t: str, lang: int = 1033) -> dict:
    return {"LocalizedLabels": [{"Label": t, "LanguageCode": lang}],
            "UserLocalizedLabel": {"Label": t, "LanguageCode": lang}}


def string_attr(ln, dn, max_length, required=False, description="", format_="Text"):
    return {"@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
            "LogicalName": ln, "SchemaName": ln, "DisplayName": _lbl(dn),
            "Description": _lbl(description),
            "RequiredLevel": {"Value": "ApplicationRequired" if required else "None"},
            "MaxLength": max_length, "Format": format_, "IsPrimaryName": False}


def memo_attr(ln, dn, max_length=4000, description=""):
    return {"@odata.type": "Microsoft.Dynamics.CRM.MemoAttributeMetadata",
            "LogicalName": ln, "SchemaName": ln, "DisplayName": _lbl(dn),
            "Description": _lbl(description), "RequiredLevel": {"Value": "None"},
            "MaxLength": max_length, "Format": "TextArea"}


def decimal_attr(ln, dn, min_val, max_val, precision, description=""):
    return {"@odata.type": "Microsoft.Dynamics.CRM.DecimalAttributeMetadata",
            "LogicalName": ln, "SchemaName": ln, "DisplayName": _lbl(dn),
            "Description": _lbl(description), "RequiredLevel": {"Value": "None"},
            "MinValue": min_val, "MaxValue": max_val, "Precision": precision}


def datetime_attr(ln, dn, description=""):
    return {"@odata.type": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata",
            "LogicalName": ln, "SchemaName": ln, "DisplayName": _lbl(dn),
            "Description": _lbl(description), "RequiredLevel": {"Value": "None"},
            "Format": "DateAndTime", "DateTimeBehavior": {"Value": "UserLocal"}}


def bool_attr(ln, dn, default_value=False, description=""):
    return {"@odata.type": "Microsoft.Dynamics.CRM.BooleanAttributeMetadata",
            "LogicalName": ln, "SchemaName": ln, "DisplayName": _lbl(dn),
            "Description": _lbl(description), "RequiredLevel": {"Value": "None"},
            "DefaultValue": default_value,
            "OptionSet": {"TrueOption": {"Value": 1, "Label": _lbl("Yes")},
                          "FalseOption": {"Value": 0, "Label": _lbl("No")}}}


def picklist_attr(ln, dn, options: list[tuple[int, str]], description=""):
    return {"@odata.type": "Microsoft.Dynamics.CRM.PicklistAttributeMetadata",
            "LogicalName": ln, "SchemaName": ln, "DisplayName": _lbl(dn),
            "Description": _lbl(description), "RequiredLevel": {"Value": "None"},
            "OptionSet": {"@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata",
                          "IsGlobal": False, "OptionSetType": "Picklist",
                          "Options": [{"Value": v, "Label": _lbl(l), "Description": _lbl("")}
                                      for v, l in options]}}


def _base_entity(ln, dn, plural, description, primary="b2b_name",
                 primary_display="Name", primary_len=300, primary_required=False):
    return {"@odata.type": "Microsoft.Dynamics.CRM.EntityMetadata",
            "LogicalName": ln, "SchemaName": ln, "DisplayName": _lbl(dn),
            "DisplayCollectionName": _lbl(plural), "Description": _lbl(description),
            "OwnershipType": "UserOwned", "IsActivity": False, "HasActivities": False,
            "HasNotes": False, "IsAuditEnabled": {"Value": True},
            "PrimaryNameAttribute": primary,
            "Attributes": [{"@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
                            "LogicalName": primary, "SchemaName": primary,
                            "DisplayName": _lbl(primary_display), "Description": _lbl(""),
                            "RequiredLevel": {"Value": "ApplicationRequired" if primary_required else "Recommended"},
                            "MaxLength": primary_len, "Format": "Text", "IsPrimaryName": True}]}


# ── Web API helpers ───────────────────────────────────────────────────────────────

def entity_exists(s, ln) -> bool:
    r = s.get(f"{API}/EntityDefinitions(LogicalName='{ln}')", params={"$select": "LogicalName"})
    return r.status_code == 200


def attribute_exists(s, ent, attr) -> bool:
    r = s.get(f"{API}/EntityDefinitions(LogicalName='{ent}')/Attributes(LogicalName='{attr}')",
              params={"$select": "LogicalName"})
    return r.status_code == 200


def relationship_exists(s, schema) -> bool:
    r = s.get(f"{API}/RelationshipDefinitions(SchemaName='{schema}')", params={"$select": "SchemaName"})
    return r.status_code == 200


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


def add_alternate_key(s, ent, schema, display, key_attrs: list[str]) -> None:
    """Create a composite alternate key (async). Best-effort; logs a manual fallback."""
    # check existing
    r = s.get(f"{API}/EntityDefinitions(LogicalName='{ent}')/Keys", params={"$select": "SchemaName"})
    if r.status_code == 200 and any(k.get("SchemaName") == schema for k in r.json().get("value", [])):
        log.info("  alt key %s exists — skip", schema); return
    payload = {"@odata.type": "Microsoft.Dynamics.CRM.EntityKeyMetadata",
               "SchemaName": schema, "LogicalName": schema.lower(),
               "DisplayName": _lbl(display), "KeyAttributes": key_attrs}
    r = s.post(f"{API}/EntityDefinitions(LogicalName='{ent}')/Keys", json=payload)
    if r.status_code in (200, 201, 204):
        log.info("  alt key %s requested (async index build)", schema)
    else:
        log.warning("  alt key %s could not be created via API (%s). "
                    "Create manually in Maker Portal: %s on (%s).",
                    schema, r.status_code, ent, ", ".join(key_attrs))


# ── Schema operations ─────────────────────────────────────────────────────────────

HOMOLOGATION_OPTS = [
    (OPT + 0, "None"), (OPT + 1, "Star_BMW"), (OPT + 2, "MO_Mercedes"),
    (OPT + 3, "MOE_Mercedes"), (OPT + 4, "N0_Porsche"), (OPT + 5, "N1_Porsche"),
    (OPT + 6, "AO_Audi"), (OPT + 7, "LR_LandRover"), (OPT + 8, "VOL_Volvo"),
    (OPT + 9, "MGT_Maserati"),
]
MATCH_METHOD_OPTS = [
    (OPT + 0, "Cache"), (OPT + 1, "ExactKey"), (OPT + 2, "Fuzzy"),
    (OPT + 3, "AI"), (OPT + 4, "Manual"),
]
CONFLICT_STATUS_OPTS = [
    (OPT + 0, "Pending"), (OPT + 1, "NeedsReview"), (OPT + 2, "NewCandidate"),
    (OPT + 3, "Approved"), (OPT + 4, "Rejected"), (OPT + 5, "AutoResolved"),
]


def extend_canonicalproduct(s) -> None:
    log.info("Extending b2b_canonicalproduct …")
    ent = "b2b_canonicalproduct"
    add_attr(s, ent, picklist_attr("b2b_homologation", "Homologation", HOMOLOGATION_OPTS,
             "OEM approval marker (*, MO, N0, LR…). Part of the canonical key — a mismatch is a different product."))
    add_attr(s, ent, bool_attr("b2b_runflat", "Run-Flat", False,
             "Run-flat construction. Price-defining discriminator."))
    add_attr(s, ent, bool_attr("b2b_extraload", "Extra Load (XL)", False))
    add_attr(s, ent, string_attr("b2b_canonical_key", "Canonical Key", 200,
             description="brand|model|W|P|D|load|speed|homolog|runflat|xl — computed by sku_matcher."))


def create_skumap(s) -> None:
    log.info("Creating b2b_skumap (memo base) …")
    ent = "b2b_skumap"
    if not entity_exists(s, ent):
        create_entity(s, _base_entity(ent, "SKU Map", "SKU Map",
                      "Memo base: a once-matched (supplier, raw SKU) resolves to the same canonical forever after.",
                      primary_len=300, primary_required=False))
    add_attr(s, ent, string_attr("b2b_raw_sku", "Raw SKU", 200, description="Supplier's internal SKU."))
    add_attr(s, ent, string_attr("b2b_normalized_key", "Normalized Key", 200))
    add_attr(s, ent, picklist_attr("b2b_match_method", "Match Method", MATCH_METHOD_OPTS))
    add_attr(s, ent, decimal_attr("b2b_confidence", "Confidence", 0.0, 1.0, 4))
    add_attr(s, ent, datetime_attr("b2b_last_seen", "Last Seen"))


def create_dataconflict(s) -> None:
    log.info("Creating b2b_dataconflict (review queue) …")
    ent = "b2b_dataconflict"
    if not entity_exists(s, ent):
        create_entity(s, _base_entity(ent, "Data Conflict", "Data Conflicts",
                      "Low-confidence / ambiguous / new-product matches awaiting admin approval.",
                      primary_len=300, primary_required=False))
    add_attr(s, ent, string_attr("b2b_raw_name", "Raw Supplier Name", 500))
    add_attr(s, ent, string_attr("b2b_raw_sku", "Raw SKU", 200))
    add_attr(s, ent, decimal_attr("b2b_ai_confidence", "AI Confidence", 0.0, 1.0, 4))
    add_attr(s, ent, memo_attr("b2b_candidates_json", "Candidates (JSON)", 8000,
             "Top-K ranked candidates returned by the matcher, for the reviewer."))
    add_attr(s, ent, picklist_attr("b2b_status", "Status", CONFLICT_STATUS_OPTS))


def extend_supplieroffer(s) -> None:
    log.info("Extending b2b_supplieroffer …")
    ent = "b2b_supplieroffer"
    add_attr(s, ent, picklist_attr("b2b_match_method", "Match Method", MATCH_METHOD_OPTS))
    add_attr(s, ent, decimal_attr("b2b_match_confidence", "Match Confidence", 0.0, 1.0, 4))


def create_lookups(s) -> None:
    log.info("Creating lookups …")
    add_lookup(s, "b2b_skumap_b2b_supplier", "b2b_skumap", "b2b_supplier", "Supplier", "b2b_supplier", required=True)
    add_lookup(s, "b2b_skumap_b2b_canonicalproduct", "b2b_skumap", "b2b_canonical_product",
               "Canonical Product", "b2b_canonicalproduct", required=True)
    add_lookup(s, "b2b_dataconflict_b2b_supplieroffer", "b2b_dataconflict", "b2b_supplier_offer",
               "Supplier Offer", "b2b_supplieroffer", required=False)
    add_lookup(s, "b2b_dataconflict_b2b_canonicalproduct", "b2b_dataconflict", "b2b_suggested_canonical",
               "Suggested Canonical", "b2b_canonicalproduct", required=False)
    add_lookup(s, "b2b_dataconflict_systemuser_reviewed", "b2b_dataconflict", "b2b_reviewed_by",
               "Reviewed By", "systemuser", required=False)


def main() -> None:
    log.info("B2BAgg matching-tables creator — %s", DV_URL)
    s = make_session(get_token())
    r = s.get(f"{API}/WhoAmI")
    if r.status_code != 200:
        log.error("WhoAmI failed: %s %s", r.status_code, r.text[:200]); sys.exit(1)
    log.info("Authenticated UserId=%s", r.json().get("UserId"))

    extend_canonicalproduct(s)
    create_skumap(s)
    create_dataconflict(s)
    extend_supplieroffer(s)

    # lookups require the new entities to exist; small delay for metadata propagation
    time.sleep(3)
    create_lookups(s)

    # alt key for idempotent upsert (supplier + raw_sku) — async index build
    time.sleep(3)
    add_alternate_key(s, "b2b_skumap", "b2b_skumap_supplier_rawsku",
                      "Supplier + Raw SKU", ["b2b_supplier", "b2b_raw_sku"])

    log.info("Done. Next: re-run seed (python3 scripts/seed-via-az-token.py after extending it),")
    log.info("then export solution + unpack into solutions/B2BAgg.Core/src.")


if __name__ == "__main__":
    main()
