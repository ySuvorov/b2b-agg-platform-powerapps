# Architecture Decision Records

This folder holds short ADRs (Architecture Decision Records). One ADR per
non-trivial choice. Template at the top of `001-pac-cli-on-net9.md`.

| # | Title | Status |
|---|---|---|
| 001 | [Pin pac CLI to 1.52.1 on .NET 9 (macOS)](001-pac-cli-on-net9.md) | Accepted |
| 002 | [Use Azure Pay-As-You-Go, not Free Account](002-azure-payg-vs-free.md) | Accepted |
| 003 | [Service Bus tier — Standard vs Basic](003-service-bus-tier.md) | Proposed |

## When to write a new ADR

- Choosing one of N legitimate technologies for a slot
- Reversing a previous decision
- Documenting a non-obvious workaround that future-you might want to undo

## When NOT to write one

- Trivial syntax preferences
- "Did the obvious thing the docs suggested"
- Implementation detail of a single component
