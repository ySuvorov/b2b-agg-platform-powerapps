// main.bicepparam — Parameter overrides for B2BAgg Azure infra
// Use a .bicepparam.local file (gitignored) to supply real secrets/IDs locally.
// In CI/CD these values come from GitHub Actions secrets or az deployment ... --parameters.

using './main.bicep'

// Target environment: dev | test | prod
param environmentName = 'dev'

// westeurope — where the resource group rg-b2b-agg-demo lives
param location = 'westeurope'

// Storage account name must be globally unique; lowercase alphanumeric only
param storageAccountName = 'b2baggstore'

// Function App name (will be suffixed with environmentName in the template)
param functionAppName = 'func-b2bagg-dev'

// Key Vault name (will be suffixed with environmentName in the template)
param keyVaultName = 'kv-b2bagg-dev'

// Object ID of the AAD service principal or developer user that needs KV access.
// Leave empty to skip the role assignment (safe for first deploy before SP is created).
// In CI: set via GitHub Actions secret KV_ADMIN_OBJECT_ID
param keyVaultAdminObjectId = ''
