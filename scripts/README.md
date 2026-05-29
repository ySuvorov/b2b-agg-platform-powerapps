# Scripts

Python utilities for building and seeding the B2BAgg Dataverse Dev environment.
All schema/seed scripts authenticate with an **az-CLI token** (the admin account
is logged into `az`) — no device code, no client secret (see PROGRESS QUIRK #1).

## Schema creation (run once, in order)

| Script | Purpose | Phase |
|---|---|---|
| `create-tables-api.py` | Create the 4 core tables (`b2b_region`, `b2b_supplier`, `b2b_canonicalproduct`, `b2b_supplieroffer`) via the Web API `EntityDefinitions` endpoint. | MVP1 |
| `create-order-tables.py` | Create `b2b_order`, `b2b_orderline`, `b2b_rfq` + their lookups. | MVP1 |
| `create-matching-tables.py` | Create/extend the SKU Resolution Engine schema: `b2b_skumap`, `b2b_dataconflict`, plus the `b2b_homologation` / `b2b_runflat` / `b2b_extraload` / `b2b_canonical_key` columns on `b2b_canonicalproduct`. | MVP2 |
| `create-warehouse-table.py` | Create `b2b_warehouse` (+ region lookup, + `b2b_warehouse` lookup on offers) and add every `b2b_` entity to the `B2BAgg_Core` solution. | Audit P1 (M-4 / H-3) |
| `gen-customizations.py` | Assemble `solutions/B2BAgg.Core/src/Other/Customizations.xml` from the individual `Entity.xml` files. | ALM |

## Data & content

| Script | Purpose | Phase |
|---|---|---|
| `seed-via-az-token.py` | **Canonical seeder.** Idempotent upsert of `data/seed/*.csv` (region → supplier → warehouse → product → offer) into Dev. | MVP1+ |
| `extend-catalog.py` | One-shot idempotent transform that upgrades the canonical catalog for the SKU engine. | MVP2 |
| `gen-training-data.py` | Generate `data/ai-builder/sku-training-data.csv` for the AI Builder Custom Text Classification model. | MVP2 |
| `setup-powerbi.py` | Provision the Power BI workspace + push the dataset. | MVP2 |
| `requirements-seed.txt` | pip deps for the scripts (`requests`, `msal`, `python-dotenv`). | — |

## Conventions

- **Idempotent**: every script is safe to re-run — records are matched by their
  natural key (e.g. `b2b_name`, or `supplier + raw_sku` for offers) before write.
- **Auth**: `az account get-access-token --resource <DataverseURL>` (QUIRK #1).
  No secrets in the repo; `.env.local` is gitignored.
- **Single seeder**: `seed-via-az-token.py` is the only seed path. (The older
  MSAL/client-credentials `seed-dev-data.py` was removed in audit P6 — that auth
  path died when the CI client secret was dropped in P0.)
- **Typical run order**: create-tables → create-order-tables → create-matching-tables
  → create-warehouse-table → `python3 scripts/seed-via-az-token.py`.
