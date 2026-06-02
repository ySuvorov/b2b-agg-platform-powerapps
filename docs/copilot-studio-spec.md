# MarketBot — Copilot Studio Build Spec (Hybrid)

> **Stage 2 of MVP2.** Claude prepared this spec + the Code App bot panel.
> YS builds the agent in the browser (~2 h). **Hybrid architecture**: generative
> answers over Dataverse for free-form Q&A + **2 explicit topics** (Price Compare,
> Create RFQ) backed by **2 Power Automate flows** for deterministic, demo-critical
> paths.

---

## Why hybrid

| Capability | How | Why |
|---|---|---|
| Product lookup, regional demand, free-form ("most stocked BMW tyre?") | **Generative answers over Dataverse** (no flow) | Shows the modern Copilot Studio AI feature; zero per-intent build |
| **Price comparison** (clean ranked table) | **Explicit topic + flow** | Demo-critical — must return a tidy table on camera, not prose |
| **Create RFQ** (write-back to Dataverse) | **Explicit topic + flow** | Write needs a deterministic action + supplier lookup |

This demonstrates **both** skill sets — generative AI grounding *and* classic
topic/slot/flow engineering — while keeping the recorded demo's critical paths
fully deterministic.

---

## Architecture

```
Code App (React) ──iframe──► Copilot Studio web chat (MarketBot)
                                    │
              ┌─────────────────────┼──────────────────────┐
              ▼                     ▼                      ▼
   Generative answers      Topic: Price Compare     Topic: Create RFQ
   (Dataverse knowledge)   → PA flow (List rows)    → PA flow (create b2b_rfq)
              │                     │                      │
              └─────────────────────┴──────────────────────┘
                                    ▼
                               Dataverse
              (b2b_supplieroffer, b2b_canonicalproduct,
               b2b_supplier, b2b_region, b2b_rfq)
```

---

## Prerequisites

- [ ] Copilot Studio licence (included in Power Platform Developer Plan)
- [ ] Environment: **B2BAgg-Dev**
- [ ] Copilot Studio: https://copilotstudio.microsoft.com
- [ ] Power Automate: https://make.powerautomate.com

---

## Part 1 — Build the 2 Power Automate flows first

Open https://make.powerautomate.com → environment **B2BAgg-Dev** (top-right picker).

> For each: **+ Create → Automated cloud flow** → search trigger
> **"When a copilot calls a flow"** (a.k.a. *Run a flow from Copilot*) → Create.
> After saving, add to solution **B2BAgg_Integration** (flow → ⋯ → Add to solution).

---

### Flow 1 — `MarketBot - Compare Prices`

**Purpose:** all offers for a product, cheapest→expensive, as a structured payload.

1. **Trigger:** "When a copilot calls a flow" → **+ Add an input → Text** → name `product_name`.

2. **List rows** (Dataverse):
   - Table name: **Supplier Offers** (`b2b_supplieroffers`)
   - Filter rows: `contains(b2b_raw_name,'@{triggerBody()?['text']}')`
   - Select columns: `b2b_raw_name,b2b_price,b2b_currency,b2b_stock,b2b_suppliername,b2b_warehouse_city,b2b_lead_time_days`
   - Sort by: `b2b_price asc`
   - Row count: `20`

3. **Select** (Data Operations → Select):
   - From: `value` (List rows output)
   - **Switch to text mode** (the `[T]` / "Edit in advanced mode" toggle) and paste:
     ```json
     {
       "supplier": "@{item()?['b2b_suppliername']}",
       "product": "@{item()?['b2b_raw_name']}",
       "price": "@{item()?['b2b_price']}",
       "currency": "@{item()?['b2b_currency']}",
       "stock": "@{item()?['b2b_stock']}",
       "city": "@{item()?['b2b_warehouse_city']}",
       "lead_days": "@{item()?['b2b_lead_time_days']}"
     }
     ```

4. **Respond to the agent** (last action — search "Respond to the agent" / "Return value(s) to Copilot"):
   - Add output **Text** `comparison_json` = `@{string(body('Select'))}`
   - Add output **Text** `cheapest_supplier` = `@{first(body('Select'))?['supplier']}`
   - Add output **Text** `cheapest_price` = `@{first(body('Select'))?['price']}`
   - Add output **Number** `result_count` = `@{length(body('Select'))}`

**Save** → turn **On** → add to solution `B2BAgg_Integration`.

---

### Flow 2 — `MarketBot - Create RFQ`

**Purpose:** create a `b2b_rfq` row for a named supplier.

