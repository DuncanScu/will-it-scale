targetScope = 'resourceGroup'

@description('Azure region for all Scale Street resources.')
param location string = resourceGroup().location

@description('Short prefix used for resource names.')
param namePrefix string = 'scalestreet'

@description('AKS VM size. One node is intentional for the constrained demo.')
param aksVmSize string = 'Standard_D2s_v6'

@allowed([
  'Basic'
  'Standard'
  'Premium'
])
@description('Azure Container Registry SKU. Premium supports ACI managed-identity pulls.')
param acrSkuName string = 'Premium'

@description('Deploy the pinned demo model after confirming regional quota.')
param deployFoundryModel bool = false

@minValue(1)
@description('Model deployment capacity in thousands of tokens per minute.')
param foundryModelCapacity int = 1

var suffix = uniqueString(subscription().id, resourceGroup().id)
var acrName = toLower(replace('${namePrefix}${suffix}', '-', ''))
var aksName = '${namePrefix}-aks'
var logAnalyticsName = '${namePrefix}-law'
var appInsightsName = '${namePrefix}-appi'
var foundryName = '${namePrefix}-ai-${suffix}'
var foundryProjectName = '${namePrefix}-project'
var workloadIdentityName = '${namePrefix}-workload'
var openAiUserRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
)
var foundryUserRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '53ca6127-db72-4b80-b1b0-d745d6d5456d'
)

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2025-11-01' = {
  name: acrName
  location: location
  sku: {
    name: acrSkuName
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2025-07-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
  }
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    Flow_Type: 'Bluefield'
    IngestionMode: 'LogAnalytics'
    Request_Source: 'rest'
    WorkspaceResourceId: logAnalytics.id
  }
}

resource workloadIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: workloadIdentityName
  location: location
}

resource aks 'Microsoft.ContainerService/managedClusters@2025-07-01' = {
  name: aksName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    dnsPrefix: aksName
    enableRBAC: true
    oidcIssuerProfile: {
      enabled: true
    }
    securityProfile: {
      workloadIdentity: {
        enabled: true
      }
    }
    autoUpgradeProfile: {
      nodeOSUpgradeChannel: 'NodeImage'
    }
    agentPoolProfiles: [
      {
        name: 'system'
        count: 1
        vmSize: aksVmSize
        osType: 'Linux'
        osSKU: 'AzureLinux'
        mode: 'System'
        type: 'VirtualMachineScaleSets'
        enableAutoScaling: false
        maxPods: 30
      }
    ]
    addonProfiles: {
      omsagent: {
        enabled: true
        config: {
          logAnalyticsWorkspaceResourceID: logAnalytics.id
          useAADAuth: 'true'
        }
      }
    }
    networkProfile: {
      networkPlugin: 'azure'
      networkPluginMode: 'overlay'
      networkPolicy: 'azure'
      loadBalancerSku: 'standard'
      outboundType: 'loadBalancer'
    }
  }
}

resource workloadFederation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2024-11-30' = {
  name: 'scale-street-aks'
  parent: workloadIdentity
  properties: {
    audiences: [
      'api://AzureADTokenExchange'
    ]
    issuer: aks.properties.oidcIssuerProfile.issuerURL
    subject: 'system:serviceaccount:default:scale-street'
  }
}

resource foundry 'Microsoft.CognitiveServices/accounts@2026-05-01' = {
  name: foundryName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: foundryName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2026-05-01' = {
  name: foundryProjectName
  parent: foundry
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: 'Scale Street'
    description: 'Financial-services demo for the Will It Scale? agents.'
  }
}

resource foundryModel 'Microsoft.CognitiveServices/accounts/deployments@2026-05-01' = if (deployFoundryModel) {
  name: 'gpt-5-mini'
  parent: foundry
  sku: {
    name: 'GlobalStandard'
    capacity: foundryModelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5-mini'
      version: '2025-08-07'
    }
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
}

resource foundryAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, workloadIdentity.id, openAiUserRoleDefinitionId)
  scope: foundry
  properties: {
    principalId: workloadIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: openAiUserRoleDefinitionId
  }
}

resource foundryProjectAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, workloadIdentity.id, foundryUserRoleDefinitionId)
  scope: foundry
  properties: {
    principalId: workloadIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: foundryUserRoleDefinitionId
  }
}

output resourceGroupName string = resourceGroup().name
output acrName string = containerRegistry.name
output acrLoginServer string = containerRegistry.properties.loginServer
output aksName string = aks.name
output applicationInsightsConnectionString string = applicationInsights.properties.ConnectionString
output foundryAccountName string = foundry.name
output foundryProjectName string = foundryProject.name
output foundryProjectEndpoint string = 'https://${foundry.name}.services.ai.azure.com/api/projects/${foundryProject.name}'
output workloadIdentityClientId string = workloadIdentity.properties.clientId
