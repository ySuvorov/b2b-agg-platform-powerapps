# ADR-003: Service Bus tier — Standard (topics) vs Basic (dual queues)

- **Status**: Accepted
- **Date**: 2026-05-28

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

Topics/subscriptions require **Standard tier** (~$10/month flat fee).
Basic tier only supports queues (no pub/sub fan-out).

The Logic App (`la-b2bagg-supplier-ingest-dev`) provides the push-model
counterpart to the pull model (Power Automate scheduled → Azure Function):
an HTTP POST endpoint that external suppliers can call to deliver stock
updates immediately, without polling.

## Considered options

| Option | Architecture | Cost | Demo impact |
|---|---|---|---|
| A. Standard tier + topic + 2 subs | clean fan-out, pub/sub semantics | ~$10/mo | reviewer sees idiomatic SB topic usage |
| B. Basic tier + 2 separate queues | dual publish from Logic App | ~$0.05/M ops | slightly less elegant; no true fan-out |
| C. Event Grid instead of Service Bus | serverless pub/sub | ~$0.60/M events | different skill keyword; overkill for one topic |
| D. Event Hubs | stream processing semantics | ~$11/mo | wrong abstraction — stream vs. message queue |
| E. No Service Bus — Logic App calls both consumers directly | flat | $0 | drops "Service Bus" from resume keyword coverage entirely |

## Decision

**Option A** — Service Bus Standard + topic `stock-updates` + subscriptions
`to-power-automate` and `to-analytics`.

Namespace: `sb-b2bagg-dev`, deployed in `westeurope` inside `rg-b2b-agg-demo`.
Auth rules: `logic-app-send` (Send), `pa-listen` (Listen + Manage).

Option B rejected: no pub/sub semantics; Logic App would need two separate
"Send message" actions, weakening the demo narrative around decoupling.

Option C rejected: Event Grid is a different Azure skill and does not map
to the "Service Bus" keyword in target vacancies.

Option D rejected: Event Hubs is designed for high-throughput stream
ingestion, not transactional message passing with competing consumers.

Option E rejected: Service Bus is a deliberate keyword in the vacancy
and showing it is core to the platform's integration story.

## Consequences

- ~$10/month line item while the namespace is running.
- Cost control: use `az servicebus namespace update --status Disabled` to
  pause the namespace outside active demo windows (no messages lost,
  billing stops for the data plane).
- MVP3: add Dead Letter Queue monitoring view in the MDA for operational
  observability.
- If budget becomes an issue, fall back to Option B; the change is local
  to the Logic App (add a second "Send" action) and the PA flow (subscribe
  to a queue rather than a topic subscription).
