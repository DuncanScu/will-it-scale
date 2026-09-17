# -----------------------------------------------------------------------------
# Azure AI Foundry: hosts the LLM / orchestration layer (the "reasoning" half).
# The Foundry agent calls the collector tools; it does NOT talk to AKS directly.
#
# NOTE: the Foundry *project* resource type is new and the provider surface is
# still moving. The account + model deployment use stable azurerm resources; the
# project child uses azapi. Verify the api-version below against the current API
# (`az rest --method get --url ".../providers/Microsoft.CognitiveServices?api-version=2024-03-01"`)
# before applying in production.
# -----------------------------------------------------------------------------

resource "azurerm_cognitive_account" "foundry" {
  count = var.deploy_foundry ? 1 : 0

  name                  = "${var.name_prefix}-foundry"
  resource_group_name   = azurerm_resource_group.hub.name
  location              = azurerm_resource_group.hub.location
  kind                  = "AIServices"
  sku_name              = "S0"
  custom_subdomain_name = "${var.name_prefix}-foundry"

  # Required so the Foundry project child resource can be created.
  project_management_enabled = true

  identity {
    type = "SystemAssigned"
  }
}

# Model deployment used by the reasoning agent.
resource "azurerm_cognitive_deployment" "reasoning_model" {
  count = var.deploy_foundry ? 1 : 0

  name                 = var.foundry_model_name
  cognitive_account_id = azurerm_cognitive_account.foundry[0].id

  model {
    format  = "OpenAI"
    name    = var.foundry_model_name
    version = var.foundry_model_version
  }

  sku {
    name     = "GlobalStandard"
    capacity = var.foundry_model_capacity
  }
}

# Foundry project (agent workspace). azapi because provider coverage is new.
resource "azapi_resource" "foundry_project" {
  count = var.deploy_foundry ? 1 : 0

  type      = "Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview"
  name      = "${var.name_prefix}-project"
  parent_id = azurerm_cognitive_account.foundry[0].id
  location  = azurerm_resource_group.hub.location

  body = {
    identity = { type = "SystemAssigned" }
    properties = {
      displayName = "Deployment Assessment Agent"
      description = "Read-only reconciliation agent for AKS deployments."
    }
  }

  schema_validation_enabled = false
}

output "foundry_endpoint" {
  value       = var.deploy_foundry ? azurerm_cognitive_account.foundry[0].endpoint : null
  description = "Foundry account endpoint for the agent SDK."
}

# Let the collector identity call the model (interpretation layer) via AAD.
resource "azurerm_role_assignment" "foundry_openai_user" {
  count                = var.deploy_foundry ? 1 : 0
  scope                = azurerm_cognitive_account.foundry[0].id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.collector.principal_id
  principal_type       = "ServicePrincipal"
}
