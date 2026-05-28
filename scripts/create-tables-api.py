#!/usr/bin/env python3
"""
create-tables-api.py
====================
Fallback script that creates the 4 core B2BAgg Dataverse tables via the
Web API (EntityDefinitions endpoint) when pac solution import is unavailable
or fails.

Usage
-----
  # With service-principal credentials (non-interactive, CI-friendly):
  export DATAVERSE_URL="https://YOUR-DATAVERSE-ORG.crm.dynamics.com"
  export AZURE_TENANT_ID="<tenant-id>"
  export AZURE_CLIENT_ID="<app-registration-client-id>"
  export AZURE_CLIENT_SECRET="<client-secret>"
  python scripts/create-tables-api.py

  # Without service-principal creds the script falls back to device-code flow:
  export DATAVERSE_URL="https://YOUR-DATAVERSE-ORG.crm.dynamics.com"
  export AZURE_TENANT_ID="<tenant-id>"
  python scripts/create-tables-api.py

Requirements
------------
  pip install requests msal

Design decisions
----------------
- Idempotent: checks EntityDefinitions before creating; skips if the entity
  already exists (matched by LogicalName).
- Attributes created one at a time after the entity so partial failures are
  easy to diagnose and retry.
- Currency (money) fields require a separate CurrencyAttributeMetadata POST.
- Lookup (relationship) fields are not created here — relationships require
  a RelationshipDefinitions POST which needs both entities to exist first.
  Use create_relationships() after all entities are created.
- Option sets are local (entity-scoped) to avoid global option set collisions
  during iterative development.
"""

from __future__ import annotations

import os
import sys
import json
import logging
from typing import Any

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

DATAVERSE_URL: str = os.environ.get(
    "DATAVERSE_URL", "https://YOUR-DATAVERSE-ORG.crm.dynamics.com"
).rstrip("/")
TENANT_ID: str = os.environ.get("AZURE_TENANT_ID", "<tenant-id>")
CLIENT_ID: str = os.environ.get("AZURE_CLIENT_ID", "")
CLIENT_SECRET: str = os.environ.get("AZURE_CLIENT_SECRET", "")

# Dataverse Web API version — 9.2 supports all features we need
API_VERSION = "v9.2"
API_BASE = f"{DATAVERSE_URL}/api/data/{API_VERSION}"

# Publisher option-value prefix (matches Solution.xml / CLAUDE.md)
OPTION_PREFIX = 10000


# ──────────────────────────────────────────────────────────────────────────────
# Authentication helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get_token_client_credentials() -> str:
    """Acquire an access token using client credentials (service principal)."""
    import msal  # type: ignore
    authority = f"https://login.microsoftonline.com/{TENANT_ID}"
    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=authority,
        client_credential=CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(scopes=[f"{DATAVERSE_URL}/.default"])
    if "access_token" not in result:
        raise RuntimeError(f"Failed to acquire token: {result.get('error_description')}")
    log.info("Token acquired via client credentials.")
    return result["access_token"]


def _get_token_device_code() -> str:
    """Acquire an access token using the device-code flow (interactive fallback)."""
    import msal  # type: ignore
    authority = f"https://login.microsoftonline.com/{TENANT_ID}"
    # Use the well-known PowerShell client ID so we don't need an app registration
    # for interactive sessions during dev.
    POWERSHELL_CLIENT_ID = "1950a258-227b-4e31-a9cf-717495945fc2"
    app = msal.PublicClientApplication(POWERSHELL_CLIENT_ID, authority=authority)
    flow = app.initiate_device_flow(scopes=[f"{DATAVERSE_URL}/.default"])
    if "user_code" not in flow:
        raise RuntimeError(f"Failed to initiate device flow: {flow}")
    log.info("Device code flow: %s", flow["message"])
    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(f"Device code auth failed: {result.get('error_description')}")
    log.info("Token acquired via device code.")
    return result["access_token"]


def get_token() -> str:
    if CLIENT_ID and CLIENT_SECRET:
        return _get_token_client_credentials()
    log.info("No service-principal credentials set — falling back to device code flow.")
    return _get_token_device_code()