> **Verified schema** (`b2b_rfq`): primary name `b2b_rfq_number` is **auto-number**
> (`RFQ-#####`, do NOT set it). Lookup to supplier = `b2b_supplier_id`. Status
> choice `b2b_status`: Draft = **100000000**, Sent = 100000001, Responded = 100000002.
> Notes = `b2b_notes` (memo). Entity set = `b2b_rfqs`.

1. **Trigger:** "When a copilot calls a flow" → add inputs:
   - **Text** `supplier_name`
   - **Text** `product_name`
   - **Number** `quantity`

2. **List rows** — find supplier by name (Dataverse):
   - Table: **Suppliers** (`b2b_suppliers`)
   - Filter rows: `b2b_name eq '@{triggerBody()?['text']}'`  *(uses `supplier_name`)*
   - Row count: `1`

3. **Condition:** `length(body('List_rows')?['value'])` **is greater than** `0`

   **If yes:**
   1. **Add a new row** (Dataverse):
      - Table: **RFQs** (`b2b_rfqs`)
      - `b2b_notes` = `RFQ via MarketBot: @{triggerBody()?['number']} units of @{triggerBody()?['text2']} from @{triggerBody()?['text']}`
      - `b2b_status` = `100000000`  *(Draft)*
      - **Supplier (b2b_supplier_id)** — set the lookup: in the dynamic field
        `b2b_supplier_id` (or "Supplier (Suppliers)") enter
        `@{first(body('List_rows')?['value'])?['b2b_supplierid']}`
        *(if only an `@odata.bind` field is exposed, use*
        `b2b_supplier_id@odata.bind` = `/b2b_suppliers(@{first(body('List_rows')?['value'])?['b2b_supplierid']})`*)*
   2. **Respond to the agent:**
      - **Text** `status` = `Created`
      - **Text** `rfq_id` = `@{outputs('Add_a_new_row')?['body/b2b_rfq_number']}`
      - **Text** `message` = `RFQ @{outputs('Add_a_new_row')?['body/b2b_rfq_number']} created for @{triggerBody()?['number']} units of @{triggerBody()?['text2']} from @{triggerBody()?['text']}`

   **If no:**
   1. **Respond to the agent:**
      - **Text** `status` = `Supplier not found`
      - **Text** `rfq_id` = (empty)
      - **Text** `message` = `Sorry — I couldn't find a supplier named "@{triggerBody()?['text']}".`

**Save** → turn **On** → add to solution `B2BAgg_Integration`.

> Trigger body keys: inputs map to `text`, `text2`, `number` in declaration order.
> So `text` = `supplier_name`, `text2` = `product_name`, `number` = `quantity`.
> Verify in each dynamic-content picker which token corresponds to which input.

---

## Part 2 — Build the agent

### 2.1 Create MarketBot

