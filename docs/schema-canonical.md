# Canonical Dataverse Schema — Source of Truth

> **Status**: authoritative. Generated from the **live B2BAgg-Dev** environment
> on 2026-05-28 and exported into `solutions/B2BAgg.Core/src` (audit H-3 fixed).
> **Naming rule (kills audit M-5)**: the **`snake_case` logical names below are
> canonical**. Docs, Code App, scripts, flows and OpenAPI MUST match these exact
> strings. When in doubt, the exported `Entity.xml` wins, not prose.
>
> Downstream consumers: [P2 Code App](audit/2026-05-28-remediation-plan.md),
> seed scripts (P6), the sync flow (P5).

## Entities (10) — logical name, primary name, collection (EntitySet)

| Entity | Primary name attr | EntitySet (OData collection) |
|---|---|---|
| `b2b_region` | `b2b_name` | `b2b_regions` |
| `b2b_supplier` | `b2b_name` | `b2b_suppliers` |
| `b2b_warehouse` | `b2b_name` | `b2b_warehouses` |
| `b2b_canonicalproduct` | `b2b_name` | `b2b_canonicalproducts` |
| `b2b_supplieroffer` | `b2b_name` | `b2b_supplieroffers` |
| `b2b_order` | **`b2b_order_number`** | `b2b_orders` |
| `b2b_orderline` | **`b2b_line_ref`** | `b2b_orderlines` |
| `b2b_rfq` | `b2b_rfq_number` | `b2b_rfqs` |
| `b2b_skumap` | `b2b_name` | `b2b_skumaps` |
| `b2b_dataconflict` | `b2b_name` | `b2b_dataconflicts` |

