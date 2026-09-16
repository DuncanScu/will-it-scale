targetScope = 'resourceGroup'

@description('Azure region for the container instance fallback.')
param location string = resourceGroup().location

@description('Name of the Scale Street container group.')
param containerGroupName string = 'scalestreet-aci'

@description('DNS label used for the public Scale Street endpoint.')
param dnsNameLabel string

@description('Name of the existing Azure Container Registry.')
param acrName string

@description('Name of the existing user-assigned managed identity.')
param workloadIdentityName string = 'scalestreet-workload'

@description('Name of the existing Application Insights component.')
param applicationInsightsName string = 'scalestreet-appi'

@description('Microsoft Foundry project endpoint.')
param foundryProjectEndpoint string

@allowed([
  'simulated'
  'foundry'
])
@description('Advisor implementation used by the deployed application.')
param agentMode string = 'foundry'

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

resource containerGroup 'Microsoft.ContainerInstance/containerGroups@2023-05-01' = {
  name: containerGroupName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${workloadIdentity.id}': {}
    }
  }
  properties: {
    containers: [
      {
        name: 'scale-street'
        properties: {
          image: '${containerRegistry.properties.loginServer}/scale-street:latest'
          command: [
            '/app/.venv/bin/python'
            '-m'
            'uvicorn'
            'scale_street.main:app'
            '--host'
            '0.0.0.0'
            '--port'
            '8000'
          ]
          ports: [
            {
              port: 8000
              protocol: 'TCP'
            }
          ]
          environmentVariables: [
            {
              name: 'AZURE_CLIENT_ID'
              value: workloadIdentity.properties.clientId
            }
            {
              name: 'SCALE_STREET_AGENT_MODE'
              value: agentMode
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
          resources: {
            requests: {
              cpu: 1
              memoryInGB: 1
            }
          }
        }
      }
    ]
    imageRegistryCredentials: [
      {
        server: containerRegistry.properties.loginServer
        identity: workloadIdentity.id
      }
    ]
    ipAddress: {
      type: 'Public'
      dnsNameLabel: dnsNameLabel
      ports: [
        {
          port: 8000
          protocol: 'TCP'
        }
      ]
    }
    osType: 'Linux'
    restartPolicy: 'Always'
  }
  dependsOn: [
    containerRegistryPull
  ]
}

output containerGroupName string = containerGroup.name
output containerIp string = containerGroup.properties.ipAddress.ip
output containerUrl string = 'http://${containerGroup.properties.ipAddress.fqdn}:8000'
