# SKU Resolution Engine — build runbook & browser handoff

Companion to **ADR-004** (matching strategy) and **ADR-005** (homologation key +
memo cache). This is the operational guide: what is built, what is automated by
script, and the exact browser steps Yuri performs (AI Builder + flow + MDA).

## Status of the parts

| Part | State | Where |
|---|---|---|
| Deterministic matcher (parse + fuzzy) | ✅ built + tested | `azure/functions/sku_matcher.py` |
| `normalize-sku` HTTP route | ✅ built | `azure/functions/function_app.py` |
| Catalog snapshot for standalone use | ✅ generated | `azure/functions/catalog.json` |
| Custom connector OpenAPI | ✅ written | `azure/openapi/normalize-sku.yaml` |
| Homologation columns + twins | ✅ live in Dev | `scripts/create-matching-tables.py`, `scripts/extend-catalog.py` |
| `b2b_skumap`, `b2b_dataconflict` tables | ✅ live in Dev | `scripts/create-matching-tables.py` |
| Trap supplier offers (unbound) | ✅ seeded | `data/seed/supplieroffer.csv` |
| Training data (180 rows) | ✅ generated | `scripts/gen-training-data.py` → `data/ai-builder/sku-training-data.csv` |
| AI Builder Prompt "SKU Matcher" | ⬜ browser (Yuri) | make.powerapps.com → AI Builder → Prompts |
| AI Builder Text Classification | ⬜ browser (Yuri) | make.powerapps.com → AI Builder → Custom models |
| Normalize SKU flow | ⬜ build after Model IDs | Power Automate (solution `B2BAgg.Integration`) |
| Data Conflicts Kanban (MDA) | ⬜ browser (Yuri) | MDA `b2b_B2BAggOperations` |

## Normalize SKU flow — cascade design

Trigger: **When a row is added or modified** → `b2b_supplieroffer`
(run only on offers where `b2b_canonical_product` is empty).

```
1. Stage 0 — Memo cache
     List rows b2b_skumap  filter: _b2b_supplier_value eq @{supplier}
                                   and b2b_raw_sku eq '@{raw_sku}'
     If a row exists:
        Update b2b_supplieroffer → b2b_canonical_product = mapped canonical,
                                    b2b_match_method = Cache, confidence = 1.0
        Terminate (Succeeded)

2. List rows b2b_canonicalproduct  (project to the connector CatalogItem shape)

3. Stage 1+2 — call connector NormalizeSku
     body: { raw_name, raw_sku, catalog: <from step 2> }

4. Switch on body('NormalizeSku')?['decision']:
     case ExactKey / Fuzzy:
        Update offer → canonical = canonical_id, method = decision, confidence
        Upsert b2b_skumap (supplier + raw_sku → canonical, method, confidence, last_seen=utcNow)
     case Ambiguous:
        → Stage 3 (AI tie-break)
     case NewCandidate:
        Create b2b_dataconflict (status = NewCandidate, candidates_json = candidates)

5. Stage 3 — AI tie-break (only reached for Ambiguous)
     5a. AI Builder → Create text with GPT (Prompt "SKU Matcher"):
            inputs: raw_name + top-K candidate names (from candidates[])
            output: canonical_id or "NONE" + confidence
     5b. AI Builder → Predict (Text Classification "SKU Classifier"):
            input: raw_name → predicted label + score
     If 5a id == matched candidate AND 5b agrees AND min(conf) ≥ 0.85:
            Update offer → canonical, method = AI, confidence = min(conf)
            Upsert b2b_skumap
     Else:
            Create b2b_dataconflict (status = Pending, ai_confidence,
                                     candidates_json, suggested_canonical = 5a id)
```

Guardrails (CLAUDE.md "Forbidden"): manual/test runs only — **no** real schedule
trigger (AI Builder credits are limited on the Developer Plan).

## AI Builder Prompt "SKU Matcher" — exact prompt text

Create in make.powerapps.com → **AI Builder → Prompts → Create**. Add two input
variables: `RawName` (text) and `Candidates` (text — a newline list the flow
builds from `candidates[]`). Paste:

```
You are a tire-catalog matching expert. Match a raw supplier product name to ONE
canonical product from the candidate list, or answer NONE.

CRITICAL RULES:
- Homologation / OEM-approval markers make tires DIFFERENT products, never to be
  merged: "*" = BMW, "MO"/"MO1"/"MOE" = Mercedes, "N0"/"N1"/"N2" = Porsche,
  "AO" = Audi, "LR" = Land Rover, "VOL" = Volvo, "MGT" = Maserati.
  A name WITHOUT a marker must NOT match a candidate WITH one (and vice versa).
- Run-flat (RunFlat, Run on Flat, ROF, RFT, SSR, ZP) vs non-run-flat are DIFFERENT.
- Size (width/profile/diameter) and load/speed index must match exactly.
- Ignore brand spelling/case, Cyrillic transliteration (МИШЛЕН = MICHELIN), and
  model spacing ("Pilot Sport 4 S" = "Pilot Sport 4S"), and abbreviations
  ("PS4" = "Pilot Sport 4").

RAW NAME:
{RawName}

CANDIDATES (one per line, "id :: name"):
{Candidates}

Respond with strict JSON only:
{"canonical_id": "<id or NONE>", "confidence": <0..1>, "reason": "<short>"}
```

## AI Builder Text Classification "SKU Classifier"

1. make.powerapps.com → **AI Builder → Custom models → Text classification**.
2. Data source: upload `data/ai-builder/sku-training-data.csv`
   (columns `Text`, `Label`; 180 rows, 36 labels). Regenerate any time with
   `python3 scripts/gen-training-data.py`.
3. Text column = `Text`; Label column = `Label`.
4. Train (background), evaluate, **Publish**.
5. Save the **Model ID** — the flow's "Predict" step needs it.

> Honest framing for the demo: classification is the *secondary* signal. It will
> struggle to separate the `*` / non-`*` twins (that is the whole point of
> ADR-004) — which is exactly why the deterministic engine is primary and the
> Prompt enforces the homologation rule.

## MDA "Data Conflicts" review board (in `b2b_B2BAggOperations`)

> **Decision (Option B):** the native **Kanban control is hard-locked to the
> Opportunity and Activity tables only** (Microsoft docs:
> <https://learn.microsoft.com/dynamics365/sales/add-kanban-control> — *"The
> Kanban control works only on the Opportunity and Activity tables."*). It does
> not appear in *Add Control* for a custom table, and BPF-Kanban is likewise
> Opportunity-only. Rather than take a third-party PCF dependency into the
> solution, we visualise the conflict queue natively with a **grouped view + a
> status chart** — same demo story, zero non-Microsoft components, clean ALM.

Built headless (committed scripts, idempotent, az-token auth):

- **`scripts/create-dataconflict-chart.py`** → system chart **"Conflicts by
  Status"** (`savedqueryvisualization`): count of conflicts grouped by
  `b2b_status`. Verified live: Pending 2 / NeedsReview 1 / NewCandidate 1.
- **`scripts/configure-dataconflict-view.py`** → public view **"Active Data
  Conflicts"** columns = Raw SKU, Raw Supplier Name, Status, AI Confidence,
  Suggested Canonical; sorted by Status then AI Confidence desc (same-status
  rows cluster → reads as a grouped board; the read-only grid also offers a
  runtime *Group by → Status*).

YS browser step (the only one left here): Operations app → **Data Conflicts** →
**Show Chart** → pick **"Conflicts by Status"**. Optionally demo runtime
*Group by Status* on the grid.

- Status column `b2b_status`: Pending / NeedsReview / NewCandidate / Approved /
  Rejected / AutoResolved.
- Main form fields (form polish, optional for demo): Raw Supplier Name, Raw SKU,
  Supplier Offer (lookup), Suggested Canonical (lookup), AI Confidence,
  Candidates (JSON), Status, Reviewed By.
- Approve action (a flow or a model-driven command): set Status = Approved, set
  the offer's `b2b_canonical_product` = Suggested Canonical, and **upsert
  `b2b_skumap`** so the match is learned (Stage 0 next time).
- Reject action: Status = Rejected; optionally create a new `b2b_canonicalproduct`
  from the parsed attributes (NewCandidate path).

## How to hand the Model IDs back to Claude

Once trained/published, just write in the next session, e.g.:

> "SKU Classifier Model ID: xxxx, Prompt 'SKU Matcher' published."

Claude then wires the IDs into the Normalize SKU flow, exports the solutions
(`B2BAgg.AI` for the model/prompt, `B2BAgg.Integration` for the flow + connector),
unpacks into `solutions/`, and opens the PR.

## Local verification (no cloud needed)

```bash
python3 azure/functions/sku_matcher.py          # self-test (5 cases)
python3 - <<'PY'                                 # full-catalog check
import json, sys; sys.path.insert(0, "azure/functions")
import sku_matcher
cat = json.load(open("azure/functions/catalog.json", encoding="utf-8"))
print(sku_matcher.match("MICHELIN Latitude Sport 3 245/45R20 103W XL Run on Flat *", cat).canonical_name)
PY
```
