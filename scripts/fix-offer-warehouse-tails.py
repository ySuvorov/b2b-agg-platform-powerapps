#!/usr/bin/env python3
"""
fix-offer-warehouse-tails.py
============================
P5 data-tail cleanup. The old hard-coded sync flow created 61 b2b_supplieroffer
rows with an EMPTY b2b_warehouse lookup and one relic city string
'Saint-Petersburg' (dash) instead of the canonical 'Saint Petersburg'.

This script (idempotent, az-token Web API — see PROGRESS QUIRK #1):
  1. Normalizes the b2b_warehouse_city cache (fixes the dashed relic).
  2. Re-links each null-warehouse offer to the warehouse matching its city.
  3. Detects collisions against the now-Active alt-key
     b2b_offer_supplier_wh_sku (supplier+warehouse+raw_sku): if re-linking a
     legacy offer would duplicate an existing canonical offer, it is a stale
     duplicate from the old flow — DELETED. Otherwise the offer is kept + linked.

Re-running is safe: once linked/cleaned there are no null-warehouse rows left.

Usage:
    python3 scripts/fix-offer-warehouse-tails.py            # apply
    python3 scripts/fix-offer-warehouse-tails.py --dry-run  # report only
"""
from __future__ import annotations
import subprocess, sys, logging
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

DV = "https://YOUR-DATAVERSE-ORG.crm.dynamics.com"
API = f"{DV}/api/data/v9.2"
DRY = "--dry-run" in sys.argv

# canonical city normalization (relic → warehouse city)
CITY_FIX = {"Saint-Petersburg": "Saint Petersburg"}


def token() -> str:
    return subprocess.run(["az","account","get-access-token","--resource",DV,
                           "--query","accessToken","-o","tsv"],
                          capture_output=True,text=True,timeout=30).stdout.strip()


def main() -> None:
    s = requests.Session()
    s.headers.update({"Authorization":f"Bearer {token()}","Accept":"application/json",
                      "OData-MaxVersion":"4.0","OData-Version":"4.0",
                      "Content-Type":"application/json; charset=utf-8"})
    if s.get(f"{API}/WhoAmI").status_code != 200:
        log.error("auth failed"); sys.exit(1)
    log.info("Mode: %s", "DRY-RUN" if DRY else "APPLY")

    wh = {w["b2b_city"]: w["b2b_warehouseid"]
          for w in s.get(f"{API}/b2b_warehouses",
                         params={"$select":"b2b_city,b2b_warehouseid"}).json()["value"]}
    log.info("warehouses by city: %s", list(wh))

    offers = s.get(f"{API}/b2b_supplieroffers",
                   params={"$select":"b2b_supplierofferid,b2b_warehouse_city,"
                           "_b2b_warehouse_value,_b2b_supplier_value,b2b_raw_sku",
                           "$top":"5000"}).json()["value"]
    null_wh = [o for o in offers if not o.get("_b2b_warehouse_value")]
    log.info("null-warehouse offers: %d", len(null_wh))

    # index existing (supplier, warehouse, raw_sku) -> id for collision detection
    triple = {}
    for o in offers:
        if o.get("_b2b_warehouse_value"):
            triple[(o["_b2b_supplier_value"], o["_b2b_warehouse_value"],
                    o.get("b2b_raw_sku"))] = o["b2b_supplierofferid"]

    linked = cleaned = deleted = errors = skipped = 0
    for o in null_wh:
        oid = o["b2b_supplierofferid"]
        raw_city = o.get("b2b_warehouse_city") or ""
        city = CITY_FIX.get(raw_city, raw_city)
        wid = wh.get(city)
        if not wid:
            log.warning("  offer %s: city %r has no warehouse — skip", oid, raw_city); skipped += 1; continue

        key = (o["_b2b_supplier_value"], wid, o.get("b2b_raw_sku"))
        if key in triple:
            log.info("  offer %s: collides with canonical %s on %s → DELETE legacy dup",
                     oid, triple[key], key)
            if not DRY:
                r = s.delete(f"{API}/b2b_supplieroffers({oid})")
                if r.status_code in (200,204): deleted += 1
                else: log.error("    delete failed %s %s", r.status_code, r.text[:200]); errors += 1
            else:
                deleted += 1
            continue

        patch = {"b2b_warehouse@odata.bind": f"/b2b_warehouses({wid})"}
        if city != raw_city:
            patch["b2b_warehouse_city"] = city
            cleaned += 1
        if not DRY:
            r = s.patch(f"{API}/b2b_supplieroffers({oid})", json=patch)
            if r.status_code in (200,204):
                linked += 1; triple[key] = oid
            else:
                log.error("  offer %s patch failed %s %s", oid, r.status_code, r.text[:200]); errors += 1
        else:
            linked += 1; triple[key] = oid

    log.info("Result: linked=%d cleaned-city=%d deleted-dup=%d skipped=%d errors=%d",
             linked, cleaned, deleted, skipped, errors)
    if errors: sys.exit(2)


if __name__ == "__main__":
    main()
