# ADR-005: Homologation tokens as a hard canonical key + the SKU memo cache

- **Status**: Accepted
- **Date**: 2026-05-28

## Context

In the tire domain, an OEM **homologation** marker (`*`=BMW, `MO`/`MOE`=Mercedes,
`N0`/`N1`=Porsche, `AO`=Audi, `LR`=Land Rover, `VOL`=Volvo) means the tire was
re-engineered and approved for a specific automaker. Two listings can be 95%
textually identical yet be **different products with a 20–30% price gap**:

```
MICHELIN Latitude Sport 3 245/45R20 103W XL Run on Flat *   ← BMW-approved, premium
MICHELIN Latitude Sport 3 245/45R20 103W XL Run on Flat     ← no approval, cheaper
```

If a matcher treats `*` as noise (as any similarity-based method does by
default), both collapse to one canonical SKU. The seller who *omitted* the `*`
then appears to offer the "same" tire cheaper, corrupting the price comparison
that is the platform's core value. **Run-flat** has the same property: a
non-run-flat casing is a different product at a different price.

Separately, even a correct matcher should not re-run on every sync. The original
system kept a memo base so a once-resolved `(seller, internal SKU)` always
resolves to the same canonical, no matter how the name is spelled next time.

## Decision

### 1. Homologation and run-flat are part of the canonical key

The canonical key composed by `azure/functions/sku_matcher.py` is:

```
brand | model | width | profile | diameter | load | speed | homologation | runflat | xl
```

`b2b_canonicalproduct` carries `b2b_homologation` (local choice),
`b2b_runflat`, `b2b_extraload`, and a stored `b2b_canonical_key`. The seed key
is produced by the **same** `canonical_key()` function the runtime uses
(`scripts/extend-catalog.py` imports it), so a seeded key is byte-identical to
what `normalize-sku` computes — Stage 1 exact match is exact.

In the fuzzy stage (Stage 2), a **mismatch on homologation or run-flat caps the
score below `FLOOR`**, so such a pair can never auto-bind. It is forced to the
AI tie-break / admin queue. Size is a separate **hard gate** (a size mismatch
disqualifies a candidate entirely). `XL` is included in the key (so it
participates in exact match) but treated as soft in fuzzy ranking, as it is a
lower-stakes discriminator.

Verified live in Dev — the homologation family shares everything but the
homologation segment:

```
MICHELIN|LATITUDESPORT3|245|45|20|103|W|None|RF|XL
MICHELIN|LATITUDESPORT3|245|45|20|103|W|Star_BMW|RF|XL
MICHELIN|LATITUDESPORT3|245|45|20|103|W|MO_Mercedes|RF|XL
MICHELIN|LATITUDESPORT3|245|45|20|103|W|N0_Porsche|RF|XL
```

### 2. `b2b_skumap` is the memo cache (Stage 0)

A new table `b2b_skumap` stores `(b2b_supplier, b2b_raw_sku) → b2b_canonical_product`
with `b2b_match_method`, `b2b_confidence`, `b2b_normalized_key`, `b2b_last_seen`,
and an **alternate key on (supplier + raw_sku)** for idempotent upsert. This is
the platform's parity with the original `(manufacturer_sku ; seller_id ;
seller_internal_sku)` base.

- Every confident resolution (ExactKey / Fuzzy / AI / admin Approve) writes a
  `b2b_skumap` row.
- The Normalize SKU flow checks `b2b_skumap` **first**; a hit binds instantly
  with no Function or AI call.
- Result: the system gets cheaper and faster over time, and human approvals are
  never repeated for the same supplier SKU.

## Consequences

- Catalog seeding and the runtime must stay in sync on the key algorithm — they
  share one function by construction, so drift is structurally prevented.
- Homologation must be modelled as a first-class catalog attribute; adding a new
  OEM marker means a new choice option + re-seed (idempotent).
- The alternate-key index on `b2b_skumap` builds asynchronously; the upsert
  pattern degrades gracefully to filter-by-(supplier,raw_sku) until it is ready.