def make_session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {token}",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "Prefer": "return=representation",  # return created entity on POST
    })
    return s


# ──────────────────────────────────────────────────────────────────────────────
# Dataverse Web API helpers
# ──────────────────────────────────────────────────────────────────────────────

def entity_exists(session: requests.Session, logical_name: str) -> bool:
    """Return True if an entity with this logical name already exists."""
    url = f"{API_BASE}/EntityDefinitions(LogicalName='{logical_name}')"
    r = session.get(url, params={"$select": "LogicalName"})
    if r.status_code == 200:
        return True
    if r.status_code == 404:
        return False
    r.raise_for_status()
    return False  # unreachable, but mypy is happy


def attribute_exists(
    session: requests.Session, entity_logical_name: str, attr_logical_name: str
) -> bool:
    """Return True if the attribute already exists on the entity."""
    url = (
        f"{API_BASE}/EntityDefinitions(LogicalName='{entity_logical_name}')"
        f"/Attributes(LogicalName='{attr_logical_name}')"
    )
    r = session.get(url, params={"$select": "LogicalName"})
    return r.status_code == 200


def create_entity(session: requests.Session, payload: dict[str, Any]) -> str:
    """POST to EntityDefinitions and return the MetadataId."""
    r = session.post(f"{API_BASE}/EntityDefinitions", json=payload)
    if r.status_code not in (200, 201):
        log.error("Entity creation failed: %s %s", r.status_code, r.text[:500])
        r.raise_for_status()
    meta_id: str = r.json()["MetadataId"]
    log.info("  Created entity: MetadataId=%s", meta_id)
    return meta_id


def create_attribute(
    session: requests.Session,
    entity_logical_name: str,
    payload: dict[str, Any],
) -> None:
    """POST to EntityDefinitions(<name>)/Attributes."""
    attr_name = payload.get("LogicalName", "?")
    url = f"{API_BASE}/EntityDefinitions(LogicalName='{entity_logical_name}')/Attributes"
    r = session.post(url, json=payload)
    if r.status_code not in (200, 201):
        log.error(
            "Attribute creation failed [%s.%s]: %s %s",
            entity_logical_name, attr_name, r.status_code, r.text[:500],
        )
        r.raise_for_status()
    log.info("    + attribute: %s", attr_name)


# ──────────────────────────────────────────────────────────────────────────────
# Shared metadata builders
# ──────────────────────────────────────────────────────────────────────────────

def _lbl(text: str, lang: int = 1033) -> dict:
    return {
        "LocalizedLabels": [{"Label": text, "LanguageCode": lang}],
        "UserLocalizedLabel": {"Label": text, "LanguageCode": lang},
    }


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
        "Description": _lbl(description) if description else _lbl(""),
        "RequiredLevel": {"Value": "ApplicationRequired" if required else "None"},
        "MaxLength": max_length,
        "Format": format_,
        "IsPrimaryName": False,
    }


def int_attr(logical_name: str, display_name: str, description: str = "") -> dict:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.IntegerAttributeMetadata",
        "LogicalName": logical_name,
        "SchemaName": logical_name,
        "DisplayName": _lbl(display_name),
        "Description": _lbl(description),
        "RequiredLevel": {"Value": "None"},
        "Format": "None",
    }


def decimal_attr(
    logical_name: str,
    display_name: str,
    min_val: float,
    max_val: float,
    precision: int,
    description: str = "",
) -> dict:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.DecimalAttributeMetadata",
        "LogicalName": logical_name,
        "SchemaName": logical_name,
        "DisplayName": _lbl(display_name),
        "Description": _lbl(description),
        "RequiredLevel": {"Value": "None"},
        "MinValue": min_val,
        "MaxValue": max_val,
        "Precision": precision,
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


def bool_attr(
    logical_name: str,
    display_name: str,
    default_value: bool = True,
    description: str = "",
) -> dict:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.BooleanAttributeMetadata",
        "LogicalName": logical_name,
        "SchemaName": logical_name,
        "DisplayName": _lbl(display_name),
        "Description": _lbl(description),
        "RequiredLevel": {"Value": "None"},
        "DefaultValue": default_value,
        "OptionSet": {
            "TrueOption": {"Value": 1, "Label": _lbl("Yes")},
            "FalseOption": {"Value": 0, "Label": _lbl("No")},
        },
    }


