#!/usr/bin/env python3
"""
create-marketsignal-table.py
============================
Stage 4 prerequisite: creates b2b_marketsignal — the table the
**Stock Redistribution Advisor** flow writes into (type=RedistributionAdvice),
also reused by Low Stock / demand signals. Visible in MDA + Power BI.

Idempotent; uses an az-CLI token (an account with Dataverse privileges).
Mirrors the metadata builders in scripts/create-matching-tables.py.

What it does:
  1. Creates b2b_marketsignal:
       b2b_name (primary), choice b2b_type, choice b2b_severity,
       memo b2b_aisummary, string b2b_source.
  2. Adds 3 lookups:
       b2b_region            -> b2b_region          (affected district)
       b2b_targetregion      -> b2b_region          (suggested source district)
       b2b_canonicalproduct  -> b2b_canonicalproduct (specific SKU, nullable)
  3. Adds the entity to B2BAgg_Core (subcomponents included).
  4. Best-effort: a saved view "Active Redistribution Advice".

Usage:
    # az must be logged in as <admin-upn>
    python3 scripts/create-marketsignal-table.py
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
OPT = 10000  # publisher option-value prefix


# ── Auth ────────────────────────────────────────────────────────────────────────

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


# ── Metadata builders (mirror create-matching-tables.py) ─────────────────────────

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


# ── Web API helpers ──────────────────────────────────────────────────────────────

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
    md = s.get(f"{API}/EntityDefinitions(LogicalName='{logical_name}')", params={"$select": "MetadataId"})
    if md.status_code != 200:
        log.warning("  %s: metadata lookup failed (%s) — skip", logical_name, md.status_code); return
    body = {"ComponentId": md.json()["MetadataId"], "ComponentType": 1,  # 1 = Entity
            "SolutionUniqueName": SOLUTION,
            "AddRequiredComponents": False, "DoNotIncludeSubcomponents": False}
    r = s.post(f"{API}/AddSolutionComponent", json=body)
    if r.status_code in (200, 204):
        log.info("  + %s -> %s", logical_name, SOLUTION)
    else:
        log.info("  %s -> %s: %s %s", logical_name, SOLUTION, r.status_code, r.text[:160])


# ── Saved view (best-effort) ─────────────────────────────────────────────────────

REDIST_FETCHXML = (
    "<fetch version='1.0' mapping='logical' no-lock='true'>"
    "<entity name='b2b_marketsignal'>"
    "<attribute name='b2b_name'/><attribute name='b2b_type'/>"
    "<attribute name='b2b_severity'/><attribute name='b2b_region'/>"
    "<attribute name='b2b_targetregion'/><attribute name='b2b_canonicalproduct'/>"
    "<attribute name='createdon'/>"
    f"<filter type='and'><condition attribute='b2b_type' operator='eq' value='{OPT + 3}'/></filter>"
    "<order attribute='createdon' descending='true'/>"
    "</entity></fetch>"
)
REDIST_LAYOUTXML = (
    "<grid name='resultset' object='10000' jump='b2b_name' select='1' icon='1' preview='1'>"
    "<row name='result' id='b2b_marketsignalid'>"
    "<cell name='b2b_name' width='200'/><cell name='b2b_severity' width='100'/>"
    "<cell name='b2b_region' width='160'/><cell name='b2b_targetregion' width='160'/>"
    "<cell name='b2b_canonicalproduct' width='200'/><cell name='createdon' width='140'/>"
    "</row></grid>"
)


def create_redist_view(s) -> None:
    """querytype=0 (public view). Best-effort; warns on failure."""
    existing = s.get(f"{API}/savedqueries",
                     params={"$select": "savedqueryid", "$filter":
                             "name eq 'Active Redistribution Advice' and returnedtypecode eq 'b2b_marketsignal'"})
    if existing.status_code == 200 and existing.json().get("value"):
        log.info("  view 'Active Redistribution Advice' exists — skip"); return
    body = {"name": "Active Redistribution Advice", "description":
            "Redistribution advisories raised by the Stock Redistribution Advisor flow.",
            "returnedtypecode": "b2b_marketsignal", "querytype": 0,
            "fetchxml": REDIST_FETCHXML, "layoutxml": REDIST_LAYOUTXML}
    r = s.post(f"{API}/savedqueries", json=body)
    if r.status_code in (200, 201, 204):
        log.info("  + view 'Active Redistribution Advice'")
    else:
        log.warning("  view could not be created via API (%s: %s). Build it in the MDA designer.",
                    r.status_code, r.text[:200])


# ── Main ─────────────────────────────────────────────────────────────────────────

TYPE_OPTS = [
    (OPT + 0, "DemandSpike"), (OPT + 1, "Seasonal"),
    (OPT + 2, "StockShortage"), (OPT + 3, "RedistributionAdvice"),
]
SEVERITY_OPTS = [
    (OPT + 0, "Info"), (OPT + 1, "Warning"), (OPT + 2, "Critical"),
]


def main() -> None:
    log.info("B2BAgg market-signal creator — %s", DV_URL)
    s = make_session(get_token())
    who = s.get(f"{API}/WhoAmI")
    if who.status_code != 200:
        log.error("WhoAmI failed: %s %s — is az logged in with Dataverse privileges?",
                  who.status_code, who.text[:200]); sys.exit(1)
    log.info("Authenticated UserId=%s", who.json().get("UserId"))

    ent = "b2b_marketsignal"
    if not entity_exists(s, ent):
        create_entity(s, _base_entity(
            ent, "Market Signal", "Market Signals",
            "Aggregated demand / competitive / redistribution signal for platform-owner "
            "analytics. RedistributionAdvice rows are raised by the Stock Redistribution "
            "Advisor flow (Stage 4).", primary_len=300, primary_required=False))
        time.sleep(3)  # metadata propagation before columns/lookups
    else:
        log.info("%s exists — skip create", ent)

    add_attr(s, ent, picklist_attr("b2b_type", "Type", TYPE_OPTS,
             "DemandSpike / Seasonal / StockShortage / RedistributionAdvice."))
    add_attr(s, ent, picklist_attr("b2b_severity", "Severity", SEVERITY_OPTS,
             "Info / Warning / Critical — set by the generating logic from the gap size."))
    add_attr(s, ent, memo_attr("b2b_aisummary", "AI Summary",
             description="Optional human-readable summary of the signal."))
    add_attr(s, ent, string_attr("b2b_source", "Source", 100,
             description="Which signal source generated it, e.g. 'Stock Redistribution Advisor'."))

    time.sleep(2)
    add_lookup(s, "b2b_marketsignal_b2b_region", ent, "b2b_region",
               "Region", "b2b_region")
    add_lookup(s, "b2b_marketsignal_b2b_targetregion", ent, "b2b_targetregion",
               "Target Region", "b2b_region")
    add_lookup(s, "b2b_marketsignal_b2b_canonicalproduct", ent, "b2b_canonicalproduct",
               "Canonical Product", "b2b_canonicalproduct")

    log.info("Adding %s to %s …", ent, SOLUTION)
    time.sleep(2)
    add_entity_to_solution(s, ent)

    log.info("Creating saved view …")
    create_redist_view(s)

    log.info("Done. Next: build the Stock Redistribution Advisor flow, "
             "then pac solution export %s.", SOLUTION)


if __name__ == "__main__":
    main()
