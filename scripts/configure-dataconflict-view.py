#!/usr/bin/env python3
"""
configure-dataconflict-view.py — set the columns + sort of the "Active Data
Conflicts" public view so it reads as a grouped review board (Option B for MVP2,
since the native Kanban control is locked to Opportunity/Activity tables).

Columns: Raw SKU, Raw Supplier Name, Status, AI Confidence, Suggested Canonical.
Sort: by Status (so same-status rows cluster), then AI Confidence desc.
Pairs with the "Conflicts by Status" chart from create-dataconflict-chart.py.

Idempotent: rewrites the view's layoutxml/fetchxml to the canonical form below.

Auth: az account get-access-token (QUIRK #1).
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
ENTITY = "b2b_dataconflict"
OTC = "10590"
VIEW_NAME = "Active Data Conflicts"

LAYOUT = (
    f'<grid name="resultset" object="{OTC}" jump="b2b_name" select="1" icon="1" preview="1">'
    '<row name="result" id="b2b_dataconflictid">'
    '<cell name="b2b_raw_sku" width="160" />'
    '<cell name="b2b_raw_name" width="280" />'
    '<cell name="b2b_status" width="130" />'
    '<cell name="b2b_ai_confidence" width="110" />'
    '<cell name="b2b_suggested_canonical" width="220" />'
    '</row></grid>'
)

FETCH = (
    '<fetch version="1.0" output-format="xml-platform" mapping="logical" distinct="false">'
    '<entity name="b2b_dataconflict">'
    '<attribute name="b2b_raw_sku" />'
    '<attribute name="b2b_raw_name" />'
    '<attribute name="b2b_status" />'
    '<attribute name="b2b_ai_confidence" />'
    '<attribute name="b2b_suggested_canonical" />'
    '<attribute name="b2b_name" />'
    '<attribute name="b2b_dataconflictid" />'
    '<order attribute="b2b_status" descending="false" />'
    '<order attribute="b2b_ai_confidence" descending="true" />'
    '</entity></fetch>'
)


def token() -> str:
    out = subprocess.run(
        ["az", "account", "get-access-token", "--resource", DV,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True)
    tok = out.stdout.strip()
    if not tok:
        sys.exit(f"No az token. Run `az login`.\n{out.stderr}")
    return tok


def _req(method: str, path: str, tok: str, body: dict | None = None):
    url = f"{API}/{path}"
    if "?" in url:
        b, q = url.split("?", 1)
        url = b + "?" + urllib.parse.quote(q, safe="=&$,'()/")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {tok}")
    req.add_header("Accept", "application/json")
    req.add_header("OData-MaxVersion", "4.0")
    req.add_header("OData-Version", "4.0")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode()
            return (json.loads(raw) if raw else {}), r.status
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path} -> {e.code}\n{e.read().decode()[:800]}")


def main() -> None:
    tok = token()
    res, _ = _req("GET",
                  f"savedqueries?$select=savedqueryid&$filter=name eq '{VIEW_NAME}' "
                  f"and querytype eq 0 and returnedtypecode eq '{ENTITY}'", tok)
    rows = res.get("value", [])
    if not rows:
        sys.exit(f"View '{VIEW_NAME}' not found.")
    vid = rows[0]["savedqueryid"]
    _req("PATCH", f"savedqueries({vid})", tok,
         {"layoutxml": LAYOUT, "fetchxml": FETCH})
    print(f"  ~ updated view '{VIEW_NAME}' ({vid})")
    _req("POST", "PublishXml", tok,
         {"ParameterXml": f"<importexportxml><entities><entity>{ENTITY}</entity></entities></importexportxml>"})
    print("  published.")


if __name__ == "__main__":
    main()
