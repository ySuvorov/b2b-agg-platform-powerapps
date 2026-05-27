# ADR-002: Use Azure Pay-As-You-Go, not Free Account

- **Status**: Accepted
- **Date**: 2026-05-27

## Context

Demo needs Azure-side components: Functions, Logic Apps, Service Bus,
Blob Storage, App Insights. The plan assumed an Azure Free Account ($200
credit + 12 months free + always-free tier). Microsoft sign-up flow rejected
the account ("You're not eligible") despite valid card and account standing.

## Considered options

| Option | Pros | Cons |
|---|---|---|
| A. Retry with a different card/region | maybe gets the $200 credit | uncertain, blocks Day 0 |
| B. Sign up for Pay-As-You-Go | unblocks now; no commitment | no $200 credit; small real cost |
| C. Use Visual Studio Dev Essentials credit | $50/month if eligible | requires VS subscription |
| D. Skip Azure components, do Power-Platform-only | simplest | drops a stated portfolio goal (Azure integrations) |

## Decision

Choose **Option B** — Pay-As-You-Go.

## Cost projection (4-week demo)

Free tiers still apply on PAYG. Estimate:

| Resource | Pricing | Demo usage | Cost |
|---|---|---|---|
| Functions Consumption | 1M req/mo FREE always | <10k req | $0 |
| Logic Apps Consumption | 4000 actions/mo FREE | <2000 actions | $0 |
| Service Bus **Standard** | $10/mo + $0.05/M ops | 1 month | ~$10 |
| Blob Storage LRS Hot | 5GB FREE 12 mo | <1GB | $0 |
| App Insights | 5GB ingestion FREE | <1GB | $0 |
| **Estimated total** | | | **$5–15** |

Acceptable for a portfolio investment.

## Consequences

- Azure namespaces should be **stopped** when not actively demoing
  (Service Bus alone is ~$0.30/day idle).
- We will revisit Service Bus tier in ADR-003: pay $10/mo for `Standard`
  (topics) vs use `Basic` with dual queues.
- No $200 credit means we can't burn through compute experimentation; stick
  to the planned architecture and verify each step works before next.
