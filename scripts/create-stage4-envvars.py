#!/usr/bin/env python3
"""
create-stage4-envvars.py
========================
Stage 4: ALM-grade configuration for the Stock Redistribution Advisor flow.
Creates two **environment variable definitions** (+ Dev current values) so the
deficit/surplus thresholds are not magic numbers baked into the flow:

    b2b_StockThresholdLow   (Number)  default 50   — district stock below this = deficit
    b2b_StockThresholdHigh  (Number)  default 200  — adjacent district above this = surplus source

Both are added to the B2BAgg_Integration solution (via MSCRM.SolutionUniqueName
header) so `pac solution export` captures them with the flow.

Idempotent; az-CLI admin token (see PROGRESS QUIRK #1).

Usage:
    python3 scripts/create-stage4-envvars.py
"""
from __future__ import annotations

import logging
import subprocess
import sys

import requests

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

DV_URL = "https://YOUR-DATAVERSE-ORG.crm.dynamics.com"
API = f"{DV_URL}/api/data/v9.2"
SOLUTION = "B2BAgg_Integration"
TYPE_NUMBER = 100000001  # environmentvariabledefinition.type: 0=String 1=Number 2=Bool 3=JSON 4=DataSource


def get_token() -> str:
    r = subprocess.run(["az", "account", "get-access-token", "--resource", DV_URL,
                        "--query", "accessToken", "-o", "tsv"],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"az get-access-token failed: {r.stderr}")
    return r.stdout.strip()


def session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {token}",
        "OData-MaxVersion": "4.0", "OData-Version": "4.0",
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "Prefer": "return=representation",
        "MSCRM.SolutionUniqueName": SOLUTION,  # add created rows to the solution
    })
    return s


def ensure_envvar(s, schema_name, display, description, default_value, dev_value) -> None:
    # definition exists?
    q = s.get(f"{API}/environmentvariabledefinitions",
              params={"$select": "environmentvariabledefinitionid,defaultvalue",
                      "$filter": f"schemaname eq '{schema_name}'"})
    rows = q.json().get("value", []) if q.status_code == 200 else []
    if rows:
        def_id = rows[0]["environmentvariabledefinitionid"]
        log.info("  def %s exists (%s) — ensuring value", schema_name, def_id)
    else:
        body = {"schemaname": schema_name, "displayname": display,
                "description": description, "type": TYPE_NUMBER,
                "defaultvalue": str(default_value)}
        r = s.post(f"{API}/environmentvariabledefinitions", json=body)
        if r.status_code not in (200, 201):
            log.error("  def %s failed: %s %s", schema_name, r.status_code, r.text[:300]); r.raise_for_status()
        def_id = r.json()["environmentvariabledefinitionid"]
        log.info("  + def %s (%s)", schema_name, def_id)

    # current value for this (Dev) environment
    vq = s.get(f"{API}/environmentvariablevalues",
               params={"$select": "environmentvariablevalueid,value",
                       "$filter": f"_environmentvariabledefinitionid_value eq {def_id}"})
    vrows = vq.json().get("value", []) if vq.status_code == 200 else []
    if vrows:
        log.info("  value for %s exists ('%s') — skip", schema_name, vrows[0].get("value")); return
    vbody = {"value": str(dev_value),
             "EnvironmentVariableDefinitionId@odata.bind":
                 f"/environmentvariabledefinitions({def_id})"}
    r = s.post(f"{API}/environmentvariablevalues", json=vbody)
    if r.status_code not in (200, 201):
        log.error("  value %s failed: %s %s", schema_name, r.status_code, r.text[:300]); r.raise_for_status()
    log.info("  + value %s = %s (Dev)", schema_name, dev_value)


def main() -> None:
    log.info("Stage 4 env-variable creator — %s", DV_URL)
    s = session(get_token())
    who = s.get(f"{API}/WhoAmI")
    if who.status_code != 200:
        log.error("WhoAmI failed (%s) — az logged in as admin@…onmicrosoft.com?", who.status_code); sys.exit(1)

    ensure_envvar(s, "b2b_StockThresholdLow", "Stock Threshold — Low (deficit)",
                  "District total stock for a SKU below this count is flagged a deficit by the "
                  "Stock Redistribution Advisor flow.", 50, 50)
    ensure_envvar(s, "b2b_StockThresholdHigh", "Stock Threshold — High (surplus)",
                  "An adjacent district must hold more than this count to be recommended as a "
                  "redistribution source.", 200, 200)

    log.info("Done. The two env vars are members of %s; pac solution export captures them.", SOLUTION)


if __name__ == "__main__":
    main()
