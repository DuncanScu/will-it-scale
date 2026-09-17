targetScope = 'resourceGroup'

@description('Name of the AKS cluster.')
param aksName string

@description('Azure region for the AKS cluster.')
param location string

@description('VM size for the single constrained node.')
param aksVmSize string = 'Standard_D2s_v6'

@description('Existing Log Analytics workspace resource ID.')
param logAnalyticsWorkspaceId string

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
          logAnalyticsWorkspaceResourceID: logAnalyticsWorkspaceId
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

output aksName string = aks.name
output nodeResourceGroup string = aks.properties.nodeResourceGroup
