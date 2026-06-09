# CI authentication — GitHub Actions OIDC + Entra federated credentials

The GitHub Actions workflows authenticate to Power Platform and Azure with
**workload-identity federation (OIDC)** — there is **no long-lived client
secret** in the repo or in CI.

## How it works

1. An Entra app registration (`b2bagg-github-actions`) holds **federated
   identity credentials (FIC)**, one per workflow trigger subject.
2. Each workflow requests an OIDC token from GitHub (`permissions: id-token: write`).
3. Power Platform / Azure validate the token against the FIC subject — no secret
   is exchanged.

## Federated credential subjects

Add one FIC per subject your workflows use, for example:

| Subject | Used by |
|---|---|
| `repo:<owner>/<repo>:ref:refs/heads/main` | deploy on push to `main` |
| `repo:<owner>/<repo>:pull_request` | PR validation |
| `repo:<owner>/<repo>:environment:<env>` | environment-gated deploys |

## Non-secret repo/variable configuration

These are **identifiers, not secrets** (still inject via repo/environment
variables rather than hardcoding):

```text
PP_CLIENT_ID   # the b2bagg-github-actions app (client) id
PP_TENANT_ID   # <tenant-id>
PP_DEV_URL     # https://<your-dev-org>.crm.dynamics.com/
PP_TEST_URL    # https://<your-test-org>.crm.dynamics.com/
PP_PROD_URL    # https://<your-prod-org>.crm.dynamics.com/
```

The Entra app is added as an **application user** with a deploy-capable security
role in each target Power Platform environment, and Contributor on the Azure
resource group. See [`.github/workflows/README.md`](../.github/workflows/README.md)
for the per-workflow breakdown.
