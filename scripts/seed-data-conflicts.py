#!/usr/bin/env python3
"""
seed-data-conflicts.py — seed realistic demo rows into b2b_dataconflict so the
MDA "Data Conflicts" Kanban has content for the demo (MVP2 А+Г, Stage A).

Each row mirrors what the Normalize SKU flow (Stage B) would produce when its
deterministic cascade can't auto-bind an offer: a homologation `*` ambiguity, a
spec-incomplete name, and an off-catalogue brand (NewCandidate). This lets the
Kanban be demoed before the flow exists, and the flow's own "create conflict"
step is kept idempotent on the same key so the two never duplicate.

Idempotent: keyed on (b2b_raw_sku). Re-running updates status/fields in place
rather than creating duplicates. Offers + canonicals are resolved by natural key
at runtime (no hard-coded GUIDs) so this is environment-portable.

Auth: az-CLI token (QUIRK #1) — no device code, no client secret.
  az login   # as <admin-upn>
  python3 scripts/seed-data-conflicts.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

DV = "https://YOUR-DATAVERSE-ORG.crm.dynamics.com"
API = f"{DV}/api/data/v9.2"

# status optionset (b2b_status)
PENDING, NEEDS_REVIEW, NEW_CANDIDATE = 10000, 10001, 10002


def token() -> str:
    out = subprocess.run(
        ["az", "account", "get-access-token", "--resource", DV,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True,
    )
    tok = out.stdout.strip()
    if not tok:
        sys.exit(f"No az token. Run `az login`.\n{out.stderr}")
    return tok


def _req(method: str, path: str, tok: str, body: dict | None = None):
    if "?" in path:
        base, q = path.split("?", 1)
        path = base + "?" + urllib.parse.quote(q, safe="=&$,'")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}/{path}", data=data, method=method)
    req.add_header("Authorization", f"Bearer {tok}")
    req.add_header("Accept", "application/json")
    req.add_header("OData-MaxVersion", "4.0")
    req.add_header("OData-Version", "4.0")
    if body is not None:
        req.add_header("Content-Type", "application/json")
        req.add_header("Prefer", "return=representation")
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode()
            return (json.loads(raw) if raw else {}), r.status
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path} -> {e.code}\n{e.read().decode()[:500]}")


def find_one(entity_set: str, id_field: str, filt: str, tok: str) -> str | None:
    res, _ = _req("GET", f"{entity_set}?$select={id_field}&$filter={filt}&$top=1", tok)
    vals = res.get("value", [])
    return vals[0][id_field] if vals else None


# Demo conflicts. canonical_key=None => NewCandidate (no suggested canonical).
CONFLICTS = [
    {
        "raw_sku": "23-LS3-MERC",
        "name": "Conflict: МИШЛЕН Latitude Sport 3 245/45R20 MO",
        "status": PENDING,
        "canonical_key": "MICHELIN|LATITUDESPORT3|245|45|20|103|W|MO_Mercedes|RF|XL",
        "ai_confidence": 0.88,
        "candidates": [
            {"key": "MO_Mercedes", "name": "Latitude Sport 3 RunFlat MO (Mercedes)", "score": 0.88},
            {"key": "base",        "name": "Latitude Sport 3 RunFlat",                "score": 0.55},
        ],
    },
    {
        "raw_sku": "ML-LS3-24545R20-RFT-S",
        "name": "Conflict: MICHELIN Latitude Sport 3 245/45 R20 Run on Flat *",
        "status": PENDING,
        "canonical_key": "MICHELIN|LATITUDESPORT3|245|45|20|103|W|Star_BMW|RF|XL",
        "ai_confidence": 0.82,
        "candidates": [
            {"key": "Star_BMW",    "name": "Latitude Sport 3 RunFlat * (BMW)",        "score": 0.82},
            {"key": "base",        "name": "Latitude Sport 3 RunFlat",                "score": 0.61},
            {"key": "MO_Mercedes", "name": "Latitude Sport 3 RunFlat MO (Mercedes)",  "score": 0.40},
        ],
    },
    {
        "raw_sku": "LS3-NOSPEC-20",
        "name": "Conflict: Michelin Latitude Sport 3 245/45 R20 (no speed idx)",
        "status": NEEDS_REVIEW,
        "canonical_key": "MICHELIN|LATITUDESPORT3|245|45|20|103|W|None|RF|XL",
        "ai_confidence": 0.69,
        "candidates": [
            {"key": "base",        "name": "Latitude Sport 3 RunFlat",               "score": 0.69},
            {"key": "Star_BMW",    "name": "Latitude Sport 3 RunFlat * (BMW)",       "score": 0.66},
            {"key": "MO_Mercedes", "name": "Latitude Sport 3 RunFlat MO (Mercedes)", "score": 0.64},
        ],
    },
    {
        "raw_sku": "CPC6-RFT-2245",
        "name": "Conflict: Continental PremiumContact 6 225/45R17 SSR",
        "status": NEW_CANDIDATE,
        "canonical_key": None,  # off-catalogue brand -> propose new canonical
        "ai_confidence": None,
        "candidates": [],
    },
]


def main() -> None:
    tok = token()
    created = updated = skipped = 0
    for c in CONFLICTS:
        offer_id = find_one(
            "b2b_supplieroffers", "b2b_supplierofferid",
            f"b2b_raw_sku eq '{c['raw_sku']}'", tok)
        if not offer_id:
            print(f"  ! offer not found for raw_sku={c['raw_sku']!r} — skipping")
            skipped += 1
            continue

        canonical_id = None
        if c["canonical_key"]:
            canonical_id = find_one(
                "b2b_canonicalproducts", "b2b_canonicalproductid",
                f"b2b_canonical_key eq '{c['canonical_key']}'", tok)
            if not canonical_id:
                print(f"  ! canonical not found for key={c['canonical_key']!r}")

        payload = {
            "b2b_name": c["name"][:100],
            "b2b_raw_sku": c["raw_sku"],
            "b2b_status": c["status"],
            "b2b_candidates_json": json.dumps(c["candidates"], ensure_ascii=False),
            "b2b_supplier_offer@odata.bind": f"/b2b_supplieroffers({offer_id})",
        }
        if c["ai_confidence"] is not None:
            payload["b2b_ai_confidence"] = c["ai_confidence"]
        if canonical_id:
            payload["b2b_suggested_canonical@odata.bind"] = \
                f"/b2b_canonicalproducts({canonical_id})"
        # carry raw_name from the offer for display fidelity
        off, _ = _req("GET",
                      f"b2b_supplieroffers({offer_id})?$select=b2b_raw_name", tok)
        if off.get("b2b_raw_name"):
            payload["b2b_raw_name"] = off["b2b_raw_name"]

        existing = find_one("b2b_dataconflicts", "b2b_dataconflictid",
                            f"b2b_raw_sku eq '{c['raw_sku']}'", tok)
        if existing:
            _req("PATCH", f"b2b_dataconflicts({existing})", tok, payload)
            print(f"  ~ updated  {c['raw_sku']:24} status={c['status']}")
            updated += 1
        else:
            _req("POST", "b2b_dataconflicts", tok, payload)
            print(f"  + created  {c['raw_sku']:24} status={c['status']}")
            created += 1

    print(f"\nDone. created={created} updated={updated} skipped={skipped}")


if __name__ == "__main__":
    main()
