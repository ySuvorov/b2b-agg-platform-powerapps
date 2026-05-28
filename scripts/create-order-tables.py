#!/usr/bin/env python3
"""
create-order-tables.py
======================
Creates 3 additional B2BAgg Dataverse tables via the Web API:
  - b2b_order
  - b2b_orderline
  - b2b_rfq

Auth: uses `az account get-access-token` (no MSAL, no device code).

Run:
  python3 scripts/create-order-tables.py

Requirements:
  pip install requests
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from typing import Any

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DATAVERSE_URL = "https://YOUR-DATAVERSE-ORG.crm.dynamics.com"
API_VERSION = "v9.2"
API_BASE = f"{DATAVERSE_URL}/api/data/{API_VERSION}"

OPTION_PREFIX = 100000000  # publisher option value prefix for b2b_ choices


# ──────────────────────────────────────────────────────────────────────────────
# Authentication
# ──────────────────────────────────────────────────────────────────────────────

def get_token() -> str:
    """Get Dataverse access token via az CLI."""
    result = subprocess.run(
        [
            "az", "account", "get-access-token",
            "--resource", DATAVERSE_URL,
            "--query", "accessToken",
            "-o", "tsv",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    token = result.stdout.strip()
    if not token:
        raise RuntimeError("Empty token returned from az CLI")
    log.info("Token acquired via az CLI.")
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


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _lbl(text: str, lang: int = 1033) -> dict:
    return {
        "LocalizedLabels": [{"Label": text, "LanguageCode": lang}],
        "UserLocalizedLabel": {"Label": text, "LanguageCode": lang},
    }


def entity_exists(session: requests.Session, logical_name: str) -> tuple[bool, str]:
    """Return (exists, MetadataId). MetadataId is '' when not found."""
    url = f"{API_BASE}/EntityDefinitions(LogicalName='{logical_name}')"
    r = session.get(url, params={"$select": "LogicalName,MetadataId"})
    if r.status_code == 200:
        return True, r.json().get("MetadataId", "")
    if r.status_code == 404:
        return False, ""
    r.raise_for_status()
    return False, ""


def attribute_exists(session: requests.Session, entity: str, attr: str) -> bool:
    url = (
        f"{API_BASE}/EntityDefinitions(LogicalName='{entity}')"
        f"/Attributes(LogicalName='{attr}')"
    )
    r = session.get(url, params={"$select": "LogicalName"})
    return r.status_code == 200


def relationship_exists(session: requests.Session, schema_name: str) -> bool:
    url = f"{API_BASE}/RelationshipDefinitions(SchemaName='{schema_name}')"
    r = session.get(url, params={"$select": "SchemaName"})
    return r.status_code == 200


def create_entity(session: requests.Session, payload: dict[str, Any]) -> str:
    """POST EntityDefinitions. Returns MetadataId."""
    r = session.post(f"{API_BASE}/EntityDefinitions", json=payload)
    if r.status_code not in (200, 201):
        log.error("Entity creation failed: %s\n%s", r.status_code, r.text[:800])
        r.raise_for_status()
    meta_id: str = r.json()["MetadataId"]
    log.info("  Created entity MetadataId=%s", meta_id)
    return meta_id


def create_attribute(session: requests.Session, entity: str, payload: dict[str, Any]) -> None:
    attr_name = payload.get("LogicalName", "?")
    url = f"{API_BASE}/EntityDefinitions(LogicalName='{entity}')/Attributes"
    r = session.post(url, json=payload)
    if r.status_code not in (200, 201):
        log.error(
            "Attribute creation failed [%s.%s]: %s\n%s",
            entity, attr_name, r.status_code, r.text[:800],
        )
        r.raise_for_status()
    log.info("    + attribute: %s", attr_name)


def create_relationship(
    session: requests.Session,
    schema_name: str,
    referencing_entity: str,
    referencing_attr: str,
    referencing_display: str,
    referenced_entity: str,
    required: bool = False,
    cascade_delete: str = "RemoveLink",
) -> None:
    if relationship_exists(session, schema_name):
        log.info("  Relationship %s already exists — skipping.", schema_name)
        return

    payload = {
        "@odata.type": "Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata",
        "SchemaName": schema_name,
        "ReferencedEntity": referenced_entity,
        "ReferencingEntity": referencing_entity,
        "Lookup": {
            "@odata.type": "Microsoft.Dynamics.CRM.LookupAttributeMetadata",
            "LogicalName": referencing_attr,
            "SchemaName": referencing_attr,
            "DisplayName": _lbl(referencing_display),
            "RequiredLevel": {"Value": "ApplicationRequired" if required else "None"},
        },
        "AssociatedMenuConfiguration": {
            "Behavior": "UseCollectionName",
            "Group": "Details",
            "Order": 10000,
        },
        "CascadeConfiguration": {
            "Assign": "NoCascade",
            "Delete": cascade_delete,
            "Merge": "NoCascade",
            "Reparent": "NoCascade",
            "Share": "NoCascade",
            "Unshare": "NoCascade",
        },
    }

    url = f"{API_BASE}/RelationshipDefinitions"
    r = session.post(url, json=payload)
    if r.status_code not in (200, 201):
        log.error(
            "Relationship creation failed [%s]: %s\n%s",
            schema_name, r.status_code, r.text[:800],
        )
        r.raise_for_status()
    log.info("  Created relationship: %s", schema_name)


# ──────────────────────────────────────────────────────────────────────────────
# Attribute payload builders
# ──────────────────────────────────────────────────────────────────────────────

def string_attr(
    logical_name: str,
    display_name: str,
    max_length: int,
    required: bool = False,
    description: str = "",
    format_: str = "Text",
) -> dict:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
        "LogicalName": logical_name,
        "SchemaName": logical_name,
        "DisplayName": _lbl(display_name),
        "Description": _lbl(description),
        "RequiredLevel": {"Value": "ApplicationRequired" if required else "None"},
        "MaxLength": max_length,
        "Format": format_,
        "IsPrimaryName": False,
    }


def int_attr(
    logical_name: str,
    display_name: str,
    min_val: int | None = None,
    max_val: int | None = None,
    description: str = "",
) -> dict:
    payload: dict[str, Any] = {
        "@odata.type": "Microsoft.Dynamics.CRM.IntegerAttributeMetadata",
        "LogicalName": logical_name,
        "SchemaName": logical_name,
        "DisplayName": _lbl(display_name),
        "Description": _lbl(description),
        "RequiredLevel": {"Value": "None"},
        "Format": "None",
    }
    if min_val is not None:
        payload["MinValue"] = min_val
    if max_val is not None:
        payload["MaxValue"] = max_val
    return payload


def money_attr(
    logical_name: str,
    display_name: str,
    description: str = "",
) -> dict:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.MoneyAttributeMetadata",
        "LogicalName": logical_name,
        "SchemaName": logical_name,
        "DisplayName": _lbl(display_name),
        "Description": _lbl(description),
        "RequiredLevel": {"Value": "None"},
        "PrecisionSource": 2,
    }


def datetime_attr(logical_name: str, display_name: str, description: str = "") -> dict:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata",
        "LogicalName": logical_name,
        "SchemaName": logical_name,
        "DisplayName": _lbl(display_name),
        "Description": _lbl(description),
        "RequiredLevel": {"Value": "None"},
        "Format": "DateAndTime",
        "DateTimeBehavior": {"Value": "UserLocal"},
    }


def memo_attr(
    logical_name: str,
    display_name: str,
    max_length: int = 2000,
    description: str = "",
) -> dict:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.MemoAttributeMetadata",
        "LogicalName": logical_name,
        "SchemaName": logical_name,
        "DisplayName": _lbl(display_name),
        "Description": _lbl(description),
        "RequiredLevel": {"Value": "None"},
        "MaxLength": max_length,
        "Format": "TextArea",
    }


def picklist_attr(
    logical_name: str,
    display_name: str,
    options: list[tuple[int, str]],
    default_value: int | None = None,
    description: str = "",
) -> dict:
    option_list = [
        {"Value": val, "Label": _lbl(label), "Description": _lbl("")}
        for val, label in options
    ]
    payload: dict[str, Any] = {
        "@odata.type": "Microsoft.Dynamics.CRM.PicklistAttributeMetadata",
        "LogicalName": logical_name,
        "SchemaName": logical_name,
        "DisplayName": _lbl(display_name),
        "Description": _lbl(description),
        "RequiredLevel": {"Value": "None"},
        "OptionSet": {
            "@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata",
            "IsGlobal": False,
            "OptionSetType": "Picklist",
            "Options": option_list,
        },
    }
    if default_value is not None:
        payload["DefaultFormValue"] = default_value
    return payload


def _base_entity_payload(
    logical_name: str,
    display_name: str,
    display_plural: str,
    description: str,
    primary_attr_name: str,
    primary_attr_display: str,
    primary_attr_max_len: int,
    primary_required: bool = True,
    auto_number_format: str | None = None,
) -> dict:
    primary_attr: dict[str, Any] = {
        "@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
        "LogicalName": primary_attr_name,
        "SchemaName": primary_attr_name,
        "DisplayName": _lbl(primary_attr_display),
        "Description": _lbl(""),
        "RequiredLevel": {
            "Value": "ApplicationRequired" if primary_required else "Recommended"
        },
        "MaxLength": primary_attr_max_len,
        "Format": "Text",
        "IsPrimaryName": True,
    }
    if auto_number_format:
        primary_attr["AutoNumberFormat"] = auto_number_format

    return {
        "@odata.type": "Microsoft.Dynamics.CRM.EntityMetadata",
        "LogicalName": logical_name,
        "SchemaName": logical_name,
        "DisplayName": _lbl(display_name),
        "DisplayCollectionName": _lbl(display_plural),
        "Description": _lbl(description),
        "OwnershipType": "UserOwned",
        "IsActivity": False,
        "HasActivities": False,
        "HasNotes": False,
        "IsAuditEnabled": {"Value": True},
        "PrimaryNameAttribute": primary_attr_name,
        "Attributes": [primary_attr],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Table definitions
# ──────────────────────────────────────────────────────────────────────────────

def create_b2b_order(session: requests.Session) -> str:
    """Create b2b_order. Returns MetadataId."""
    lname = "b2b_order"
    log.info("Processing entity: %s", lname)

    exists, meta_id = entity_exists(session, lname)
    if exists:
        log.info("  Entity %s already exists (MetadataId=%s) — skipping creation.", lname, meta_id)
    else:
        payload = _base_entity_payload(
            logical_name=lname,
            display_name="Order",
            display_plural="Orders",
            description="Customer purchase order aggregated from supplier offers.",
            primary_attr_name="b2b_order_number",
            primary_attr_display="Order Number",
            primary_attr_max_len=100,
            primary_required=True,
            auto_number_format="ORD-{SEQNUM:5}",
        )
        meta_id = create_entity(session, payload)

    attrs: list[dict] = [
        money_attr("b2b_total_amount", "Total Amount",
                   description="Total order value in the order currency."),
        picklist_attr(
            "b2b_status",
            "Status",
            options=[
                (100000000, "Draft"),
                (100000001, "Confirmed"),
                (100000002, "Shipped"),
            ],
            default_value=100000000,
            description="Order lifecycle status.",
        ),
        string_attr("b2b_currency_code", "Currency Code", max_length=3,
                    description="ISO 4217 3-letter code. Default: USD."),
    ]

    for attr in attrs:
        aname = attr["LogicalName"]
        if attribute_exists(session, lname, aname):
            log.info("    Attribute %s already exists — skipping.", aname)
        else:
            create_attribute(session, lname, attr)

    return meta_id


def create_b2b_orderline(session: requests.Session) -> str:
    """Create b2b_orderline. Returns MetadataId."""
    lname = "b2b_orderline"
    log.info("Processing entity: %s", lname)

    exists, meta_id = entity_exists(session, lname)
    if exists:
        log.info("  Entity %s already exists (MetadataId=%s) — skipping creation.", lname, meta_id)
    else:
        payload = _base_entity_payload(
            logical_name=lname,
            display_name="Order Line",
            display_plural="Order Lines",
            description="Single line item within an order, referencing a supplier offer.",
            primary_attr_name="b2b_line_ref",
            primary_attr_display="Line Ref",
            primary_attr_max_len=100,
            primary_required=True,
        )
        meta_id = create_entity(session, payload)

    attrs: list[dict] = [
        int_attr("b2b_qty", "Quantity", min_val=1, max_val=99999,
                 description="Number of units ordered."),
        money_attr("b2b_unit_price", "Unit Price",
                   description="Price per unit at time of order."),
    ]

    for attr in attrs:
        aname = attr["LogicalName"]
        if attribute_exists(session, lname, aname):
            log.info("    Attribute %s already exists — skipping.", aname)
        else:
            create_attribute(session, lname, attr)

    return meta_id


def create_b2b_rfq(session: requests.Session) -> str:
    """Create b2b_rfq. Returns MetadataId."""
    lname = "b2b_rfq"
    log.info("Processing entity: %s", lname)

    exists, meta_id = entity_exists(session, lname)
    if exists:
        log.info("  Entity %s already exists (MetadataId=%s) — skipping creation.", lname, meta_id)
    else:
        payload = _base_entity_payload(
            logical_name=lname,
            display_name="RFQ",
            display_plural="RFQs",
            description="Request for Quotation sent to a supplier for a given order.",
            primary_attr_name="b2b_rfq_number",
            primary_attr_display="RFQ Number",
            primary_attr_max_len=100,
            primary_required=True,
            auto_number_format="RFQ-{SEQNUM:5}",
        )
        meta_id = create_entity(session, payload)

    attrs: list[dict] = [
        picklist_attr(
            "b2b_status",
            "Status",
            options=[
                (100000000, "Draft"),
                (100000001, "Sent"),
                (100000002, "Responded"),
            ],
            default_value=100000000,
            description="RFQ lifecycle status.",
        ),
        datetime_attr("b2b_sent_at", "Sent At",
                      description="Timestamp when the RFQ was dispatched to the supplier."),
        datetime_attr("b2b_deadline", "Deadline",
                      description="Supplier response deadline."),
        memo_attr("b2b_notes", "Notes", max_length=2000,
                  description="Free-text notes for the RFQ."),
    ]

    for attr in attrs:
        aname = attr["LogicalName"]
        if attribute_exists(session, lname, aname):
            log.info("    Attribute %s already exists — skipping.", aname)
        else:
            create_attribute(session, lname, attr)

    return meta_id


# ──────────────────────────────────────────────────────────────────────────────
# Relationships
# ──────────────────────────────────────────────────────────────────────────────

def create_all_relationships(session: requests.Session) -> None:
    log.info("Creating lookup relationships...")

    # b2b_orderline → b2b_order (required, cascade delete)
    create_relationship(
        session,
        schema_name="b2b_orderline_order_rel",
        referencing_entity="b2b_orderline",
        referencing_attr="b2b_order_id",
        referencing_display="Order",
        referenced_entity="b2b_order",
        required=True,
        cascade_delete="Cascade",
    )

    # b2b_orderline → b2b_supplieroffer (nullable)
    create_relationship(
        session,
        schema_name="b2b_orderline_offer_rel",
        referencing_entity="b2b_orderline",
        referencing_attr="b2b_supplieroffer_id",
        referencing_display="Supplier Offer",
        referenced_entity="b2b_supplieroffer",
        required=False,
        cascade_delete="RemoveLink",
    )

    # b2b_rfq → b2b_order (nullable)
    create_relationship(
        session,
        schema_name="b2b_rfq_order_rel",
        referencing_entity="b2b_rfq",
        referencing_attr="b2b_order_id",
        referencing_display="Order",
        referenced_entity="b2b_order",
        required=False,
        cascade_delete="RemoveLink",
    )

    # b2b_rfq → b2b_supplier (nullable)
    create_relationship(
        session,
        schema_name="b2b_rfq_supplier_rel",
        referencing_entity="b2b_rfq",
        referencing_attr="b2b_supplier_id",
        referencing_display="Supplier",
        referenced_entity="b2b_supplier",
        required=False,
        cascade_delete="RemoveLink",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Solution: add component
# ──────────────────────────────────────────────────────────────────────────────

def add_to_solution(
    session: requests.Session,
    solution_name: str,
    metadata_id: str,
    table_name: str,
) -> None:
    """Add entity (ComponentType=1) to the solution."""
    payload = {
        "ComponentId": metadata_id,
        "ComponentType": 1,
        "SolutionUniqueName": solution_name,
        "AddRequiredComponents": False,
        "DoNotIncludeSubcomponents": False,
    }
    url = f"{API_BASE}/AddSolutionComponent"
    r = session.post(url, json=payload)
    if r.status_code not in (200, 201, 204):
        log.error(
            "AddSolutionComponent failed [%s/%s]: %s\n%s",
            solution_name, table_name, r.status_code, r.text[:800],
        )
        r.raise_for_status()
    log.info("  Added %s (MetadataId=%s) to solution %s", table_name, metadata_id, solution_name)


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("B2BAgg order-tables creator — target: %s", DATAVERSE_URL)

    try:
        token = get_token()
    except Exception as exc:
        log.error("Authentication failed: %s", exc)
        sys.exit(1)

    session = make_session(token)

    # Verify connectivity
    r = session.get(f"{API_BASE}/WhoAmI")
    if r.status_code != 200:
        log.error("WhoAmI check failed: %s %s", r.status_code, r.text[:200])
        sys.exit(1)
    who = r.json()
    log.info("Authenticated as UserId=%s", who.get("UserId"))

    # --- Step 1: Create tables ---
    results: dict[str, str] = {}

    for fn, name in [
        (create_b2b_order, "b2b_order"),
        (create_b2b_orderline, "b2b_orderline"),
        (create_b2b_rfq, "b2b_rfq"),
    ]:
        try:
            meta_id = fn(session)
            results[name] = meta_id
        except Exception as exc:
            log.error("FAILED to create %s: %s", name, exc)
            results[name] = "ERROR"

    # --- Step 2: Create relationships ---
    try:
        create_all_relationships(session)
    except Exception as exc:
        log.error("FAILED during relationship creation: %s", exc)

    # --- Step 3: Add to solution ---
    solution = "B2BAgg_Core"
    log.info("Adding tables to solution: %s", solution)
    for table_name, meta_id in results.items():
        if meta_id == "ERROR":
            log.warning("  Skipping %s — table creation failed.", table_name)
            continue
        try:
            add_to_solution(session, solution, meta_id, table_name)
        except Exception as exc:
            log.error("  Failed to add %s to solution: %s", table_name, exc)

    # --- Summary ---
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, meta_id in results.items():
        status = "OK" if meta_id != "ERROR" else "FAILED"
        print(f"  {name:<30} [{status}]  MetadataId={meta_id}")
    print("=" * 60)
    print("Next: pac solution export --name B2BAgg_Core ...")


if __name__ == "__main__":
    main()
