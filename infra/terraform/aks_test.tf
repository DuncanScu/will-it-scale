# -----------------------------------------------------------------------------
# Optional throwaway AKS cluster to experiment against.
# Enabled with create_test_aks = true. Assumes hub and target are the SAME
# subscription (the experiment case). Comes with AAD + Azure RBAC for Kubernetes
# already enabled so the collector's "AKS RBAC Reader" grant authorizes reads.
# -----------------------------------------------------------------------------

data "azurerm_client_config" "current" {}

resource "azurerm_kubernetes_cluster" "test" {
  count = var.create_test_aks ? 1 : 0

  name                = "${var.name_prefix}-aks"
  location            = azurerm_resource_group.hub.location
  resource_group_name = azurerm_resource_group.hub.name
  dns_prefix          = "${var.name_prefix}-aks"

  default_node_pool {
    name       = "system"
    node_count = var.test_aks_node_count
    vm_size    = var.test_aks_vm_size
  }

  identity {
    type = "SystemAssigned"
  }

  azure_active_directory_role_based_access_control {
    azure_rbac_enabled = true
    tenant_id          = data.azurerm_client_config.current.tenant_id
  }
}

locals {
  # Use the created test cluster if enabled, otherwise the supplied resource ID.
  effective_aks_id = var.create_test_aks ? azurerm_kubernetes_cluster.test[0].id : var.target_aks_id
}
