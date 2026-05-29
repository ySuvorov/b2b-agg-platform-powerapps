// =============================================================================
// Service Bus module — B2BAgg Platform
// Standard tier namespace + topic stock-updates + 2 subscriptions
// =============================================================================

@description('Environment suffix: dev | test | prod')
param environmentName string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

// ---------------------------------------------------------------------------
// Namespace
// ---------------------------------------------------------------------------

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: 'sb-b2bagg-${environmentName}'
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
}

// ---------------------------------------------------------------------------
// Topic
// ---------------------------------------------------------------------------

resource topic 'Microsoft.ServiceBus/namespaces/topics@2022-10-01-preview' = {
  parent: serviceBusNamespace
  name: 'stock-updates'
  properties: {
    defaultMessageTimeToLive: 'P1D'
    maxSizeInMegabytes: 1024
    requiresDuplicateDetection: false
  }
}

// ---------------------------------------------------------------------------
// Subscriptions
// ---------------------------------------------------------------------------

resource subPowerAutomate 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2022-10-01-preview' = {
  parent: topic
  name: 'to-power-automate'
  properties: {
    lockDuration: 'PT1M'
    maxDeliveryCount: 10
    deadLetteringOnMessageExpiration: true
  }
}

resource subAnalytics 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2022-10-01-preview' = {
  parent: topic
  name: 'to-analytics'
  properties: {
    lockDuration: 'PT1M'
    maxDeliveryCount: 10
    deadLetteringOnMessageExpiration: true
  }
}

// ---------------------------------------------------------------------------
// Auth rules
// ---------------------------------------------------------------------------

resource sendRule 'Microsoft.ServiceBus/namespaces/authorizationRules@2022-10-01-preview' = {
  parent: serviceBusNamespace
  name: 'logic-app-send'
  properties: {
    rights: ['Send']
  }
}

resource listenRule 'Microsoft.ServiceBus/namespaces/authorizationRules@2022-10-01-preview' = {
  parent: serviceBusNamespace
  name: 'pa-listen'
  properties: {
    rights: ['Listen', 'Send']
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

output namespaceName string = serviceBusNamespace.name
output namespaceId string = serviceBusNamespace.id
output sendConnectionString string = listKeys(sendRule.id, '2022-10-01-preview').primaryConnectionString
output listenConnectionString string = listKeys(listenRule.id, '2022-10-01-preview').primaryConnectionString
