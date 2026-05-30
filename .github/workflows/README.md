# GitHub Actions workflows

| Workflow | Trigger | Purpose |
|---|---|---|
| `pr-validation.yml` | PR → `main` | Pack solution + **Solution Checker**; lint & build the Code App; `py_compile` scripts; compile the Azure Function (`function_app.py` + `sku_matcher.py`); run the SKU-matcher pytest suite; post a PR summary comment. A real gate (no `continue-on-error`). |
| `deploy-dev.yml` | `workflow_dispatch` + push to `main` on `solutions/**` | Pack from `solutions/B2BAgg.Core/src` → import (unmanaged) into **Dev**. |
| `deploy-test.yml` | `workflow_dispatch` | Pack → import into **Test**. |
| `deploy-prod.yml` | `workflow_dispatch` | Pack **managed** → import into **Prod**. Manual run is the approval gate (the Developer Plan can't set environment required-reviewers). |
| `export-solution.yml` | `workflow_dispatch` (inputs: source env, managed?) | `pac solution export` from Dev/Test → unpack → **open a PR from a bot branch** (never pushes straight to `main`). |

> Note: there is no Bicep what-if step in PR validation today. Azure infra is
> built/validated with `az bicep build` locally; wiring `what-if` into CI is a
> roadmap item.

## Authentication

**GitHub Actions OIDC + Entra federated credentials — no long-lived client
secret.** Every workflow sets `permissions: id-token: write` and authenticates
via `microsoft/powerplatform-actions` (`actions-install` + `who-am-i`) using the
app id + tenant id. See [`docs/ci-secrets-todo.md`](../../docs/ci-secrets-todo.md)
for the federated-credential subjects and the (non-secret) repo variables.

Required access: the `b2bagg-github-actions` app is an Application User with a
deploy-capable role in each target Power Platform environment, and Contributor
on the Azure resource group.
