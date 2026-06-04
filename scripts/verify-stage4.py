#!/usr/bin/env python3
"""
verify-stage4.py
================
Stage 4 verification + demo-hygiene helpers (az-token Web API, admin).

Subcommands:
  signals            List current b2b_marketsignal rows (any type).
  clear-redist       Delete all RedistributionAdvice signals (clean slate before a demo run).
  expect-redist      Assert the СКФО←ЮФО RedistributionAdvice exists (post flow run).
  expect-stockshortage   Assert at least one StockShortage signal exists (post Low Stock run).
  district-stock     Print the per-district SUM(stock) the flow sees (the aggregate).
  lowstock-fire OFFER_NAME   Set one offer's b2b_stock -> 0 (fires Low Stock Alert), prints old value.
  lowstock-reset OFFER_NAME OLD   Restore an offer's b2b_stock to OLD.

Usage:
    python3 scripts/verify-stage4.py district-stock
    python3 scripts/verify-stage4.py clear-redist
    python3 scripts/verify-stage4.py expect-redist
"""
from __future__ import annotations

import subprocess
import sys
import urllib.parse

import requests

DV_URL = "https://YOUR-DATAVERSE-ORG.crm.dynamics.com"
API = f"{DV_URL}/api/data/v9.2"
OPT = 10000
REDIST = OPT + 3  # b2b_type RedistributionAdvice
STOCKSHORT = OPT + 2  # b2b_type StockShortage

AGG_FETCH = (
    '<fetch aggregate="true"><entity name="b2b_supplieroffer">'
    '<attribute name="b2b_stock" alias="district_stock" aggregate="sum"/>'
    '<link-entity name="b2b_warehouse" from="b2b_warehouseid" to="b2b_warehouse" alias="wh">'
    '<link-entity name="b2b_region" from="b2b_regionid" to="b2b_region" alias="reg">'
    '<attribute name="b2b_name" alias="district" groupby="true"/>'
    '<attribute name="b2b_regionid" alias="district_id" groupby="true"/>'
    '</link-entity></link-entity>'
    '<order alias="district_stock" descending="true"/>'
    '</entity></fetch>'
)


def token() -> str:
    r = subprocess.run(["az", "account", "get-access-token", "--resource", DV_URL,
                        "--query", "accessToken", "-o", "tsv"],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise SystemExit(f"az get-access-token failed: {r.stderr}")
    return r.stdout.strip()


def sess() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token()}",
                      "OData-MaxVersion": "4.0", "OData-Version": "4.0",
                      "Accept": "application/json",
                      "Content-Type": "application/json; charset=utf-8"})
    return s


def cmd_signals(s):
    r = s.get(f"{API}/b2b_marketsignals",
              params={"$select": "b2b_name,b2b_type,b2b_severity,b2b_source,createdon",
                      "$orderby": "createdon desc", "$top": 50})
    rows = r.json().get("value", [])
    print(f"{len(rows)} market signal(s):")
    for x in rows:
        print(f"  [{x.get('b2b_type@OData.Community.Display.V1.FormattedValue')}] "
              f"{x.get('b2b_name')}  "
              f"({x.get('b2b_severity@OData.Community.Display.V1.FormattedValue')})")


def cmd_clear_redist(s):
    r = s.get(f"{API}/b2b_marketsignals",
              params={"$select": "b2b_marketsignalid,b2b_name",
                      "$filter": f"b2b_type eq {REDIST}"})
    rows = r.json().get("value", [])
    for x in rows:
        d = s.delete(f"{API}/b2b_marketsignals({x['b2b_marketsignalid']})")
        print(("  deleted " if d.status_code in (200, 204) else f"  FAILED {d.status_code} ")
              + x.get("b2b_name", ""))
    print(f"cleared {len(rows)} RedistributionAdvice row(s).")