> ⚠️ `b2b_order` primary name is `b2b_order_number` (NOT `b2b_name`) and
> `b2b_orderline` is `b2b_line_ref`. The Code App currently reads `b2b_name` and
> omits `b2b_line_ref` on create — both wrong (audit P1-4 / Codex #2). Fix in P2.

## Lookups & `$expand` navigation property names

The single-valued navigation property used in OData `$expand` **equals the
lookup logical name** (not `..._id` unless the attribute itself ends in `_id`):

| On entity | Lookup attr (= `$expand` nav prop) | → references |
|---|---|---|
| `b2b_supplieroffer` | `b2b_supplier` | `b2b_supplier` |
| `b2b_supplieroffer` | `b2b_canonical_product` | `b2b_canonicalproduct` |
| `b2b_supplieroffer` | `b2b_warehouse` | `b2b_warehouse` *(new, P1)* |
| `b2b_warehouse` | `b2b_region` | `b2b_region` |
| `b2b_orderline` | `b2b_order_id` | `b2b_order` |
| `b2b_orderline` | `b2b_supplieroffer_id` | `b2b_supplieroffer` |
| `b2b_skumap` | `b2b_supplier` | `b2b_supplier` |
| `b2b_skumap` | `b2b_canonical_product` | `b2b_canonicalproduct` |
| `b2b_dataconflict` | `b2b_supplier_offer` | `b2b_supplieroffer` |
| `b2b_dataconflict` | `b2b_suggested_canonical` | `b2b_canonicalproduct` |
| `b2b_dataconflict` | `b2b_reviewed_by` | `systemuser` |

> ⚠️ Code App used `$expand=b2b_supplier_id(...)`; correct is `b2b_supplier`
> (audit H-1). For writes, bind with `<navprop>@odata.bind`, e.g.
> `b2b_order_id@odata.bind`, `b2b_supplieroffer_id@odata.bind`,
> `b2b_warehouse@odata.bind`, `b2b_supplier@odata.bind`.

## Key columns (the ones code/scripts get wrong)

**`b2b_supplieroffer`** — `b2b_raw_sku`, `b2b_raw_name`, `b2b_price` (Money),
`b2b_price_base` (Money), `b2b_currency`, `b2b_stock` (Int),
**`b2b_lead_time_days`** (Int — NOT `b2b_lead_days`/`b2b_leaddays`),
**`b2b_warehouse_city`** (String — denormalized cache, kept),
**`b2b_warehouse`** (lookup — new grain), `b2b_last_synced` (DateTime),
`b2b_match_method` (Picklist), `b2b_match_confidence` (Decimal),
`b2b_canonical_product` (lookup), `b2b_supplier` (lookup).
There is **no** `b2b_year` and **no** `b2b_country` (audit H-1).

**`b2b_canonicalproduct`** — `b2b_brand`, `b2b_model`, `b2b_season` (Picklist),
`b2b_width`/`b2b_profile`/`b2b_diameter` (Int), `b2b_load_index` (Int),
`b2b_speed_index` (String), `b2b_ean`, `b2b_normalized_name`,
plus SKU engine: `b2b_homologation` (Picklist), `b2b_runflat` (Bool),
`b2b_extraload` (Bool), `b2b_canonical_key` (String).

**`b2b_warehouse`** *(new P1)* — `b2b_name`, `b2b_code`, `b2b_city`,
`b2b_capacity` (Int), `b2b_region` (lookup).

**`b2b_order`** — `b2b_order_number`, `b2b_status` (Picklist), `b2b_total_amount`
(Money), `b2b_total_amount_base` (Money), `b2b_currency_code`.

**`b2b_orderline`** — `b2b_line_ref`, `b2b_qty` (Int), `b2b_unit_price` (Money),
`b2b_unit_price_base` (Money), `b2b_order_id` (lookup), `b2b_supplieroffer_id` (lookup).

## Option-set values — ⚠️ TWO conventions live in Dev (use exactly these)

There are two numbering series in the live environment. **Do not renumber**
(it would orphan existing data). Match these exact integers:

| Attribute | Values (value → label) |
|---|---|
| `b2b_order.b2b_status` | `100000000` Draft · `100000001` Confirmed · `100000002` Shipped |
| `b2b_canonicalproduct.b2b_season` | `10000` Summer · `10001` WinterStudded · `10002` WinterFriction · `10003` AllSeason |
| `b2b_supplieroffer.b2b_match_method` | `10000` Cache · `10001` ExactKey · `10002` Fuzzy · `10003` AI · `10004` Manual |
| `b2b_dataconflict.b2b_status` | `10000` Pending · `10001` NeedsReview · `10002` NewCandidate · `10003` Approved · `10004` Rejected · `10005` AutoResolved |
| `b2b_canonicalproduct.b2b_homologation` | `10000` None · `10001` Star_BMW · `10002` MO_Mercedes · `10003` MOE_Mercedes · `10004` N0_Porsche · `10005` N1_Porsche · `10006` AO_Audi · `10007` LR_LandRover · `10008` VOL_Volvo · `10009` MGT_Maserati |

> ⚠️ Code App writes `b2b_status: 10000` for orders — wrong; order status is the
> `100000000` series (audit P1-4). Booleans `b2b_runflat`/`b2b_extraload` use
> `1`/`0`. Define these as named TS enums in P2 (audit L-6).

## Alternate keys (idempotent upsert — for P5 flow)

- `b2b_skumap`: composite alt key on (`b2b_supplier`, `b2b_raw_sku`).
- `b2b_supplieroffer`: upsert grain for the sync flow is (`b2b_warehouse`/city +
  `b2b_raw_sku`). Verify/create the alt key before wiring the flow PATCH-upsert.

## Solution membership

All 10 entities are RootComponents of **`B2BAgg_Core`** (unmanaged) and exported
to `solutions/B2BAgg.Core/src/Entities/`. The sync flow lives under
`src/Workflows/` (scrubbed; rebuilt in P5). Module split into `B2BAgg.AI`
(skumap/dataconflict) and `B2BAgg.Integration` (flows) is **deferred** — noted in
PROGRESS as a follow-up ALM refinement.
