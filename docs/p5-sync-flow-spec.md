# P5 — "Sync Supplier Offers" flow: build & import spec

> **Status**: authoritative build spec for the rebuilt sync flow (audit P5,
> L-1/L-2/L-3). Claude builds the design + solution scaffolding headless; **YS**
> creates connections, imports/binds, and test-runs in the maker portal. After a
> green test-run Claude re-exports the real PP-generated definition into
> `solutions/` (the source-of-truth step).
>
> Source of truth for schema: [`schema-canonical.md`](schema-canonical.md).
> Alt-key prerequisite: created by [`scripts/create-supplieroffer-altkey.py`](../scripts/create-supplieroffer-altkey.py)
> → **`b2b_offer_supplier_wh_sku`** = `(b2b_supplier + b2b_warehouse + b2b_raw_sku)`, **Active**.

---

## ✅ As-built (P5 complete, 2026-05-30)

The flow was **built in the designer** (not imported) and exported to
`solutions/B2BAgg.Integration/src/`. Verified idempotent: **201 → 201 → 201**
across two runs (no inline secret in the export; key lives in the connector
connection). Three deviations from the original plan below, all forced by
Power Automate / Dataverse behaviour:

1. **Upsert connector.** The Dataverse connector **"Update a row"** *cannot* build
   a composite-lookup alternate-key URL — it returned a bogus IIS `404`. The
   upsert is done via the **HTTP with Microsoft Entra ID (preauthorized)**
   connector (`shared_webcontents`): raw `PATCH` to the Web API alt-key URL,
   connection-managed auth (no secret). True upsert (create-or-update).
2. **Alt-key URL `_value` form.** Lookup key segments must use `_value`, not the
   logical name: `(_b2b_supplier_value=<g>,_b2b_warehouse_value=<g>,b2b_raw_sku='<sku>')`.
   The `b2b_supplier=<g>` form returns `400 0x80060888`.
