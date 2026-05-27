# Demo / seed data

CSVs and JSON used to seed Dev (and to drive mock supplier feeds).

| File | Purpose |
|---|---|
| `regions.csv` | 8 federal districts with climate zones |
| `suppliers.csv` | 5 suppliers, mixed tiers and regions |
| `canonical_products.csv` | ~100 tires across major brands |
| `supplier_offers.csv` | ~1000 offers across suppliers/products |
| `feeds/feed_supplier_a.json` | Mock supplier A feed (EN schema) |
| `feeds/feed_supplier_b.json` | Mock supplier B feed (RU schema) |
| `feeds/feed_supplier_c.json` | Mock supplier C feed (pseudo-XML in JSON) |

> Files appear progressively as MVP1 and MVP2 are built. The seed script
> (`scripts/seed.ts`) reads from this folder.
