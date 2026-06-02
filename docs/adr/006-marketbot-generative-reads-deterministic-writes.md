# ADR-006: MarketBot — generative answers for reads, deterministic topic+flow for writes

- **Status**: Accepted
- **Date**: 2026-06-02

## Context

MarketBot (Copilot Studio agent, MVP2 Stage 2) was originally specced as a
**hybrid** with two explicit, deterministic topics — **Price Compare** and
**Create RFQ** — each calling a Power Automate flow, plus a generative
Dataverse-knowledge layer for free-form questions.

Building and testing the **Price Compare** deterministic topic surfaced two
problems that make it the wrong tool for price/lookup queries:

1. **Entity capture is fragile.** The topic used `Ask a question` with
   *Identify: User's entire response* → variable `ProductName`. Users naturally
   repeat context ("compare prices for 225/45"), so `ProductName` captured the
   whole sentence and the flow ran
   `contains(b2b_raw_name, 'compare prices for 225/45')` → zero matches.
2. **`b2b_raw_name` filter defeats cross-supplier comparison.** The same tire is
   written differently by each supplier — `Michelin Pilot Sport 4 225/45R17`
   (Rosshinaopt), `Мишлен Пилот Спорт 4 225/45R17` (TyreCenter, Cyrillic),
   `Michelin PS4 225/45/17` (Koleso). A literal `contains` on the raw name
   matches only one supplier's spelling, so the core value prop — "who is
   cheapest **across** suppliers" — silently fails.

Meanwhile, in the same test, the **generative Dataverse-knowledge layer answered
correctly**: for `cheapest CrossClimate 2` it returned a clean cross-supplier
table (Koleso.ru 103.50, Rosshinaopt 110.00, …), named the cheapest offer, and
**cited the source** (`b2b_supplieroffer`). The LLM normalized the heterogeneous
raw names on its own — exactly the gap the deterministic raw_name filter has.

The two halves also **competed**: a single query produced two contradictory
answers ("No offers found" from the topic + a correct table from the generative
layer), which reads as a bug on a demo/Loom recording.

## Considered options

| Option | Approach | Verdict |
|---|---|---|
| A. Generative for reads, deterministic only for writes | drop/disable Price Compare topic; let knowledge layer answer compare/lookup; keep Create RFQ deterministic | **Accepted** |
| B. Fix the deterministic Price Compare topic | switch filter to canonical product (`b2b_canonical_product/b2b_name`), add entity extraction, suppress generative echo | Rejected — more work, more fragile, duplicates what the generative layer already does well |

## Decision

**Option A.** Split the agent by operation type:

- **Reads / price comparison / inventory lookup → generative answers** over the
  Dataverse knowledge sources. Already working, robust to synonyms/typos/Cyrillic,
  and it cites the underlying rows. The explicit **Price Compare topic is
  disabled** (kept in the agent as an artifact, not triggering).
- **Writes / Create RFQ → deterministic topic + Power Automate flow.** Creating
  Dataverse records needs explicit confirmation and controlled field mapping;
  this is not delegated to free generation. This topic also showcases Power
  Automate orchestration in the demo.

The `MarketBot - Compare Prices` flow is left in place but unreferenced; its fate
(keep as a PA artifact vs. delete) is decided at solution-export cleanup.

## Consequences

- **Pro:** single, clean answer per query; cross-supplier comparison works
  (LLM-normalized); answers carry citations — a strong "Dataverse-grounded
  generative AI" story for the interview. Less brittle than rigid topics.
- **Pro:** clean architectural narrative — *generative for reads, deterministic
  for writes* — which is the senior-level pattern for agent design.
- **Con:** comparison formatting (table layout, "cheapest" call-out, sort order)
  is LLM-driven, so it can vary run-to-run. Mitigated by agent Instructions
  ("prefer a Markdown table … Supplier | Product | Price | Stock | City").
- Power Automate is still demonstrated via Sync, Normalize SKU, and Create RFQ
  flows, so dropping the Price Compare topic costs no PA coverage.
- If a *deterministic* price table is ever required (e.g. for a contract/export),
  the disabled topic + `MarketBot - Compare Prices` flow can be revived and fixed
  per Option B (canonical filter — see the offer→canonical lookup
  `b2b_canonical_product`).
