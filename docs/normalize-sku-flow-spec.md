# Normalize SKU flow — authoritative build spec

> Companion to `docs/sku-engine-runbook.md` (design) and ADR-004/005 (strategy).
> This is the **click-by-click** spec YS builds in the Power Automate designer.
> Every action and expression is given verbatim. Build once, test in Dev, then
> Claude exports `B2BAgg.Integration` + `B2BAgg.AI` and opens the PR.
>
> **All values below are verified live in B2BAgg-Dev (2026-05-30).**

## Already done headless (no YS action)

| Piece | Detail |
|---|---|
| Custom connector **"B2BAgg Normalize SKU"** | `pac connector create` into `B2BAgg_Integration`; connector id `e37e6b69-945c-f111-a826-00224837db9d`, unique name `new_b2bagg-20normalize-20sku`, operation **NormalizeSku**. ⚠️ pac forced `new_` publisher prefix (as-built deviation). |
| AI Builder prompt **SKU Matcher** | GPT-4.1, JSON output. **Published.** |
| AI Builder model **SKU Classifier** | Model ID `2725b63b-6b48-4fdb-a205-51bb1d94f7f4`. **Published.** |
| Function | `POST https://func-b2bagg-dev.azurewebsites.net/api/normalize-sku` — verified: `*` BMW raw name → `decision=ExactKey, canonical_id=bmw`. |
| Review board | chart "Conflicts by Status" + grouped view (Option B). |

## 0. Create the flow

1. make.powerapps.com → **B2BAgg-Dev** → **Solutions → B2BAgg.Integration** →
   **+ New → Automation → Cloud flow → Automated**.
2. Name **`Normalize SKU`**. Trigger: **Dataverse → When a row is added, modified
   or deleted**. → Create.
