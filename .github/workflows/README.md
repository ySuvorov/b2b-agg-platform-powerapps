# GitHub Actions workflows

| Workflow | Trigger | Purpose | Phase |
|---|---|---|---|
| `pr-validation.yml` | PR opened/updated | `pac solution check`, lint Code App, Bicep what-if | MVP1/MVP2 |
| `export-solutions.yml` | Manual / nightly cron | Export from Dev → unpack → commit changes | MVP2 |
| `deploy-test.yml` | Manual dispatch | Pack solution → import into Test | MVP2 |
| `deploy-prod.yml` | Release tag `v*` | Pack managed → import into Prod | MVP3 |

## Authentication

Service Principal (Entra app) + GitHub OIDC federated credentials. No
long-lived client secret in `secrets`. Required permissions: System
Administrator role on each Power Platform environment, Contributor on the
Azure resource group.

Secrets used:
- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `POWER_PLATFORM_*_URL` (one per env)
