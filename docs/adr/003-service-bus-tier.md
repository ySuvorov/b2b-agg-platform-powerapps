# ADR-003: Service Bus tier — Standard (topics) vs Basic (dual queues)

- **Status**: Proposed (decide at start of MVP2)
- **Date**: 2026-05-27

## Context

The architecture uses Azure Service Bus to decouple supplier feed ingestion
(Logic App publisher) from downstream consumers (Power Automate normalization
flow + analytics ingestion). The cleanest pattern is a **topic** with two
subscriptions:

```
Logic App ──→ Topic stock-updates
              ├── Subscription to-power-automate
              └── Subscription to-analytics
```

Topics require **Standard tier** (~$10/month flat fee). On Pay-As-You-Go this
is real money, even if small.

## Considered options

| Option | Architecture | Cost | Demo impact |
|---|---|---|---|
| A. Standard tier + topic + 2 subs | clean fan-out | ~$10/mo | reviewer sees idiomatic SB topic |
| B. Basic tier + 2 separate queues | dual publish from Logic App | ~$0.05/M ops | slightly less elegant; talking-point trade-off |
| C. No Service Bus — Logic App calls both consumers directly | flattest | $0 | drops "Service Bus" from the resume keyword coverage |

## Decision

Proposed: **Option A** (Standard + topic) for the live demo window, and we
**stop the namespace** outside demo windows to avoid idle charges. If the
budget conversation becomes uncomfortable, fall back to **Option B** and
document the change as a follow-up note in this ADR.

Option C is rejected — Service Bus is a deliberate keyword in the vacancy and
showing it is part of the demo's value.

Decision will be finalized when we provision the Azure resource group at the
start of MVP2 (before then it doesn't matter).

## Consequences

- ~$10 line item on the demo monthly cost.
- We'll demonstrate `az servicebus namespace start/stop` (or terraform/Bicep
  equivalent) as part of the cost-control story in the deck.
- If we later switch to Basic + dual queues, the change is local to the Logic
  App workflow (one extra "Send message" action) and the PA flow (subscribes
  to a queue instead of a subscription) — no schema impact.
