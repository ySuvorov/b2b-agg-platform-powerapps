#!/usr/bin/env python3
"""
create-security-role.py — create the "B2B Procurement Ops" custom security role
in B2BAgg-Dev and add it to the B2BAgg_Core solution. (Audit A-4.)

A real, minimal custom role that grants CRUD on the b2b_ operational tables —
the artifact the audit asked for so the "security roles" claim is backed by an
exported component rather than prose. Layer it on top of a base role (e.g.
"Basic User") for full app access; this role only carries the b2b_* privileges.

Idempotent: re-running finds the existing role and re-asserts privileges.

Auth: az-CLI token (QUIRK #1) — no device code, no client secret.
  az login   # as <admin-upn>
  python3 scripts/create-security-role.py

Requirements: pip install requests
"""

from __future__ import annotations

import subprocess
import sys
import requests

DATAVERSE_URL = "https://YOUR-DATAVERSE-ORG.crm.dynamics.com"
API = f"{DATAVERSE_URL}/api/data/v9.2"
SOLUTION = "B2BAgg_Core"
ROLE_NAME = "B2B Procurement Ops"

# b2b_ tables the role gets access to.
ENTITIES = [
    "b2b_region", "b2b_supplier", "b2b_warehouse", "b2b_canonicalproduct",
    "b2b_supplieroffer", "b2b_order", "b2b_orderline", "b2b_rfq",
    "b2b_skumap", "b2b_dataconflict",
]
# Privilege verbs granted on each table, with depth.
# Depth: Basic (user) | Local (BU) | Deep (parent:child BU) | Global (org).
# Org-owned tables only honour Global; user-owned honour all — Global is safe for both.
ACTIONS = ["Create", "Read", "Write", "Delete", "Append", "AppendTo"]
DEPTH = "Global"


def token() -> str:
    r = subprocess.run(
        ["az", "account", "get-access-token", "--resource", DATAVERSE_URL,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        raise SystemExit(f"az get-access-token failed: {r.stderr.strip()} (run `az login`)")
    return r.stdout.strip()


def main() -> None:
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {token()}",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
    })

    # 1. Root business unit
    bu = s.get(f"{API}/businessunits",
               params={"$filter": "parentbusinessunitid eq null",
                       "$select": "businessunitid"}, timeout=30)
    bu.raise_for_status()
    bu_id = bu.json()["value"][0]["businessunitid"]
    print(f"Root business unit: {bu_id}")

    # 2. Create-or-find the role
    existing = s.get(f"{API}/roles",
                     params={"$filter": f"name eq '{ROLE_NAME}' and _businessunitid_value eq {bu_id}",
                             "$select": "roleid"}, timeout=30)
    existing.raise_for_status()
    rows = existing.json()["value"]
    if rows:
        role_id = rows[0]["roleid"]
        print(f"Role already exists: {role_id}")
    else:
        r = s.post(f"{API}/roles", json={
            "name": ROLE_NAME,
            "businessunitid@odata.bind": f"/businessunits({bu_id})",
        }, timeout=30)
        r.raise_for_status()
        role_id = r.headers["OData-EntityId"].split("(")[1].rstrip(")")
        print(f"Created role: {role_id}")

    # 3. Resolve privilege ids for every prv{Action}{entity}
    wanted = [f"prv{a}{e}" for e in ENTITIES for a in ACTIONS]
    # chunk the $filter (URL length) — 25 names per query
    name_to_id: dict[str, str] = {}
    for i in range(0, len(wanted), 25):
        chunk = wanted[i:i + 25]
        flt = " or ".join(f"name eq '{n}'" for n in chunk)
        r = s.get(f"{API}/privileges",
                  params={"$filter": flt, "$select": "name,privilegeid"}, timeout=60)
        r.raise_for_status()
        for p in r.json()["value"]:
            name_to_id[p["name"]] = p["privilegeid"]

    privileges = []
    missing = []
    for n in wanted:
        pid = name_to_id.get(n)
        if pid:
            privileges.append({"PrivilegeId": pid, "Depth": DEPTH})
        else:
            missing.append(n)
    if missing:
        print(f"  (skipped {len(missing)} privileges not found, e.g. {missing[:3]})")
    print(f"Granting {len(privileges)} privileges at depth {DEPTH} ...")

    # 4. AddPrivilegesRole (replaces/sets the role's privilege depths)
    r = s.post(f"{API}/roles({role_id})/Microsoft.Dynamics.CRM.AddPrivilegesRole",
               json={"Privileges": privileges}, timeout=120)
    if r.status_code >= 300:
        raise SystemExit(f"AddPrivilegesRole failed {r.status_code}: {r.text}")
    print("  privileges applied.")

    # 5. Add the role to the B2BAgg_Core solution (ComponentType 20 = Role)
    r = s.post(f"{API}/AddSolutionComponent", json={
        "ComponentId": role_id,
        "ComponentType": 20,
        "SolutionUniqueName": SOLUTION,
        "AddRequiredComponents": False,
    }, timeout=60)
    if r.status_code >= 300:
        raise SystemExit(f"AddSolutionComponent failed {r.status_code}: {r.text}")
    print(f"Role added to solution {SOLUTION}.")
    print(f"\nDone. Role '{ROLE_NAME}' ({role_id}) ready. Re-export Core to capture it.")


if __name__ == "__main__":
    sys.exit(main())
