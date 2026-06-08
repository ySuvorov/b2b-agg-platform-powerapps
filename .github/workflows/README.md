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

## Solution coverage

GitHub Actions pack/check/deploy/export currently gate **`B2BAgg.Core`** only.
`B2BAgg.AI` and `B2BAgg.Integration` are promoted through **Power Platform
Pipelines** (Dev → Test), which is the source-of-truth ALM path for those two
modules. Expanding GitHub Actions to a `Core → AI → Integration` matrix is a
roadmap item; the trade-off is that Solution Checker emits known, non-blocking
warnings for those component types (see below).

> **Known `pac solution pack` warnings (non-blocking):** packing `B2BAgg.AI`
> warns that `AIModel` root components are not defined in customizations, and
> `B2BAgg.Integration` warns that `ECConnector` (custom connector) root
> components are not defined in customizations. `pac` still exits `0` and the
> output zips include `AIConfiguration/` and `Connector/` files. These warnings
> are expected for AI Builder models and custom connectors exported as solution
> source; the managed imports were verified end-to-end via PP Pipelines in
> Stage 5. They are documented here so a future CI matrix does not treat them as
> failures.

## Authentication

**GitHub Actions OIDC + Entra federated credentials — no long-lived client
secret.** Every workflow sets `permissions: id-token: write` and authenticates
via `microsoft/powerplatform-actions` (`actions-install` + `who-am-i`) using the
app id + tenant id. See [`docs/ci-secrets-todo.md`](../../docs/ci-secrets-todo.md)
for the federated-credential subjects and the (non-secret) repo variables.

Required access: the `b2bagg-github-actions` app is an Application User with a
deploy-capable role in each target Power Platform environment, and Contributor
on the Azure resource group.