def cmd_expect_redist(s):
    r = s.get(f"{API}/b2b_marketsignals",
              params={"$select": "b2b_name,b2b_severity",
                      "$filter": f"b2b_type eq {REDIST}",
                      "$expand": "b2b_region($select=b2b_name),b2b_targetregion($select=b2b_name)"})
    rows = r.json().get("value", [])
    if not rows:
        print("✗ no RedistributionAdvice signals — run the flow first."); sys.exit(1)
    ok = False
    for x in rows:
        reg = (x.get("b2b_region") or {}).get("b2b_name")
        tgt = (x.get("b2b_targetregion") or {}).get("b2b_name")
        sev = x.get("b2b_severity@OData.Community.Display.V1.FormattedValue")
        print(f"  ✓ {reg} ← {tgt}  ({sev})")
        if reg == "North Caucasian Federal District" and tgt == "Southern Federal District":
            ok = True
    print("PASS: expected СКФО←ЮФО signal present." if ok
          else "WARN: signals exist but not the expected СКФО←ЮФО pair.")
    sys.exit(0 if ok else 2)


def cmd_expect_stockshortage(s):
    r = s.get(f"{API}/b2b_marketsignals",
              params={"$select": "b2b_name,b2b_severity",
                      "$filter": f"b2b_type eq {STOCKSHORT}",
                      "$orderby": "createdon desc"})
    rows = r.json().get("value", [])
    if not rows:
        print("✗ no StockShortage signals — run the Low Stock Alert flow first."); sys.exit(1)
    for x in rows[:10]:
        print(f"  ✓ {x.get('b2b_name')}  "
              f"({x.get('b2b_severity@OData.Community.Display.V1.FormattedValue')})")
    print(f"PASS: {len(rows)} StockShortage signal(s) present.")


def cmd_district_stock(s):
    q = urllib.parse.quote(AGG_FETCH)
    r = s.get(f"{API}/b2b_supplieroffers?fetchXml={q}")
    rows = r.json().get("value", [])
    print(f"{len(rows)} district(s) with stock (7 total; absent = 0 = deficit):")
    for x in rows:
        print(f"  {x.get('district'):38} {x.get('district_stock')}")


def _find_offer(s, name):
    r = s.get(f"{API}/b2b_supplieroffers",
              params={"$select": "b2b_supplierofferid,b2b_raw_name,b2b_stock",
                      "$filter": f"contains(b2b_raw_name,'{name}')", "$top": 1})
    rows = r.json().get("value", [])
    if not rows:
        raise SystemExit(f"no offer matching '{name}'")
    return rows[0]


def cmd_lowstock_fire(s, name):
    o = _find_offer(s, name)
    old = o.get("b2b_stock")
    s.patch(f"{API}/b2b_supplieroffers({o['b2b_supplierofferid']})", json={"b2b_stock": 0})
    print(f"set '{o['b2b_raw_name']}' stock {old} -> 0  (id {o['b2b_supplierofferid']}). "
          f"Reset later: lowstock-reset '{name}' {old}")


def cmd_lowstock_reset(s, name, old):
    o = _find_offer(s, name)
    s.patch(f"{API}/b2b_supplieroffers({o['b2b_supplierofferid']})", json={"b2b_stock": int(old)})
    print(f"restored '{o['b2b_raw_name']}' stock -> {old}")


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    s = sess()
    cmd, rest = sys.argv[1], sys.argv[2:]
    dispatch = {
        "signals": lambda: cmd_signals(s),
        "clear-redist": lambda: cmd_clear_redist(s),
        "expect-redist": lambda: cmd_expect_redist(s),
        "expect-stockshortage": lambda: cmd_expect_stockshortage(s),
        "district-stock": lambda: cmd_district_stock(s),
        "lowstock-fire": lambda: cmd_lowstock_fire(s, rest[0]),
        "lowstock-reset": lambda: cmd_lowstock_reset(s, rest[0], rest[1]),
    }
    if cmd not in dispatch:
        print(__doc__); sys.exit(1)
    dispatch[cmd]()


if __name__ == "__main__":
    main()
