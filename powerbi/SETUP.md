# Power BI Setup Guide — B2BAgg Analytics

> This guide walks through provisioning the `B2BAgg-Analytics` workspace,
> connecting Power BI Desktop to Dataverse, importing DAX measures, and
> publishing the four core reports.

## Requirements

| Item | Version / Plan |
|---|---|
| Power BI Desktop | Latest (download from https://powerbi.microsoft.com/desktop) |
| Power BI licence | **Power BI Pro** or **Power Platform Developer Plan** (includes Pro features) |
| Dataverse environment | `B2BAgg-Dev` — `https://YOUR-DATAVERSE-ORG.crm.dynamics.com/` |
| Azure CLI | 2.x (for running `setup-powerbi.py`) |
| Python | 3.9+ with `requests` installed |

> Note: embedding Power BI tiles into Code App or MDA requires every consuming
> user to hold a Power BI Pro licence. The 60-day trial is sufficient for the
> demo window.

---

## Step 1 — Provision the Workspace and Push Dataset

Run the provisioning script once from the repo root:

```bash
pip3 install requests          # one-time
python3 scripts/setup-powerbi.py
```

The script will:

1. Acquire a Power BI token via `az account get-access-token`.
2. Create (or find) the `B2BAgg-Analytics` workspace.
3. Create (or find) the `B2BAgg Market Data` push dataset with four tables.
4. Push 24 SupplierOffers rows, 7 Orders, 3 Suppliers, and 6 Regions.
5. Write workspace / dataset IDs to `powerbi/workspace-ids.json`.

Expected output:

```
=== Power BI Setup Complete ===
Workspace:    B2BAgg-Analytics
Workspace ID: <guid>
Dataset:      B2BAgg Market Data
Dataset ID:   <guid>
App URL:      https://app.powerbi.com/groups/<guid>
```

Workspace ID is also recorded in `docs/setup-log.md` (Power BI Workspace
section) and in `powerbi/workspace-ids.json`.

---

## Step 2 — Connect Power BI Desktop to Dataverse

> Use Dataverse connector for the full production dataset.
> The push dataset (Step 1) is a live preview / demo layer.

1. Open Power BI Desktop.
2. **Home → Get data → More → Power Platform → Dataverse**.
3. Enter the environment URL:
   ```
   https://YOUR-DATAVERSE-ORG.crm.dynamics.com/
   ```
4. Sign in with `<admin-upn>` (MFA required).
5. In the Navigator, select the following tables:

   | Table (logical name) | Display name |
   |---|---|
   | `b2b_supplieroffer` | Supplier Offers |
   | `b2b_canonicalproduct` | Canonical Products |
   | `b2b_supplier` | Suppliers |
   | `b2b_region` | Regions |
   | `b2b_order` | Orders |

6. Click **Transform Data** (do not load yet).

### Recommended transformations in Power Query

- `b2b_supplieroffer`: keep columns `b2b_rawsku`, `b2b_price`, `b2b_stock`,
  `b2b_warehouse`, `b2b_season`, `b2b_leaddays`, `createdon`,
  and the related supplier/product lookups.
- `b2b_canonicalproduct`: keep `b2b_brand`, `b2b_model`, `b2b_width`,
  `b2b_profile`, `b2b_diameter`, `b2b_country`.
- Rename columns to friendly names (strip the `b2b_` prefix).
- Set correct data types (decimals for price, whole numbers for stock/dims).

Click **Close & Apply**.

---

## Step 3 — Add DAX Measures

All measures live in `powerbi/measures.dax`. To add them:

1. In the **Data** pane, right-click a table → **New measure**.
2. Paste the measure expression from `measures.dax`.
3. Repeat for each measure.

Alternatively, use the **External Tools → DAX Studio** to bulk-import.

Key measures by report:

| Report | Primary measures |
|---|---|
| Regional Demand & Stock | `Total Stock`, `Stock by Region`, `Region Stock Share %`, `Low Stock Alert` |
| Supplier Scorecard | `Fill Rate %`, `Avg Price per Supplier`, `Price Competitiveness %`, `Supplier Stock Rank` |
| Top-moving SKUs | `Stock Rank`, `SKUs in Top 10`, `Best Price`, `Inventory Value` |
| Price Spread | `Price Spread`, `Min Price this Season`, `Summer vs Winter Price Ratio`, `Country Price Premium` |
| Orders | `Total Revenue`, `Realised Revenue`, `Avg Order Value`, `Cancellation Rate %` |

---

## Step 4 — Build the Four Reports

### Report 1: Regional Demand & Stock

**Purpose**: show where tyre inventory is concentrated across Russia's federal districts.

| Element | Configuration |
|---|---|
| Visual type | **Filled Map** (choropleth) — one per region |
| Location field | `Region` (string: ЦФО, СЗФО, etc.) |
| Color saturation | `Total Stock` measure |
| Tooltips | `Distinct SKU Count`, `Avg Lead Days` |
| Bar chart (supporting) | `Region` on X-axis, `Total Stock` on Y-axis |
| Slicer | `Season` (Summer / Winter) |
| Slicer | `Brand` |
| KPI card | `Low Stock Alert` — highlight when value = "⚠ Low Stock" |

> Tip: set the Map visual's **Map style** to "Road" and language to Russian
> for authentic region label rendering.

---

### Report 2: Supplier Scorecard

**Purpose**: rank the three suppliers on price, fill rate, and product breadth.

| Element | Configuration |
|---|---|
| Visual type | **Table** or **Matrix** with conditional formatting |
| Rows | `SupplierName` |
| Columns / Values | `Offer Count`, `Fill Rate %`, `Avg Price per Supplier`, `Price Competitiveness %`, `Supplier Stock Rank` |
| Conditional formatting | `Fill Rate %`: green > 80 %, amber 50–80 %, red < 50 % |
| Bar chart | `SupplierName` on Y-axis, `Total Stock` on X-axis (sorted DESC) |
| Slicer | `Brand` |
| Slicer | `Season` |
| KPI card (×3) | One per supplier — `Avg Price per Supplier` vs. prior period target |

---

### Report 3: Top-moving SKUs

**Purpose**: identify which SKU/product combinations have the highest inventory velocity.

| Element | Configuration |
|---|---|
| Visual type | **Bar chart** (horizontal, sorted DESC by stock) |
| Y-axis | `ProductName` |
| X-axis | `Total Stock` |
| Filter | `Stock Rank <= 10` (using `Stock Rank` measure as page filter) |
| Color legend | `Brand` |
| Supporting table | `RawSku`, `SupplierName`, `Stock`, `Best Price`, `Supplier Count per SKU` |
| Slicer | `Diameter` (15 / 16 / 17 / 18) |
| Slicer | `Season` |
| Card | `Inventory Value` (total value of visible SKUs) |

---

### Report 4: Price Spread & Competitiveness

**Purpose**: visualise price range per product across suppliers and seasons.

| Element | Configuration |
|---|---|
| Visual type | **Error bar chart** or **Box-and-Whisker** (min / avg / max price per product) |
| X-axis | `ProductName` |
| Values | `Min Price this Season`, `Avg Price per Supplier`, `Price Spread` |
| Supporting line chart | `Diameter` on X-axis, `Avg Price per Supplier` on Y-axis, `Season` as legend |
| Scatter chart | X = `Fill Rate %`, Y = `Avg Price per Supplier`, size = `Offer Count`, legend = `SupplierName` |
| Slicer | `Season` |
| Slicer | `Country` (France / Germany / Japan) |
| KPI card | `Summer vs Winter Price Ratio` |
| KPI card | `Country Price Premium` (vs. cheapest origin) |

---

## Step 5 — Publish to Workspace

1. **Home → Publish**.
2. Select destination: **B2BAgg-Analytics**.
3. Confirm overwrite if a prior version exists.
4. Open the link shown after publish:
   `https://app.powerbi.com/groups/<workspace_id>/reports/<report_id>`

The workspace ID can be found in:
- `powerbi/workspace-ids.json` (generated by `setup-powerbi.py`)
- `docs/setup-log.md` → Power BI Workspace section

---

## Step 6 — Embed Tiles in Code App and MDA

### Code App (`/insights` page)

1. In Power BI service, open the report → **File → Embed report → Website or portal**.
2. Copy the embed URL.
3. In `apps/buyer-code-app/src/pages/InsightsPage.tsx`, set the `src` of the
   `<iframe>` to the embed URL.
4. Wrap in the Fluent UI `Card` component; set height to `600px`.

### Model-driven App (Operations MDA)

1. In Power BI service, pin a visual from Report 1 or Report 2 to a dashboard.
2. In the MDA form XML, add a **Power BI Embedded** control (available under
   `<controlDescriptions>`) pointing to the dashboard tile.
3. Alternatively, add a Power BI Dashboard page via **App designer → Pages →
   Power BI**.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `401 Unauthorized` from `setup-powerbi.py` | `az` token expired | `az login` then re-run |
| Workspace not found after create | API propagation delay | Wait 30 s and re-run (script is idempotent) |
| "No data" in Dataverse connector | Environment URL wrong | Verify URL in `docs/setup-log.md` |
| Map visual shows blank regions | Region strings not matching Power BI geo categories | Change `Region` column data category to **Place** in Data view |
| Push dataset rows not visible | Dataset was just created | Refresh the dataset in PBI service, or wait 1–2 min |
| Embed tile shows "Content not available" | User lacks Power BI Pro | Assign Pro trial via M365 admin centre |