1. https://copilotstudio.microsoft.com → environment **B2BAgg-Dev**.
2. **Create → New agent** → **Skip to configure** (don't use the describe flow).
3. Name: **MarketBot**
4. Description: *B2B tire market intelligence assistant for procurement buyers.*
5. Instructions:
   ```
   You are MarketBot, a procurement assistant for a B2B tire wholesale platform.
   You help buyers find supplier offers, compare prices across suppliers, check
   regional inventory, and create RFQs (Request for Quotations).
   Answer concisely. When listing offers or prices, prefer a Markdown table with
   columns: Supplier | Product | Price | Stock | City. Prices are in the offer's
   currency (RUB unless stated). Accept Russian region/city names (Moscow,
   Novosibirsk, Ekaterinburg, Kazan, Krasnodar, Saint Petersburg).
   Before creating an RFQ, confirm the product, supplier, and quantity.
   ```
6. **Create**.

---

### 2.2 Add Dataverse as knowledge (the generative half)

1. Open MarketBot → **Knowledge** tab → **+ Add knowledge**.
2. Choose **Dataverse**.
3. Select tables:
   - **Supplier Offers** (`b2b_supplieroffer`)
   - **Canonical Products** (`b2b_canonicalproduct`)
   - **Suppliers** (`b2b_supplier`)
   - **Regions** (`b2b_region`)
4. Add → wait for indexing (status shows "Ready").
5. **Settings → Generative AI** → ensure **mode = Generative** (not Classic) and
   "Use general knowledge" can stay off (we want grounded answers only).

> This makes free-form questions ("which supplier has the most Michelin stock?",
> "what's available in Novosibirsk?") answerable with no per-intent topic.
> ⚠️ Dataverse knowledge is in preview; if a table can't be added in Dev, the two
> explicit topics below still carry the demo — proceed regardless.

---

### 2.3 Topic — Price Compare (explicit, deterministic table)

**Topics → + Add a topic → From blank.** Name: **Price Compare**.

- **Trigger** (Phrases):
  - compare prices for
  - price comparison
  - cheapest
  - best price for
  - which supplier is cheapest for
  - compare suppliers for
  - lowest price for
- **Nodes:**
  1. **Question:** "Which product would you like to compare prices for?" →
     save user response (whole text) to var **`ProductName`**.
  2. **Add a tool → Flow →** `MarketBot - Compare Prices`
     - input `product_name` ← `ProductName`
     - outputs → `ComparisonJson`, `CheapestSupplier`, `CheapestPrice`, `ResultCount`
  3. **Condition:** `ResultCount > 0`
     - **Yes → Message:**
       ```
       Here are the offers for **{ProductName}**, cheapest first:

       {ComparisonJson}

       💡 Cheapest: **{CheapestSupplier}** at **{CheapestPrice}**.
       Want me to raise an RFQ with {CheapestSupplier}?
       ```
       *(Optionally add Quick replies: "Yes, create RFQ" → redirect to Create RFQ topic.)*
     - **No → Message:** `No offers found for "{ProductName}". Try another product name.`

> The flow returns a JSON array; the message prints it. If you want a true Markdown
> table, add a small "Apply to each + compose" before Respond in the flow — optional
> polish, not required for the demo.

---

### 2.4 Topic — Create RFQ (explicit, write-back)

**+ Add a topic → From blank.** Name: **Create RFQ**.

- **Trigger** (Phrases):
  - create RFQ
  - request a quote
  - send an RFQ
  - raise an RFQ
  - I want to order
  - request for quotation
- **Nodes:**
  1. **Question:** "Which product?" → var **`RFQProduct`**.
  2. **Question:** "Which supplier? (e.g. Rosshinaopt, Koleso.ru, TyreCenter SPB)" →
     var **`RFQSupplier`**.
  3. **Question:** "How many units?" → **Number** → var **`RFQQty`**.
  4. **Message (confirm):**
     ```
     Please confirm the RFQ:
     • Product: {RFQProduct}
     • Supplier: {RFQSupplier}
     • Quantity: {RFQQty}
     ```
     **Quick replies:** `Confirm` | `Cancel`
  5. **Condition:** user picked `Confirm`
     - **Yes → Add a tool → Flow →** `MarketBot - Create RFQ`
       - inputs: `supplier_name` ← `RFQSupplier`, `product_name` ← `RFQProduct`, `quantity` ← `RFQQty`
       - outputs → `RFQStatus`, `RFQId`, `RFQMessage`
       - **Message:** `{RFQMessage}`
     - **No → Message:** `Okay, cancelled — no RFQ created.`

---

### 2.5 Publish + get embed URL

1. **Publish** (top-right) → confirm.
2. **Settings → Channels → Custom website** (or **Channels → Embed**).
3. Copy the iframe **`src`** URL — that's `VITE_COPILOT_BOT_URL`. It looks like:
   ```
   https://web.powerva.microsoft.com/environments/<envId>/bots/<botId>/webchat
   ```

---

## Part 3 — Wire into the Code App

1. `apps/buyer-code-app/.env.local`:
   ```
   VITE_COPILOT_BOT_URL=<the embed src URL>
   ```
   *(see `.env.example` for the Power BI vars too)*
2. The `BotPanel` component already renders a floating chat button (bottom-right)
   that opens MarketBot in a drawer once this is set.
3. Rebuild/redeploy: `power-apps push` (or `npm run build` for local preview).

---

## Verification (demo scenario)

1. Code App → click **MarketBot** (bottom-right).
2. Free-form (generative): `"what's available in Novosibirsk?"` → grounded answer.
3. Explicit topic: `"compare prices for Pilot Sport 4"` → ranked offers + cheapest.
4. Explicit topic: `"create an RFQ"` → product/supplier/qty → Confirm →
   `RFQ-00001 created…`.
5. MDA (Operations app) → **RFQs** → the new row is visible. ✅

---

## Estimated YS time: ~2 h

| Task | Time |
|---|---|
| Flow 1 — Compare Prices | ~25 min |
| Flow 2 — Create RFQ | ~30 min |
| Agent + Dataverse knowledge | ~25 min |
| 2 topics | ~25 min |
| Publish + embed + .env.local + redeploy | ~15 min |
| Smoke test (generative + 2 topics + MDA) | ~20 min |
