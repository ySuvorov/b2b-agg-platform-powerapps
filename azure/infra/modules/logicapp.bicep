// =============================================================================
// Logic App module — B2BAgg Platform
// HTTP trigger → validate schema → publish to SB topic stock-updates
// =============================================================================

@description('Environment suffix: dev | test | prod')
param environmentName string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

@description('Service Bus connection string with Send rights (from servicebus module output)')
@secure()
param serviceBusConnectionString string

// ---------------------------------------------------------------------------
// Managed API connection for Service Bus
// ---------------------------------------------------------------------------

resource sbApiConnection 'Microsoft.Web/connections@2016-06-01' = {
  name: 'servicebus-b2bagg-${environmentName}'
  location: location
  tags: tags
  properties: {
    displayName: 'SB B2BAgg ${environmentName}'
    api: {
      id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'servicebus')
    }
    parameterValues: {
      connectionString: serviceBusConnectionString
    }
  }
}

// ---------------------------------------------------------------------------
// Logic App workflow
// ---------------------------------------------------------------------------

resource logicApp 'Microsoft.Logic/workflows@2019-05-01' = {
  name: 'la-b2bagg-supplier-ingest-${environmentName}'
  location: location
  tags: tags
  properties: {
    state: 'Enabled'
    definition: {
      '$schema': 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
      contentVersion: '1.0.0.0'
      parameters: {
        '$connections': {
          defaultValue: {}
          type: 'Object'
        }
      }
      triggers: {
        manual: {
          type: 'Request'
          kind: 'Http'
          inputs: {
            schema: {
              type: 'object'
              properties: {
                supplier_id: { type: 'string' }
                schema_version: { type: 'string' }
                items: { type: 'array' }
              }
              required: ['supplier_id', 'items']
            }
          }
        }
      }
      actions: {
        Send_to_topic: {
          type: 'ApiConnection'
          inputs: {
            host: {
              connection: {
                name: '@parameters(\'$connections\')[\'servicebus\'][\'connectionId\']'
              }
            }
            method: 'post'
            body: {
              ContentData: '@{base64(string(triggerBody()))}'
              ContentType: 'application/json'
              Properties: {
                supplier_id: '@{triggerBody()[\'supplier_id\']}'
              }
            }
            path: '/@{encodeURIComponent(encodeURIComponent(\'stock-updates\'))}/messages'
            queries: {
              systemProperties: 'None'
            }
          }
          runAfter: {}
        }
        Response_202: {
          type: 'Response'
          inputs: {
            statusCode: 202
            headers: {
              'Content-Type': 'application/json'
            }
            body: {
              status: 'accepted'
              supplier_id: '@{triggerBody()[\'supplier_id\']}'
              item_count: '@{length(triggerBody()[\'items\'])}'
              enqueued_at: '@{utcNow()}'
            }
          }
          runAfter: {
            Send_to_topic: ['Succeeded']
          }
        }
        Response_error: {
          type: 'Response'
          inputs: {
            statusCode: 500
            body: {
              status: 'error'
              detail: '@{body(\'Send_to_topic\')}'
            }
          }
          runAfter: {
            Send_to_topic: ['Failed', 'TimedOut']
          }
        }
      }
    }
    parameters: {
      '$connections': {
        value: {
          servicebus: {
            connectionId: sbApiConnection.id
            connectionName: sbApiConnection.name
            id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'servicebus')
          }
        }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

output logicAppName string = logicApp.name
output logicAppId string = logicApp.id