def money_attr(logical_name: str, display_name: str, description: str = "") -> dict:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.MoneyAttributeMetadata",
        "LogicalName": logical_name,
        "SchemaName": logical_name,
        "DisplayName": _lbl(display_name),
        "Description": _lbl(description),
        "RequiredLevel": {"Value": "None"},
        "PrecisionSource": 2,  # CurrencyPrecision
    }


def picklist_attr(
    logical_name: str,
    display_name: str,
    options: list[tuple[int, str]],
    description: str = "",
) -> dict:
    """Build a local (entity-scoped) picklist attribute payload."""
    return {
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
            "Options": [
                {
                    "Value": val,
                    "Label": _lbl(label),
                    "Description": _lbl(""),
                }
                for val, label in options
            ],
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# Entity definitions
# ──────────────────────────────────────────────────────────────────────────────

def _base_entity_payload(
    logical_name: str,
    display_name: str,
    display_plural: str,
    description: str,
    primary_attr_name: str,
    primary_attr_display: str,
    primary_attr_max_len: int,
    primary_required: bool = True,
) -> dict:
    """Build the entity+primaryAttribute payload for EntityDefinitions POST."""
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
        # The primary name attribute must be defined inline on entity creation.
        "Attributes": [
            {
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
        ],
    }


# ── b2b_region ────────────────────────────────────────────────────────────────

def create_b2b_region(session: requests.Session) -> None:
    lname = "b2b_region"
    log.info("Processing entity: %s", lname)

    if entity_exists(session, lname):
        log.info("  Entity %s already exists — skipping entity creation.", lname)
    else:
        payload = _base_entity_payload(
            logical_name=lname,
            display_name="Region",
            display_plural="Regions",
            description="Geographic region (Russian federal district) for supplier/buyer matching.",
            primary_attr_name="b2b_name",
            primary_attr_display="Name",
            primary_attr_max_len=200,
        )
        create_entity(session, payload)

    attrs: list[dict] = [
        picklist_attr(
            "b2b_climate_zone",
            "Climate Zone",
            options=[
                (OPTION_PREFIX + 0, "Nord"),
                (OPTION_PREFIX + 1, "Center"),
                (OPTION_PREFIX + 2, "South"),
                (OPTION_PREFIX + 3, "Caucasus"),
                (OPTION_PREFIX + 4, "FarEast"),
            ],
            description="Climate classification for tire season filtering.",
        ),
        string_attr(
            "b2b_federal_district",
            "Federal District",
            max_length=100,
            description="Full official name of the federal district.",
        ),
    ]

    for attr in attrs:
        aname = attr["LogicalName"]
        if attribute_exists(session, lname, aname):
            log.info("    Attribute %s already exists — skipping.", aname)
        else:
            create_attribute(session, lname, attr)


# ── b2b_supplier ──────────────────────────────────────────────────────────────

def create_b2b_supplier(session: requests.Session) -> None:
    lname = "b2b_supplier"
    log.info("Processing entity: %s", lname)

    if entity_exists(session, lname):
        log.info("  Entity %s already exists — skipping entity creation.", lname)
    else:
        payload = _base_entity_payload(
            logical_name=lname,
            display_name="Supplier",
            display_plural="Suppliers",
            description="Wholesale tire supplier. Source of offers and feed data.",
            primary_attr_name="b2b_name",
            primary_attr_display="Name",
            primary_attr_max_len=200,
        )
        create_entity(session, payload)

    attrs: list[dict] = [
        picklist_attr(
            "b2b_tier",
            "Tier",
            options=[
                (OPTION_PREFIX + 0, "Gold"),
                (OPTION_PREFIX + 1, "Silver"),
                (OPTION_PREFIX + 2, "Bronze"),
            ],
            description="Supplier classification tier.",
        ),
        decimal_attr(
            "b2b_trust_score", "Trust Score",
            min_val=0.0, max_val=100.0, precision=2,
            description="Weighted reliability score 0–100.",
        ),
        string_attr(
            "b2b_feed_endpoint", "Feed Endpoint",
            max_length=500, format_="Url",
            description="HTTP(S) URL of the supplier offer feed.",
        ),
        datetime_attr("b2b_last_sync", "Last Sync",
                      description="Timestamp of the last completed sync."),
        bool_attr("b2b_is_active", "Is Active", default_value=True,
                  description="Exclude from sync and search when false."),
        # NOTE: b2b_region lookup relationship is created by create_relationships()
        #       after both entities exist.
    ]

    for attr in attrs:
        aname = attr["LogicalName"]
        if attribute_exists(session, lname, aname):
            log.info("    Attribute %s already exists — skipping.", aname)
        else:
            create_attribute(session, lname, attr)


# ── b2b_canonicalproduct ──────────────────────────────────────────────────────

def create_b2b_canonicalproduct(session: requests.Session) -> None:
    lname = "b2b_canonicalproduct"
    log.info("Processing entity: %s", lname)

    if entity_exists(session, lname):
        log.info("  Entity %s already exists — skipping entity creation.", lname)
    else:
        payload = _base_entity_payload(
            logical_name=lname,
            display_name="Canonical Product",
            display_plural="Canonical Products",
            description="Normalized tire SKU that supplier offers are mapped to.",
            primary_attr_name="b2b_name",
            primary_attr_display="Name / SKU",
            primary_attr_max_len=300,
        )
        create_entity(session, payload)

    attrs: list[dict] = [
        string_attr("b2b_brand", "Brand", max_length=100, required=True),
        string_attr("b2b_model", "Model", max_length=100, required=True),
        picklist_attr(
            "b2b_season",
            "Season",
            options=[
                (OPTION_PREFIX + 0, "Summer"),
                (OPTION_PREFIX + 1, "WinterStudded"),
                (OPTION_PREFIX + 2, "WinterFriction"),
                (OPTION_PREFIX + 3, "AllSeason"),
            ],
            description="WinterStudded and WinterFriction are split for buyer season filter.",
        ),
        int_attr("b2b_width",      "Width (mm)"),
        int_attr("b2b_profile",    "Profile (%)"),
        int_attr("b2b_diameter",   "Diameter (R)"),
        int_attr("b2b_load_index", "Load Index"),
        string_attr("b2b_speed_index",    "Speed Index",    max_length=5),
        string_attr("b2b_ean",            "EAN",            max_length=20,
                    description="EAN-13. Alternate key registered post-import."),
        string_attr("b2b_normalized_name", "Normalized Name", max_length=500,
                    description="Machine-generated canonical form for fuzzy matching. Set by flows."),
    ]

    for attr in attrs:
        aname = attr["LogicalName"]
        if attribute_exists(session, lname, aname):
            log.info("    Attribute %s already exists — skipping.", aname)
        else:
            create_attribute(session, lname, attr)


# ── b2b_supplieroffer ─────────────────────────────────────────────────────────

def create_b2b_supplieroffer(session: requests.Session) -> None:
    lname = "b2b_supplieroffer"
    log.info("Processing entity: %s", lname)

    if entity_exists(session, lname):
        log.info("  Entity %s already exists — skipping entity creation.", lname)
    else:
        payload = _base_entity_payload(
            logical_name=lname,
            display_name="Supplier Offer",
            display_plural="Supplier Offers",
            description="Stock lot as ingested from a supplier feed. Linked to canonical product after normalization.",
            primary_attr_name="b2b_name",
            primary_attr_display="Offer Name",
            primary_attr_max_len=300,
            primary_required=False,
        )
        create_entity(session, payload)

    attrs: list[dict] = [
        # Lookup columns (b2b_supplier, b2b_canonical_product) are created via
        # create_relationships() because they require both entities to exist.
        string_attr("b2b_raw_name",       "Raw Supplier Name", max_length=500,
                    description="Product name as received from the supplier feed."),
        string_attr("b2b_raw_sku",        "Raw SKU",           max_length=200,
                    description="Supplier's own SKU code. Part of alternate key for upsert."),
        money_attr( "b2b_price",          "Price",
                    description="Asking price per unit."),
        string_attr("b2b_currency",       "Currency Code",     max_length=10,
                    description="ISO 4217 code, e.g. USD. Default: USD."),
        int_attr(   "b2b_stock",          "Stock (units)"),
        datetime_attr("b2b_last_synced",  "Last Synced",
                      description="Timestamp of the last sync that updated this offer."),
        string_attr("b2b_warehouse_city", "Warehouse City",    max_length=100,
                    description="Denormalized city for efficient search filtering."),
        int_attr(   "b2b_lead_time_days", "Lead Time (days)"),
    ]

    for attr in attrs:
        aname = attr["LogicalName"]
        if attribute_exists(session, lname, aname):
            log.info("    Attribute %s already exists — skipping.", aname)
        else:
            create_attribute(session, lname, attr)


# ──────────────────────────────────────────────────────────────────────────────
# Relationships (lookup columns as Many-to-One relationships)
# ──────────────────────────────────────────────────────────────────────────────

def _relationship_exists(
    session: requests.Session, schema_name: str
) -> bool:
    url = f"{API_BASE}/RelationshipDefinitions(SchemaName='{schema_name}')"
    r = session.get(url, params={"$select": "SchemaName"})
    return r.status_code == 200


def create_relationship(
    session: requests.Session,
    schema_name: str,
    referencing_entity: str,
    referencing_attr: str,
    referencing_display: str,
    referenced_entity: str,
    required: bool = False,
) -> None:
    """Create a Many-to-One (N:1) relationship = lookup column on referencing entity."""
    if _relationship_exists(session, schema_name):
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
            "Delete": "RemoveLink",
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
            "Relationship creation failed [%s]: %s %s",
            schema_name, r.status_code, r.text[:500],
        )
        r.raise_for_status()
    log.info("  Created relationship: %s", schema_name)


