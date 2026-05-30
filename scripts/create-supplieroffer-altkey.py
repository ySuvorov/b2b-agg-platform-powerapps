#!/usr/bin/env python3
"""
create-supplieroffer-altkey.py
==============================
Creates the idempotent-upsert alternate key on b2b_supplieroffer (audit P5 / L-1).

Grain decision (P5): the composite key is
    (b2b_supplier + b2b_warehouse + b2b_raw_sku)
Rationale: the same raw_sku at the same warehouse can legitimately come from
different suppliers, so supplier is part of the offer's identity. The sync flow
PATCH-upserts on this key; the seeder (seed-via-az-token.py) must dedupe on the
same triple so the two never diverge.

Idempotent; uses an az-CLI token (no MSAL / device code — see PROGRESS QUIRK #1).
Alternate-key indexes activate asynchronously — this script polls until the key
reports EntityKeyIndexStatus == 'Active' (or times out with a clear message).

Usage:
    # az must be logged in as <admin-upn>
    python3 scripts/create-supplieroffer-altkey.py
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
ENTITY = "b2b_supplieroffer"
KEY_SCHEMA = "b2b_offer_supplier_wh_sku"
KEY_DISPLAY = "Offer Upsert Key (Supplier+Warehouse+RawSKU)"
KEY_ATTRS = ["b2b_supplier", "b2b_warehouse", "b2b_raw_sku"]
POLL_SECONDS = 5
POLL_MAX = 36  # ~3 min


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
    })
    return s


def _lbl(t: str, lang: int = 1033) -> dict:
    return {"LocalizedLabels": [{"Label": t, "LanguageCode": lang}],
            "UserLocalizedLabel": {"Label": t, "LanguageCode": lang}}


def get_key(s: requests.Session) -> dict | None:
    r = s.get(f"{API}/EntityDefinitions(LogicalName='{ENTITY}')/Keys",
              params={"$select": "SchemaName,KeyAttributes,EntityKeyIndexStatus",
                      "$filter": f"SchemaName eq '{KEY_SCHEMA}'"})
    if r.status_code != 200:
        log.error("Key query failed: %s %s", r.status_code, r.text[:300]); r.raise_for_status()
    vals = r.json().get("value", [])
    return vals[0] if vals else None


def create_key(s: requests.Session) -> None:
    payload = {"@odata.type": "Microsoft.Dynamics.CRM.EntityKeyMetadata",
               "SchemaName": KEY_SCHEMA,
               "DisplayName": _lbl(KEY_DISPLAY),
               "KeyAttributes": KEY_ATTRS}
    r = s.post(f"{API}/EntityDefinitions(LogicalName='{ENTITY}')/Keys", json=payload)
    if r.status_code not in (200, 201, 204):
        log.error("Key create failed: %s %s", r.status_code, r.text[:500]); r.raise_for_status()
    log.info("Key POST accepted (%s). Index activates asynchronously.", r.status_code)


def main() -> None:
    log.info("Alt-key creator for %s — grain %s", ENTITY, " + ".join(KEY_ATTRS))
    s = make_session(get_token())
    who = s.get(f"{API}/WhoAmI")
    if who.status_code != 200:
        log.error("WhoAmI failed: %s %s", who.status_code, who.text[:200]); sys.exit(1)
    log.info("Authenticated UserId=%s", who.json().get("UserId"))

    existing = get_key(s)
    if existing:
        log.info("Key %s already exists — status=%s, attrs=%s",
                 KEY_SCHEMA, existing.get("EntityKeyIndexStatus"),
                 existing.get("KeyAttributes"))
    else:
        create_key(s)

    # poll for Active
    for i in range(1, POLL_MAX + 1):
        k = get_key(s)
        status = k.get("EntityKeyIndexStatus") if k else "(missing)"
        log.info("  poll %d/%d: EntityKeyIndexStatus=%s", i, POLL_MAX, status)
        if status == "Active":
            log.info("DONE. Key %s is Active. KeyAttributes=%s",
                     KEY_SCHEMA, k.get("KeyAttributes"))
            log.info("Upsert URL pattern: PATCH %s/%ss"
                     "(b2b_supplier=<id>,b2b_warehouse=<id>,b2b_raw_sku='<sku>')",
                     API, ENTITY)
            return
        if status in ("Failed", "Pending"):  # Pending may flip to Failed; keep polling unless Failed
            if status == "Failed":
                log.error("Key index entered Failed state. Inspect manually.")
                sys.exit(2)
        time.sleep(POLL_SECONDS)

    log.warning("Timed out waiting for Active (last status=%s). "
                "Re-run the script later to re-check; creation is idempotent.", status)
    sys.exit(3)


if __name__ == "__main__":
    main()
