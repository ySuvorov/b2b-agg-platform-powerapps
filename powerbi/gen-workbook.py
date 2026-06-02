#!/usr/bin/env python3
"""
gen-workbook.py — generate the Power BI import workbook from seed data.

Produces powerbi/B2BAgg-Analytics-data.xlsx with two sheets:
  - SupplierOffers : 201 real offers, denormalized (region/season/brand/...)
  - Orders         : mock order headers (orders are runtime artifacts)

This is the upload source for the **import semantic model** path in
powerbi/SETUP.md (browser web-authoring, Mac-safe). An import model — unlike the
push dataset — supports the DAX measures in powerbi/measures.dax.

Run from repo root:
    python3 powerbi/gen-workbook.py
"""
import importlib.util
import os
from openpyxl import Workbook

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)

# Reuse the denormalization in scripts/setup-powerbi.py (hyphenated filename).
spec = importlib.util.spec_from_file_location(
    "pbisetup", os.path.join(REPO, "scripts", "setup-powerbi.py"))
pbi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pbi)

data = pbi.load_seed_data()

OFFER_COLS = ["OfferId", "RawSku", "SupplierName", "ProductName", "Brand",
              "Model", "Width", "Profile", "Diameter", "Season", "Warehouse",
              "Region", "Stock", "Price", "LeadDays", "SyncedAt"]
ORDER_COLS = ["OrderId", "OrderName", "TotalAmount", "Status", "CreatedOn",
              "LineCount"]


def add_sheet(wb, title, cols, rows, first=False):
    ws = wb.active if first else wb.create_sheet()
    ws.title = title
    ws.append(cols)
    for r in rows:
        ws.append([r.get(c) for c in cols])


wb = Workbook()
add_sheet(wb, "SupplierOffers", OFFER_COLS, data["SupplierOffers"], first=True)
add_sheet(wb, "Orders", ORDER_COLS, data["Orders"])

out = os.path.join(REPO, "powerbi", "B2BAgg-Analytics-data.xlsx")
wb.save(out)
print(f"Wrote {out}")
print(f"  SupplierOffers: {len(data['SupplierOffers'])} rows")
print(f"  Orders:         {len(data['Orders'])} rows")