def create_relationships(session: requests.Session) -> None:
    """Create all lookup relationships between the 4 entities."""
    log.info("Creating lookup relationships...")

    # b2b_supplier.b2b_region → b2b_region
    create_relationship(
        session,
        schema_name="b2b_supplier_b2b_region",
        referencing_entity="b2b_supplier",
        referencing_attr="b2b_region",
        referencing_display="Region",
        referenced_entity="b2b_region",
        required=False,
    )

    # b2b_supplieroffer.b2b_supplier → b2b_supplier (Required)
    create_relationship(
        session,
        schema_name="b2b_supplieroffer_b2b_supplier",
        referencing_entity="b2b_supplieroffer",
        referencing_attr="b2b_supplier",
        referencing_display="Supplier",
        referenced_entity="b2b_supplier",
        required=True,
    )

    # b2b_supplieroffer.b2b_canonical_product → b2b_canonicalproduct (nullable)
    create_relationship(
        session,
        schema_name="b2b_supplieroffer_b2b_canonicalproduct",
        referencing_entity="b2b_supplieroffer",
        referencing_attr="b2b_canonical_product",
        referencing_display="Canonical Product",
        referenced_entity="b2b_canonicalproduct",
        required=False,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("B2BAgg table creator — target: %s", DATAVERSE_URL)

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

    # Create entities (order matters for readability; relationships handled separately)
    create_b2b_region(session)
    create_b2b_supplier(session)
    create_b2b_canonicalproduct(session)
    create_b2b_supplieroffer(session)

    # Create lookup relationships (requires all 4 entities to exist)
    create_relationships(session)

    log.info("Done. All 4 entities and relationships processed successfully.")
    log.info(
        "Next steps:\n"
        "  1. Register alternate keys in the Maker Portal:\n"
        "       b2b_canonicalproduct.b2b_ean (unique)\n"
        "       b2b_supplier.b2b_name (unique)\n"
        "       b2b_supplieroffer: b2b_supplier + b2b_raw_sku (composite)\n"
        "  2. Export the solution: pac solution export …\n"
        "  3. Unpack: pac solution unpack … --folder solutions/B2BAgg.Core/src\n"
        "  4. Commit the unpacked XML to git."
    )


if __name__ == "__main__":
    main()
