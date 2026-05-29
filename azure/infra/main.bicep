// =============================================================================
// B2B Aggregation Platform — Azure Infrastructure
// MVP1 stub — not all resources wired yet
//
// Provisions:
//   - Storage account (b2baggstore) with 3 feed containers
//   - App Service Plan (Consumption) + Function App (Python 3.11)
//   - Application Insights + Log Analytics workspace
//   - Key Vault (placeholder — app settings wired as Key Vault references)
//
// Deploy:
//   az deployment group create \
//     --resource-group rg-b2b-agg-demo \
//     --template-file main.bicep \
//     --parameters main.bicepparam
// =============================================================================

targetScope = 'resourceGroup'

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

@description('Short environment tag: dev | test | prod')
@allowed(['dev', 'test', 'prod'])
param environmentName string = 'dev'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Name of the storage account (globally unique, 3-24 lowercase alphanumeric). Default is uniquified from the resource group id.')
@minLength(3)
@maxLength(24)
param storageAccountName string = 'b2bagg${uniqueString(resourceGroup().id)}'

@description('Name of the Function App')
param functionAppName string = 'func-b2bagg-${environmentName}'

@description('Name of the Key Vault')
param keyVaultName string = 'kv-b2bagg-${environmentName}'

@description('Object ID of the AAD principal that should have Key Vault admin access (developer / CI service principal)')
param keyVaultAdminObjectId string = ''

@description('Principal type of keyVaultAdminObjectId (a user object needs "User", a CI service principal needs "ServicePrincipal").')
@allowed(['User', 'Group', 'ServicePrincipal'])
param keyVaultAdminPrincipalType string = 'ServicePrincipal'

// ---------------------------------------------------------------------------
// Variables
// ---------------------------------------------------------------------------

var appServicePlanName = 'asp-b2bagg-${environmentName}'
var appInsightsName    = 'appi-b2bagg-${environmentName}'
var logWorkspaceName   = 'log-b2bagg-${environmentName}'
var tags = {
  project:     'B2BAggPlatform'
  environment: environmentName
  managedBy:   'bicep'
}

// Feed container names — must match the names used in the Python function
var feedContainers = [
  'feed-supplier-en'
  'feed-supplier-ru'
  'feed-supplier-xml'
]

// ---------------------------------------------------------------------------
// Storage account
// ---------------------------------------------------------------------------

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    accessTier: 'Hot'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
}

// Create the three feed containers
resource feedBlobContainers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = [
  for containerName in feedContainers: {
    parent: blobService
    name: containerName
    properties: {
      publicAccess: 'None'
    }
  }
]

// ---------------------------------------------------------------------------
// Log Analytics workspace (required by App Insights v2)
// ---------------------------------------------------------------------------

resource logWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logWorkspaceName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// ---------------------------------------------------------------------------
// Application Insights
// ---------------------------------------------------------------------------

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logWorkspace.id
    RetentionInDays: 30
  }
}

// ---------------------------------------------------------------------------
// App Service Plan — Consumption (Y1) for Functions
// ---------------------------------------------------------------------------

resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: appServicePlanName
  location: location
  tags: tags
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  kind: 'linux'
  properties: {
    reserved: true  // required for Linux Consumption
  }
}

// ---------------------------------------------------------------------------
// Function App
// ---------------------------------------------------------------------------

resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: functionAppName
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'  // used to resolve the Key Vault references below
  }
  properties: {
    serverFarmId: appServicePlan.id
    reserved: true  // required for Linux
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          // Key Vault reference — resolved at runtime via the Function App's
          // managed identity (granted Key Vault Secrets User below). No secret
          // material is inlined into app settings (audit Codex #8 / L-8).
          value: '@Microsoft.KeyVault(SecretUri=${storageConnSecret.properties.secretUri})'
        }
        {
          name: 'AZURE_STORAGE_CONNECTION_STRING'
          value: '@Microsoft.KeyVault(SecretUri=${storageConnSecret.properties.secretUri})'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: '@Microsoft.KeyVault(SecretUri=${appInsightsConnSecret.properties.secretUri})'
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '1'
        }
      ]
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
    }
    httpsOnly: true
  }
}

// ---------------------------------------------------------------------------
// Key Vault — backs the Function App's connection-string settings via
// @Microsoft.KeyVault references (no secrets inlined in app settings).
//
// NOTE: the deployer principal (CI SP / developer) must hold "Key Vault
// Secrets Officer" (or Administrator) on this vault for the secret writes
// below to succeed against an RBAC-enabled vault — grant it via
// keyVaultAdminObjectId, and allow for role-propagation delay on first deploy.
// ---------------------------------------------------------------------------

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true   // use Azure RBAC instead of access policies
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enabledForTemplateDeployment: false
  }
}

// Grant the developer / CI principal Key Vault Administrator role
// (only when keyVaultAdminObjectId is provided)
resource kvAdminRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(keyVaultAdminObjectId)) {
  name: guid(keyVault.id, keyVaultAdminObjectId, 'Key Vault Administrator')
  scope: keyVault
  properties: {
    // Key Vault Administrator built-in role ID
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '00482a5a-887f-4fb3-b363-3b7fe8e74483')
    principalId: keyVaultAdminObjectId
    principalType: keyVaultAdminPrincipalType
  }
}

// Secrets that back the Function App's app settings (see appSettings above).
// listKeys() is used HERE (at deploy time) to populate the vault — never inlined
// into app settings, which only carry @Microsoft.KeyVault references.
resource storageConnSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'storage-connection-string'
  properties: {
    value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=core.windows.net'
  }
  dependsOn: [kvAdminRoleAssignment]  // best-effort: write after the deployer is granted access
}

resource appInsightsConnSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'appinsights-connection-string'
  properties: {
    value: appInsights.properties.ConnectionString
  }
  dependsOn: [kvAdminRoleAssignment]
}

// Let the Function App's managed identity READ the secrets (Key Vault Secrets User).
resource functionKvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, functionApp.id, 'Key Vault Secrets User')
  scope: keyVault
  properties: {
    // Key Vault Secrets User built-in role ID
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Service Bus (MVP2) — push-ingestion from supplier systems
// ---------------------------------------------------------------------------

module serviceBus 'modules/servicebus.bicep' = {
  name: 'serviceBusDeploy'
  params: {
    environmentName: environmentName
    location: location
    tags: tags
  }
}

// ---------------------------------------------------------------------------
// Logic App — HTTP trigger → validate → publish to SB topic stock-updates
// ---------------------------------------------------------------------------

module logicApp 'modules/logicapp.bicep' = {
  name: 'logicAppDeploy'
  params: {
    environmentName: environmentName
    location: location
    tags: tags
    serviceBusConnectionString: serviceBus.outputs.sendConnectionString
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

output storageAccountName string = storageAccount.name
output functionAppName string = functionApp.name
output functionAppHostName string = functionApp.properties.defaultHostName
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output keyVaultUri string = keyVault.properties.vaultUri
output serviceBusNamespaceName string = serviceBus.outputs.namespaceName
output serviceBusListenConnectionString string = serviceBus.outputs.listenConnectionString
output logicAppName string = logicApp.outputs.logicAppName