3. **Connection setup (the only secret you type in the whole flow).** The first
   time you drop the **NormalizeSku** action (§4), the designer has no connection
   to the custom connector yet, so it pops a "Create connection" dialog. The
   connector calls the Azure Function `POST .../api/normalize-sku`, which is
   locked with an Azure Functions key (authLevel `function`) — without the key
   in the `x-functions-key` header the call returns **401**. The connector
   definition stores *how* the key is sent (header name `x-functions-key`) but
   **not the value**, on purpose, so the secret never lands in the solution.
   That's why it asks here. Fill the dialog:
   - **Connection name** → `NormalizeSku-dev` (your label; "-dev" = it holds the
     **dev** function's key. Test/Prod get their own connection later).
   - **API Key value** → paste the value of `NORMALIZE_SKU_FUNCTION_KEY` from
     `.env.local` (line 21 — copy everything right of the `=`).
   - **Create.**

   It's created **once** and reused by every NormalizeSku action in this flow
   (the dialog won't reappear). This is the **only** place you enter a secret —
   all other actions (Dataverse, AI Builder, HTTP-with-Entra) use standard or
   OIDC/Entra connections, no keys typed.

Guardrail (CLAUDE.md "Forbidden"): **no recurrence/schedule trigger** — test via
manual row edits only (AI Builder credits are limited on the Dev plan).

## 1. Trigger — When a row is added or modified

| Field | Value |
|---|---|
| Change type | **Added or Modified** |
| Table | **Supplier Offers** (`b2b_supplieroffer`) |
| Scope | **Organization** |
| Select columns | `b2b_raw_name,b2b_raw_sku,b2b_supplier,b2b_warehouse,b2b_canonical_product` |
| Filter rows | `b2b_canonical_product eq null` |

> ⚠️ **Trigger filter uses the lookup logical name** (`b2b_canonical_product`),
> NOT the Web-API `_b2b_canonical_product_value` form. The trigger validates
> against the restricted callback-registration model; `_..._value` fails with
> `Could not find a property named '_b2b_canonical_product_value'`. The `_..._value`
> form is still correct in List rows and in `triggerOutputs()` expressions.
> Fallback if rejected: clear the filter, add a Condition
> `empty(coalesce(triggerOutputs()?['body/_b2b_canonical_product_value'],''))` eq
> `true` → else Terminate.

The filter makes the flow fire only on **unbound** offers, and Stage 2/3 sets the
canonical lookup → the offer won't re-trigger. No infinite loop.

## 2. Stage 0 — Memo cache (short-circuit on a known supplier+SKU)

**Dataverse → List rows** `Stage0_Cache`:
- Table **SKU Maps** (`b2b_skumap`), Row count `1`
- Filter rows:
  `_b2b_supplier_value eq @{triggerOutputs()?['body/_b2b_supplier_value']} and b2b_raw_sku eq '@{triggerOutputs()?['body/b2b_raw_sku']}'`

**Condition** `Stage0_Hit`: `length(outputs('Stage0_Cache')?['body/value'])` **>** `0`.

**If yes:**
1. **Dataverse → Update a row** (`b2b_supplieroffer`), Row ID
   `@{triggerOutputs()?['body/b2b_supplierofferid']}`:
   - **Canonical Product** → switch the field to *Enter custom value* and bind:
     `b2b_canonicalproducts(@{first(outputs('Stage0_Cache')?['body/value'])?['_b2b_canonical_product_value']})`
   - **Match Method** (`b2b_match_method`) = **Cache** (`10000`)
   - **Match Confidence** (`b2b_match_confidence`) = `1`
   - **Last Synced** (`b2b_last_synced`) = `@{utcNow()}`
2. **Terminate** → Succeeded.

**If no:** continue.

## 3. Build the catalog (List rows → Select projection)

**Dataverse → List rows** `ListCatalog`:
- Table **Canonical Products** (`b2b_canonicalproducts`), Row count `5000`
- Select columns:
  `b2b_canonicalproductid,b2b_name,b2b_brand,b2b_model,b2b_width,b2b_profile,b2b_diameter,b2b_load_index,b2b_speed_index,b2b_homologation,b2b_runflat,b2b_extraload`

**Data Operation → Select** `ProjectCatalog`:
- From: `@outputs('ListCatalog')?['body/value']`
- Map (switch to **text/`{}` mode**, paste):
```json
{
  "id": "@{item()?['b2b_canonicalproductid']}",
  "name": "@{item()?['b2b_name']}",
  "brand": "@{item()?['b2b_brand']}",
  "model": "@{item()?['b2b_model']}",
  "width": "@item()?['b2b_width']",
  "profile": "@item()?['b2b_profile']",
  "diameter": "@item()?['b2b_diameter']",
  "load_index": "@item()?['b2b_load_index']",
  "speed_index": "@{item()?['b2b_speed_index']}",
  "homologation": "@{if(equals(coalesce(item()?['b2b_homologation@OData.Community.Display.V1.FormattedValue'],'None'),'None'),'',item()?['b2b_homologation@OData.Community.Display.V1.FormattedValue'])}",
  "runflat": "@coalesce(item()?['b2b_runflat'], false)",
  "extraload": "@coalesce(item()?['b2b_extraload'], false)"
}
```

> ⚠️ **Numeric/boolean fields use the `"@expr"` form (single `@`, no braces, in
> quotes), NOT `@{expr}` unquoted.** The designer's Select text-mode validator
> rejects unquoted `@{...}` as "Enter a valid json". The whole-expression
> `"@..."` form is valid JSON *and* Logic Apps strips the quotes at runtime to
> emit a real number/bool. Keep string fields (`name`, `speed_index`,
> `homologation`…) as quoted `@{...}` interpolation.

> **Homologation maps 1:1.** `b2b_homologation` is a Choice whose **labels are
> exactly the engine tokens** (verified): `None`, `Star_BMW`, `MO_Mercedes`,
> `MOE_Mercedes`, `N0_Porsche`, `N1_Porsche`, `AO_Audi`, `LR_LandRover`,
> `VOL_Volvo`, `MGT_Maserati`. So the formatted value feeds the connector's
> string `homologation` directly; `None` → `""` (no marker).

## 4. Stage 1+2 — call the engine

**B2BAgg Normalize SKU → NormalizeSku** `CallEngine`:
- Raw supplier name = `@{triggerOutputs()?['body/b2b_raw_name']}`
- Raw SKU = `@{triggerOutputs()?['body/b2b_raw_sku']}`
- catalog = `@{body('ProjectCatalog')}`

Response fields: `decision`, `method`, `confidence`, `canonical_id`,
`canonical_name`, `candidates[]`, `parsed{}`.

## 5. Switch on decision

**Switch** `OnDecision` = `@{body('CallEngine')?['decision']}`.

### Case **ExactKey** / Case **Fuzzy** → auto-bind
1. **Update a row** (`b2b_supplieroffer`, trigger row id):
   - Canonical Product (custom value) =
     `b2b_canonicalproducts(@{body('CallEngine')?['canonical_id']})`
   - Match Method = **ExactKey** (`10001`) / **Fuzzy** (`10002`)
   - Match Confidence = `@{body('CallEngine')?['confidence']}`
   - Last Synced = `@{utcNow()}`
2. **LearnMapping** upsert → §6 (method ExactKey/Fuzzy).

### Case **NewCandidate** → admin queue
**Add a row** (`b2b_dataconflict`):
- Name (`b2b_name`) = `@{substring(concat('Conflict: ', triggerOutputs()?['body/b2b_raw_name']), 0, min(100, length(concat('Conflict: ', triggerOutputs()?['body/b2b_raw_name']))))}`
- Raw Supplier Name = `@{triggerOutputs()?['body/b2b_raw_name']}`
- Raw SKU = `@{triggerOutputs()?['body/b2b_raw_sku']}`
- Status (`b2b_status`) = **NewCandidate** (`10002`)
- Candidates JSON (`b2b_candidates_json`) = `@{string(body('CallEngine')?['candidates'])}`
- Supplier Offer (`b2b_supplier_offer`, custom value) =
  `b2b_supplieroffers(@{triggerOutputs()?['body/b2b_supplierofferid']})`

### Default = **Ambiguous** → Stage 3 (§7)

## 6. LearnMapping — upsert into b2b_skumap (shared)

Alt key `b2b_skumap_supplier_rawsku` = (`b2b_supplier`, `b2b_raw_sku`), **Active**.
"Update a row" can't target a composite alt key, so use the **HTTP with
Microsoft Entra ID** connection (the same one P5 used for the offer upsert) —
idempotent PATCH:

```
PATCH https://YOUR-DATAVERSE-ORG.crm.dynamics.com/api/data/v9.2/b2b_skumaps(_b2b_supplier_value=@{triggerOutputs()?['body/_b2b_supplier_value']},b2b_raw_sku='@{triggerOutputs()?['body/b2b_raw_sku']}')
Headers:
  Content-Type: application/json
  # NO If-Match / If-None-Match header → true upsert (create-or-update).
  # If-Match:* means UPDATE-ONLY → 404 0x80060891 when the row doesn't exist yet.
Body:
{
  "b2b_name": "@{triggerOutputs()?['body/b2b_raw_sku']}",
  "b2b_match_method": <10001 ExactKey | 10002 Fuzzy | 10003 AI>,
  "b2b_confidence": @{body('CallEngine')?['confidence']},
  "b2b_canonical_product@odata.bind": "/b2b_canonicalproducts(<canonical_id used above>)"
}
```

> ✅ CONFIRMED (as-built): lookup key segment **must** be `_b2b_supplier_value=`,
> not `b2b_supplier=` — the latter returns `400 0x80060888 The key in the request
> URI is not valid`. Same `_value` rule as P5 offer upsert.
>
> ⚠️ **Body source differs per branch — do NOT copy the body verbatim into the
> AI branch.** ExactKey/Fuzzy: canonical_id + confidence from `CallEngine`. **AI
> branch (Stage 3): from `ParsePrompt`** — at `decision=Ambiguous` the engine's
> top-level `canonical_id` is empty, so `body('CallEngine')?['canonical_id']`
> yields `/b2b_canonicalproducts()` → `400 The supplied reference link … is
> invalid`. Use `body('ParsePrompt')?['canonical_id']` and `…['confidence']`,
> method `10003`.
> P5 as-built note: the alt-key URL with a lookup segment may need the `_value`
> form — copy the exact working pattern from `docs/p5-sync-flow-spec.md`
> §As-built if the `b2b_supplier=` form 404s. `b2b_skumap.b2b_canonical_product`
> lookup **already exists** (verified), so Stage 0 will bind canonicals from
> cache on the next pass.

## 7. Stage 3 — AI tie-break (Ambiguous only, Switch Default)

1. Newline `id :: name` list the prompt expects. ⚠️ `select()` is **not** a valid
   inline WDL function (only the Select *action* exists) — so build it in two steps:
   1a. **Data Operation → Select** `CandidateLines`:
       - From: `take(body('CallEngine')?['candidates'], 5)`
       - Map (key/value GUI, **leave key EMPTY** → scalar array; text mode trips
         "Enter a valid json"): value = `@{concat(item()?['canonical_id'], ' :: ', item()?['canonical_name'])}`
   1b. **Compose** `TopCandidates`: `@{join(body('CandidateLines'), decodeUriComponent('%0A'))}`

2. **AI Builder → Run a prompt** (prompt **SKU Matcher**):
   - `RawName` = `@{triggerOutputs()?['body/b2b_raw_name']}`
   - `Candidates` = `@{outputs('TopCandidates')}`
     ⚠️ Name inside `outputs('…')` must match the Compose action's name exactly
     (spaces → `_`). `TopCandidates` → `outputs('TopCandidates')`. Mismatch =
     `InvalidTemplate … not defined in the template`. Safest: insert via dynamic
     content (Compose → Outputs).

3. **Parse JSON** `ParsePrompt` on the prompt's text output, schema:
   ```json
   {"type":"object","properties":{"canonical_id":{"type":"string"},"confidence":{"type":"number"},"reason":{"type":"string"}}}
   ```

4. **AI Builder → Predict** (model **SKU Classifier**,
   `2725b63b-6b48-4fdb-a205-51bb1d94f7f4`): Text =
   `@{triggerOutputs()?['body/b2b_raw_name']}`. (Secondary signal — see ADR-004.)

5. **Condition** `AIConfident`:
   - `body('ParsePrompt')?['canonical_id']` **≠** `NONE`
   - **AND** `body('ParsePrompt')?['confidence']` **≥** `0.85`

   **If yes:** Update offer (Canonical = prompt's `canonical_id`, Match Method =
   **AI** `10003`, Match Confidence = `@{body('ParsePrompt')?['confidence']}`,
   Last Synced = `utcNow()`) + LearnMapping upsert (§6, method AI).

   **If no:** Add `b2b_dataconflict`:
   - Status = **Pending** (`10000`)
   - AI Confidence (`b2b_ai_confidence`) = `@{body('ParsePrompt')?['confidence']}`
   - Suggested Canonical (`b2b_suggested_canonical`, custom value) =
     `b2b_canonicalproducts(@{body('ParsePrompt')?['canonical_id']})`  *(only if ≠ NONE)*
   - Candidates JSON = `@{string(body('CallEngine')?['candidates'])}`
   - Raw Supplier Name / Raw SKU / Supplier Offer as in §5 NewCandidate.

## 8. Verified reference values (B2BAgg-Dev, 2026-05-30)

**Match method** (same choice on `b2b_supplieroffer` + `b2b_skumap`):
`Cache=10000, ExactKey=10001, Fuzzy=10002, AI=10003, Manual=10004`.

> ⚠️ **Choice fields take the raw integer when typed.** If the Match Method
> dropdown doesn't populate, switch to custom value and type **only the number**
> (`10000`) — *not* `Cache (10000)`. A label-as-text chip trips
> "Enter a valid integer".

**b2b_dataconflict status**:
`Pending=10000, NeedsReview=10001, NewCandidate=10002, Approved=10003, Rejected=10004, AutoResolved=10005`.

**b2b_supplieroffer** match cols: `b2b_match_method` (Choice),
`b2b_match_confidence` (Double), `b2b_canonical_product` (Lookup→canonicalproduct),
`b2b_supplier`/`b2b_warehouse` (Lookup). Alt key `b2b_offer_supplier_wh_sku` =
(supplier, warehouse, raw_sku), Active.

**b2b_skumap**: `b2b_raw_sku` (String), `b2b_supplier` (Lookup), `b2b_match_method`
(Choice), `b2b_confidence` (Double), `b2b_canonical_product` (Lookup→canonicalproduct),
primary `b2b_name`. Alt key `b2b_skumap_supplier_rawsku` = (supplier, raw_sku), Active.

**b2b_dataconflict**: lookups `b2b_supplier_offer`→supplieroffer,
`b2b_suggested_canonical`→canonicalproduct; `b2b_candidates_json` (String),
`b2b_ai_confidence` (Double), `b2b_reviewed_by` (String).

**b2b_homologation** choice = engine tokens (None=10000, Star_BMW=10001,
MO_Mercedes=10002, MOE_Mercedes=10003, N0_Porsche=10004, N1_Porsche=10005,
AO_Audi=10006, LR_LandRover=10007, VOL_Volvo=10008, MGT_Maserati=10009).

## 9. Test (manual, in Dev)

Edit any field of an **unbound trap offer** (one of the 8 seeded without a
canonical) to fire the trigger. Expected:
- clean offer → `ExactKey`/`Fuzzy` → canonical bound, skumap row written;
- `*` vs non-`*` twin → `Ambiguous` → AI tie-break → bound as AI if confident,
  else a **Pending** card on the Data Conflicts board;
- off-catalogue brand → `NewCandidate` card.

Confirm no re-fire (trigger filter stops the second pass). Then tell Claude.

## 10. What Claude does after the test passes

Export `B2BAgg.Integration` (flow + connector + connection refs) and `B2BAgg.AI`
(prompt + model), `pac solution unpack` into `solutions/`, scrub any inline
secret, update PROGRESS.md, open the PR `feat/mvp2-sku-engine → main`.

## 11. As-built deviations (fill in while building)

- [ ] Connector unique name is `new_*` (pac default publisher), not `b2b_*`.
- [ ] Record any action/expression you had to change here.
