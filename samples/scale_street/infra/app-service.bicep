targetScope = 'resourceGroup'

@description('Azure region for the App Service fallback.')
param location string = resourceGroup().location

@description('Name of the Linux App Service plan.')
param appServicePlanName string = 'scalestreet-plan'

@description('Globally unique name of the Scale Street web app.')
param webAppName string

@description('Name of the existing Azure Container Registry.')
param acrName string

@description('Name of the existing user-assigned managed identity.')
param workloadIdentityName string = 'scalestreet-workload'

@description('Name of the existing Application Insights component.')
param applicationInsightsName string = 'scalestreet-appi'

@description('Microsoft Foundry project endpoint.')
param foundryProjectEndpoint string

var acrPullRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7f951dda-4ed3-4680-a7ca-43fe172d538d'
)

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2025-11-01' existing = {
  name: acrName
}

resource workloadIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' existing = {
  name: workloadIdentityName
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: applicationInsightsName
}

resource containerRegistryPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, workloadIdentity.id, acrPullRoleDefinitionId)
  scope: containerRegistry
  properties: {
    principalId: workloadIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleDefinitionId
  }
}

resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: appServicePlanName
  location: location
  kind: 'linux'
  sku: {
    name: 'B1'
    tier: 'Basic'
    size: 'B1'
    capacity: 1
  }
  properties: {
    reserved: true
  }
}

resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  name: webAppName
  location: location
  kind: 'app,linux,container'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${workloadIdentity.id}': {}
    }
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    publicNetworkAccess: 'Enabled'
    siteConfig: {
      alwaysOn: true
      acrUseManagedIdentityCreds: true
      acrUserManagedIdentityID: workloadIdentity.properties.clientId
      healthCheckPath: '/health'
      linuxFxVersion: 'DOCKER|${containerRegistry.properties.loginServer}/scale-street:latest'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: [
        {
          name: 'WEBSITES_PORT'
          value: '8000'
        }
        {
          name: 'AZURE_CLIENT_ID'
          value: workloadIdentity.properties.clientId
        }
        {
          name: 'SCALE_STREET_AGENT_MODE'
          value: 'foundry'
        }
        {
          name: 'SCALE_STREET_SCALE_PROFILE'
          value: 'constrained'
        }
        {
          name: 'FOUNDRY_PROJECT_ENDPOINT'
          value: foundryProjectEndpoint
        }
        {
          name: 'FOUNDRY_MODEL'
          value: 'gpt-5-mini'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: applicationInsights.properties.ConnectionString
        }
      ]
    }
  }
  dependsOn: [
    containerRegistryPull
  ]
}

output webAppName string = webApp.name
output webAppUrl string = 'https://${webApp.properties.defaultHostName}'
