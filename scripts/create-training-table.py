#!/usr/bin/env python3
"""
create-training-table.py — create a TEMPORARY Dataverse table to feed AI Builder
Category classification (the wizard requires a Dataverse table, not a file upload).

Table: b2b_skutraining
  b2b_text   (primary name, String 850)  <- map to AI Builder "Text" column
  b2b_label  (String 200)                <- map to AI Builder "Label" column

Loads data/ai-builder/sku-training-data.csv (cols: Text, Label).

Idempotent:
  - entity created only if missing (checked by LogicalName)
  - rows inserted only if the table is currently empty (re-run = no duplicates).
    Pass --force to wipe existing rows and reload.

Auth: az account get-access-token (QUIRK #1).
  az login   # as <admin-upn>
  python3 scripts/create-training-table.py
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DV = "https://YOUR-DATAVERSE-ORG.crm.dynamics.com"
API = f"{DV}/api/data/v9.2"
CSV_PATH = Path(__file__).resolve().parent.parent / "data/ai-builder/sku-training-data.csv"
ENTITY = "b2b_skutraining"
FORCE = "--force" in sys.argv


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


def _req(method: str, path: str, tok: str, body: dict | None = None,
         prefer: str | None = None):
    url = path if path.startswith("http") else f"{API}/{path}"
    if "?" in url:
        base, q = url.split("?", 1)
        url = base + "?" + urllib.parse.quote(q, safe="=&$,'()/")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {tok}")
    req.add_header("Accept", "application/json")
    req.add_header("OData-MaxVersion", "4.0")
    req.add_header("OData-Version", "4.0")
    if prefer:
        req.add_header("Prefer", prefer)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode()
            return (json.loads(raw) if raw else {}), r.status
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {url} -> {e.code}\n{e.read().decode()[:800]}")


def _label(text: str) -> dict:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.Label",
        "LocalizedLabels": [{
            "@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel",
            "Label": text, "LanguageCode": 1033,
        }],
    }


def _string_attr(schema: str, display: str, maxlen: int, primary: bool = False):
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
        "SchemaName": schema,
        "DisplayName": _label(display),
        "IsPrimaryName": primary,
        "MaxLength": maxlen,
        "AttributeType": "String",
        "AttributeTypeName": {"Value": "StringType"},
    }


def entity_exists(tok: str) -> bool:
    res, _ = _req("GET",
                  f"EntityDefinitions?$select=LogicalName&$filter=LogicalName eq '{ENTITY}'",
                  tok)
    return bool(res.get("value"))


def entity_set_name(tok: str) -> str:
    res, _ = _req("GET",
                  f"EntityDefinitions(LogicalName='{ENTITY}')?$select=EntitySetName",
                  tok)
    return res["EntitySetName"]


def create_entity(tok: str) -> None:
    if entity_exists(tok):
        print(f"  = {ENTITY} already exists")
        return
    body = {
        "@odata.type": "Microsoft.Dynamics.CRM.EntityMetadata",
        "SchemaName": ENTITY,
        "DisplayName": _label("SKU Training"),
        "DisplayCollectionName": _label("SKU Training"),
        "Description": _label("TEMP — AI Builder Category classification training data. Safe to delete after model is trained/published."),
        "OwnershipType": "UserOwned",
        "HasActivities": False,
        "HasNotes": False,
        "PrimaryNameAttribute": "b2b_text",
        "Attributes": [
            _string_attr("b2b_text", "Text", 850, primary=True),
            _string_attr("b2b_label", "Label", 200),
        ],
    }
    _req("POST", "EntityDefinitions", tok, body)
    print(f"  + created {ENTITY} (b2b_text, b2b_label)")
    # publish + wait for the entity set to become queryable
    print("  … waiting for metadata to propagate", end="", flush=True)
    for _ in range(30):
        time.sleep(4)
        print(".", end="", flush=True)
        if entity_exists(tok):
            try:
                eset = entity_set_name(tok)
                _req("GET", f"{eset}?$top=1", tok)
                print(" ready")
                return
            except SystemExit:
                continue
    print(" (proceeding)")


def row_count(eset: str, tok: str) -> int:
    res, _ = _req("GET", f"{eset}?$select={ENTITY}id&$top=2", tok)
    return len(res.get("value", []))


def wipe(eset: str, tok: str) -> None:
    pk = f"{ENTITY}id"
    deleted = 0
    while True:
        res, _ = _req("GET", f"{eset}?$select={pk}&$top=200", tok)
        rows = res.get("value", [])
        if not rows:
            break
        for r in rows:
            _req("DELETE", f"{eset}({r[pk]})", tok)
            deleted += 1
    print(f"  - wiped {deleted} existing rows")


def load_rows(eset: str, tok: str) -> None:
    with open(CSV_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    n = 0
    for r in rows:
        text = (r.get("Text") or "").strip()
        label = (r.get("Label") or "").strip()
        if not text or not label:
            continue
        _req("POST", eset, tok, {"b2b_text": text[:850], "b2b_label": label[:200]})
        n += 1
        if n % 30 == 0:
            print(f"    … {n} rows")
    print(f"  + inserted {n} rows from {CSV_PATH.name}")


def main() -> None:
    if not CSV_PATH.exists():
        sys.exit(f"CSV not found: {CSV_PATH}")
    tok = token()
    create_entity(tok)
    eset = entity_set_name(tok)
    existing = row_count(eset, tok)
    if existing and not FORCE:
        print(f"  = {eset} already has rows — skipping load (use --force to reload)")
    else:
        if existing and FORCE:
            wipe(eset, tok)
        load_rows(eset, tok)
    print(f"\nDone. AI Builder → pick table 'SKU Training'; "
          f"Text column = Text, Label column = Label.")


if __name__ == "__main__":
    main()
