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

@description('Name of the storage account (globally unique, 3-24 lowercase alphanumeric)')
@minLength(3)
@maxLength(24)
param storageAccountName string = 'b2baggstore'

@description('Name of the Function App')
param functionAppName string = 'func-b2bagg-${environmentName}'

@description('Name of the Key Vault')
param keyVaultName string = 'kv-b2bagg-${environmentName}'

@description('Object ID of the AAD principal that should have Key Vault admin access (developer / CI service principal)')
param keyVaultAdminObjectId string = ''

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
  properties: {
    serverFarmId: appServicePlan.id
    reserved: true  // required for Linux
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          // TODO MVP1: use Key Vault reference — @Microsoft.KeyVault(SecretUri=...)
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=core.windows.net'
        }
        {
          name: 'AZURE_STORAGE_CONNECTION_STRING'
          // TODO: replace with Key Vault reference once KV is wired
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=core.windows.net'
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
          value: appInsights.properties.ConnectionString
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
// Key Vault (placeholder — secrets not yet stored here in MVP1)
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
    principalType: 'ServicePrincipal'
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
