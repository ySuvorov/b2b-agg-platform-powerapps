# Scripts

| Script | Purpose | Phase |
|---|---|---|
| `seed.ts` | Idempotent upsert of `data/*.csv` into Dataverse Dev | MVP1 |
| `ai-builder-training-data.csv` | Labeled raw→canonical pairs for AI Builder training | MVP2 |
| `cost-report.sh` | One-liner az CLI rollup of monthly Azure spend | MVP3 |

## Conventions

- Scripts are idempotent: safe to re-run, no duplicates.
- Reads tenant/env from `.env.local` (gitignored). Never hard-code secrets.