3. **Scope = supplier 1 (Rosshinaopt / EN) spine.** GUIDs are resolved by Dataverse
   lookups (no hard-coded GUID — fixes L-2's worst part). Multi-supplier RU/XML
   fan-out reuses the same upsert tail and is the documented next iteration.

Actions as built: `Get_supplier` (List rows) → `Get_supplier_feed` (custom
connector) → `Parse_feed` → `For_each_offer` { `City_normalized` (Compose) →
`Get_warehouse` (List rows) → `Upsert_offer` (HTTP PATCH) }.

The sections below are the original build spec, kept for context.

---

## 1. What was wrong with the old flow (and is now fixed)

The scrubbed export `solutions/B2BAgg.Core/src/Workflows/Button-…1821A52A….json`
had four audit defects:

| # | Old behaviour | Fix in rebuild |
|---|---|---|
| **L-1** | `HTTP POST` to `b2b_supplieroffers` → **plain insert** → re-runs duplicate rows | **PATCH-upsert by alt-key** → idempotent (262→201 baseline stays put on re-run) |
| **C-1** | Inline `?code=<funcKey>` in the GET **and** inline `clientId/secret` on the POST `ActiveDirectoryOAuth` → secret leaked to git | **No secret in the flow.** Function key lives in the connection (custom connector) / an **environment variable**; Dataverse writes go through a **connection reference** (connector-managed auth) |
| **L-2** | Hard-coded `supplier_id=1` + hard-coded supplier GUID `8059989f-…` | **Supplier-agnostic**: trigger input + loop over `['1','2','3']`; supplier GUID resolved at runtime |
| **L-3** | Lived in `B2BAgg_Core` | Moves to **`B2BAgg.Integration`** solution |

---

## 2. Target architecture

Single solution-aware cloud flow, **manual (button) trigger** (no schedule — dev
API-entitlement guardrail, CLAUDE.md). Supplier-agnostic via a parametrized loop.

```
[Manual trigger]  (optional input: supplier_id; empty = all)
   │
   ├─ Initialize var  Suppliers = empty(supplier_id) ? ['1','2','3'] : [supplier_id]
   │
   └─ Apply to each  S in Suppliers
        │
        ├─ FetchSupplierFeed.GetSupplierFeed(supplier_id = S)      ← CUSTOM CONNECTOR (conn ref; key in connection)
        │
        ├─ Parse JSON  (EN canonical wrapper { supplier_id, items[] })
        │
        ├─ List rows b2b_supplier   filter b2b_name/slug = feed supplier_id  → supplierGUID
        │
        └─ Apply to each  item in items
             │
             ├─ List rows b2b_warehouse  filter b2b_city eq item.warehouse  → warehouseGUID
             │     (cache distinct cities in an object var to cut lookups)
             │
             └─ Upsert offer  →  PATCH (HTTP w/ Entra ID, conn ref):
                  /api/data/v9.2/b2b_supplieroffers(
                      b2b_supplier=<supplierGUID>,
                      b2b_warehouse=<warehouseGUID>,
                      b2b_raw_sku='<item.sku>')
                  body = mapped b2b_ columns (see §4)
```

### Heterogeneous feeds (EN / RU / XML)
The Azure Function returns each supplier's **raw** feed verbatim (by design — that
is the aggregator's whole point):
- `1 rosshinaopt` → `{ supplier_id, items[] }` (English keys) — **the flow maps this directly.**
- `2 tyrecenter-spb` → `{ postavschik, tovary[] }` (Russian keys).
- `3 koleso-ru` → `{ source, format, payload }` with an XML `<catalog>` string.

For the demo, the flow normalizes the **EN canonical** shape end-to-end. The RU/XML
variants are the documented heterogeneity story: their field-name / XML mapping is
a **per-supplier branch** (Switch on `S`) or the downstream `normalize-sku`
Function + `sku_matcher`. Keep the EN path as the working, tested spine; add the
RU/XML Switch branches only if demo time allows (they reuse the same upsert tail).

---

## 3. Connection references & environment variable (no secrets in the flow)

Claude adds these definitions to the **`B2BAgg.Integration`** solution; YS binds
them at import.

| Component | Logical name | Bound to (YS, at import) |
|---|---|---|
| Connection ref — custom connector | `b2b_FetchSupplierFeed` | the **FetchSupplierFeed** connection (holds the function key) |
| Connection ref — Dataverse (HTTP w/ Entra ID) | `b2b_DataverseHttp` | a connection authenticated as YS / the app user |
| Environment variable (string) | `b2b_FunctionBaseUrl` | `https://func-b2bagg-dev.azurewebsites.net/api` |

> The **function key is NOT an env var** — it is entered once into the custom
> connector **connection** (API-key security, header `x-functions-key`) and never
> appears in the flow definition or the solution export.

---

## 4. Field mapping (feed item → b2b_supplieroffer)

EN canonical feed item → Dataverse columns (canonical logical names):

| Feed field | → `b2b_supplieroffer` column | Note |
|---|---|---|
| `sku` | `b2b_raw_sku` | also part of alt-key |
| `product_name` | `b2b_raw_name` | |
| `price_usd` | `b2b_price` (Money) | feed quotes USD |
| `stock_qty` | `b2b_stock` (Int) | |
| `lead_days` | `b2b_lead_time_days` (Int) | NOT `b2b_lead_days` |
| `warehouse` | `b2b_warehouse_city` (String cache) | + resolve → `b2b_warehouse` lookup |
| — | `b2b_currency` = `"USD"` | |
| — | `b2b_last_synced` = `utcNow()` | |
| (resolved) | `b2b_supplier@odata.bind` | from feed `supplier_id` → b2b_supplier |
| (resolved) | `b2b_warehouse@odata.bind` | from `warehouse` city → b2b_warehouse |

`b2b_name` (offer primary) = `"<supplier> – <sku>"` (display only; not the key).

> Normalize the relic city `Saint-Petersburg` → `Saint Petersburg` in the flow
> (a `replace()` or Switch), so re-introduced data stays canonical. The existing
> tail was already purged (see `fix-offer-warehouse-tails.py`).

---

## 5. YS portal steps (the blocking sitting, ~45–75 min)

Environment everywhere = **B2BAgg-Dev** (`YOUR-DATAVERSE-ORG`).

**B1. Connections** (~10 min)
1. make.powerapps.com → **… More → Connections → + New connection**:
   - **Microsoft Dataverse** (or "HTTP with Microsoft Entra ID (preauthorized)"
     pointed at `https://YOUR-DATAVERSE-ORG.crm.dynamics.com`) — for the upsert PATCH.
   - (Custom-connector connection is created in B2 after the connector exists.)

**B2. Custom connector** (~15 min)
1. Custom connectors → **+ New → Import an OpenAPI file** →
   [`azure/openapi/fetch-supplier-feed.yaml`](../azure/openapi/fetch-supplier-feed.yaml).
2. **General**: host `func-b2bagg-dev.azurewebsites.net`, base `/api`, HTTPS.
3. **Security**: API Key, param `x-functions-key`, **Header**.
4. **Create connector** → **Test** tab → **+ New connection** → paste the
   **`FUNC_FEED_KEY`** value from `.env.local` (the P0-rotated key) → run
   `GetSupplierFeed` with `supplier_id = 1` → expect 200 + JSON.

**B3. Import flow + bind** (~15–30 min)
1. **Solutions** → import the `B2BAgg.Integration` zip Claude provides
   (or update it if already present).
2. **Connection References** step: bind `b2b_FetchSupplierFeed` → your custom-connector
   connection (B2); `b2b_DataverseHttp` → your Dataverse/Entra connection (B1).
3. **Environment variables** step: set `b2b_FunctionBaseUrl` =
   `https://func-b2bagg-dev.azurewebsites.net/api` for Dev.
4. Finish import → open the flow → **Turn on**.
   - *Fallback*: if import is rejected, rebuild the flow in the designer per §2/§4
     (Claude will sit with you action-by-action).

**B4. Test-run + idempotency check** (~5–10 min)
1. Flow → **Test → Manually → Run flow** (leave `supplier_id` empty = all 3).
2. Confirm parent + per-supplier branches succeed.
3. **Idempotency (L-1):** note offer count = **201**. Run a **second** time. Count
   must stay **201** (upsert, not insert). If it grows → the alt-key path is wrong
   → tell Claude (flow-side bug, not yours).
4. Spot-check a couple of rows: price/stock/lead-time updated, `b2b_warehouse`
   populated, `b2b_warehouse_city` clean.

**B5. Signal Claude** → "P5 flow imported, bound, test passed, 201→201".
Then Claude re-exports `B2BAgg.Integration`, unpacks into `solutions/`, removes the
old scrubbed `B2BAgg.Core/src/Workflows/…` placeholder, and closes P5.

---

## 6. Quick-reference values

| Item | Value |
|---|---|
| Env | **B2BAgg-Dev** (`YOUR-DATAVERSE-ORG`) |
| Function | `GET https://func-b2bagg-dev.azurewebsites.net/api/feed/{supplier_id}` |
| Connector auth | API Key, header `x-functions-key`, value = `.env.local FUNC_FEED_KEY` |
| supplier_id values | `1`/`2`/`3` (or `rosshinaopt`/`tyrecenter-spb`/`koleso-ru`) |
| Alt-key | `b2b_offer_supplier_wh_sku` = `(b2b_supplier + b2b_warehouse + b2b_raw_sku)` (Active) |
| Upsert URL | `PATCH …/b2b_supplieroffers(b2b_supplier=<id>,b2b_warehouse=<id>,b2b_raw_sku='<sku>')` |
| Idempotency baseline | **201** offers → must stay 201 on 2nd run |
| Solution | `B2BAgg.Integration` |
