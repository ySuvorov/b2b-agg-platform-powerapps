# ADR-004: SKU matching strategy — deterministic-first hybrid over pure classification

- **Status**: Accepted
- **Date**: 2026-05-28

## Context

Supplier offers arrive as free-text names with the supplier's own internal SKU
and no shared product identifier, e.g.:

```
Michelin PRIMACY ALL SEASON 285/40 R23 115Y XL LR
МИШЛЕН Pilot Sport 4 S 245/35 R20 95Y
MICH PS4 225/45R17 91Y
```

The platform must resolve each to a **canonical product** so that cross-supplier
price comparison is correct. The original real-world system (a 50k-SKU tire
catalog) did **not** use a single classifier. It used a memo base
`(manufacturer_sku ; seller_id ; seller_internal_sku) → canonical`, a matcher
that auto-bound only on a strong unambiguous match, and an admin queue for
low-confidence matches, collisions, and brand-new products.

The MVP2 plan originally proposed a single **AI Builder Custom Text
Classification** model (raw name → canonical class). On closer analysis this is
the wrong primary tool for the domain.

## Considered options

| Option | Approach | Verdict |
|---|---|---|
| A. Pure AI Builder Text Classification | one class per canonical SKU | **Rejected as primary** |
| B. Pure fuzzy match (rapidfuzz only) | string similarity threshold | Rejected — collapses homologation twins |
| C. Pure LLM / AI Builder Prompt | ask a GPT model every time | Rejected as primary — cost, latency, non-determinism, credits |
| D. Deterministic-first hybrid + AI tie-break | parse→key→fuzzy, AI only for residue | **Accepted** |

### Why Text Classification fails as the primary matcher

1. **Scale.** One class per canonical SKU means ~50k classes in production.
   AI Builder classification is not designed for that cardinality; even at demo
   scale it does not represent the real problem.
2. **Homologation blindness.** A classifier learns surface similarity, so
   `…Run on Flat *` (BMW) and `…Run on Flat` (no approval) — 95% identical text,
   20–30% price gap — collapse into one class. That makes the seller who
   *dropped* the `*` look artificially cheapest. See **ADR-005**.
3. **No clean "new product".** Classification always returns a class; it cannot
   cleanly say "this SKU is not in the catalog yet."

## Decision

**Option D — a 4-stage resolution cascade**, cheapest/most-certain first:

```
Stage 0  Memo cache   b2b_skumap lookup by (supplier, raw_sku)        → instant
Stage 1  Exact key    deterministic parse → b2b_canonical_key match    → conf 1.0
Stage 2  Fuzzy rank   rapidfuzz, size hard-gate, homologation cap      → auto / ambiguous
Stage 3  AI tie-break (only for the ambiguous residue)
            3a AI Builder Custom Prompt (GPT): pick canonical or NONE
            3b AI Builder Text Classification: second-opinion / agreement check
Stage 4  Human queue  b2b_dataconflict (MDA Kanban); Approve writes back to b2b_skumap
```

The deterministic engine lives in the Azure Function `normalize-sku`
(`azure/functions/sku_matcher.py`), is framework-free and unit-tested, and is
exposed to Power Automate via a custom connector (`azure/openapi/normalize-sku.yaml`).

**Both** AI Builder flavors are kept (the "layered" choice): the modern
generative **Prompt** handles linguistic noise the dictionaries miss
(`МИШЛЕН`, `Pilot Sport 4 S` == `4S`, abbreviations like `PS4`), and the
**Text Classification** model provides an independent agreement signal. This
maximizes demonstrated Microsoft surface (Azure Functions + two AI Builder
modes + Power Automate + Dataverse + MDA + Power BI) while the deterministic
core keeps the system reliable, explainable, and cheap.

### Why deterministic-first is the senior-level answer

- Exact on the price-defining discriminators (size, homologation, run-flat).
- Explainable: every auto-bind has a canonical key, not a black-box score.
- Cheap: AI Builder credits (limited on the Developer Plan) are spent only on
  the genuinely ambiguous tail, run on-demand, never on a schedule.
- The admin loop **learns**: each approval writes a `b2b_skumap` row, so the
  same raw SKU resolves instantly at Stage 0 forever after.

## Consequences

- New Azure Function module + custom connector to maintain.
- `b2b_canonicalproduct` gains homologation columns and a computed
  `b2b_canonical_key` (seeded by the same code the Function runs — see
  `scripts/extend-catalog.py`).
- Decision thresholds (`AUTO=0.92`, `MARGIN=0.08`, `FLOOR=0.70`) are tunable;
  in production they would move to Power Platform environment variables.
- The catalog passed to the Function must carry the homologation/run-flat
  attributes, or Stage 1/2 cannot discriminate twins.
