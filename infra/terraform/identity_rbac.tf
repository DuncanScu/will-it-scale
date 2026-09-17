# -----------------------------------------------------------------------------
# Hub resource group + collector identity (in YOUR subscription)
# -----------------------------------------------------------------------------

resource "azurerm_resource_group" "hub" {
  name     = "${var.name_prefix}-rg"
  location = var.location
}

# Single user-assigned identity the collector tools authenticate as.
# The Foundry agent calls the collectors; the collectors use THIS identity to
# reach ARM + the target cluster. No static secrets.
resource "azurerm_user_assigned_identity" "collector" {
  name                = "${var.name_prefix}-collector-mi"
  resource_group_name = azurerm_resource_group.hub.name
  location            = azurerm_resource_group.hub.location
}

# -----------------------------------------------------------------------------
# Cross-subscription Azure RBAC on the target AKS (control plane / ARM)
# -----------------------------------------------------------------------------

# Read AKS config, node pools, versions, upgrades.
resource "azurerm_role_assignment" "aks_reader" {
  provider             = azurerm.target
  scope                = local.effective_aks_id
  role_definition_name = "Reader"
  principal_id         = azurerm_user_assigned_identity.collector.principal_id
  principal_type       = "ServicePrincipal"
}

# Pull a user (non-admin) kubeconfig via listClusterUserCredential.
resource "azurerm_role_assignment" "aks_cluster_user" {
  provider             = azurerm.target
  scope                = local.effective_aks_id
  role_definition_name = "Azure Kubernetes Service Cluster User Role"
  principal_id         = azurerm_user_assigned_identity.collector.principal_id
  principal_type       = "ServicePrincipal"
}

# -----------------------------------------------------------------------------
# Kubernetes data-plane reads via Azure RBAC for Kubernetes Authorization.
# Requires the target cluster to have `azure-rbac` enabled. Scope can be the
# whole cluster or a single namespace for least privilege.
# -----------------------------------------------------------------------------
resource "azurerm_role_assignment" "aks_rbac_reader" {
  provider             = azurerm.target
  scope                = var.aks_rbac_namespace == "" ? local.effective_aks_id : "${local.effective_aks_id}/namespaces/${var.aks_rbac_namespace}"
  role_definition_name = "Azure Kubernetes Service RBAC Reader"
  principal_id         = azurerm_user_assigned_identity.collector.principal_id
  principal_type       = "ServicePrincipal"
}

# -----------------------------------------------------------------------------
# Subscription-scope Reader for vCPU/VM quota reads (az vm list-usage).
# -----------------------------------------------------------------------------
resource "azurerm_role_assignment" "subscription_reader" {
  count                = var.grant_subscription_reader ? 1 : 0
  provider             = azurerm.target
  scope                = "/subscriptions/${var.target_subscription_id}"
  role_definition_name = "Reader"
  principal_id         = azurerm_user_assigned_identity.collector.principal_id
  principal_type       = "ServicePrincipal"
}

# -----------------------------------------------------------------------------
# Optional: Cosmos DB RU signals (control-plane metrics via Azure Monitor).
# -----------------------------------------------------------------------------
resource "azurerm_role_assignment" "cosmos_account_reader" {
  count                = var.cosmos_account_id == "" ? 0 : 1
  provider             = azurerm.target
  scope                = var.cosmos_account_id
  role_definition_name = "Cosmos DB Account Reader Role"
  principal_id         = azurerm_user_assigned_identity.collector.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "cosmos_monitoring_reader" {
  count                = var.cosmos_account_id == "" ? 0 : 1
  provider             = azurerm.target
  scope                = var.cosmos_account_id
  role_definition_name = "Monitoring Reader"
  principal_id         = azurerm_user_assigned_identity.collector.principal_id
  principal_type       = "ServicePrincipal"
}

output "collector_identity_client_id" {
  description = "Client ID the collector uses for DefaultAzureCredential (AZURE_CLIENT_ID)."
  value       = azurerm_user_assigned_identity.collector.client_id
}

output "collector_identity_principal_id" {
  value = azurerm_user_assigned_identity.collector.principal_id
}
