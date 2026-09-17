terraform {
  required_version = ">= 1.6"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azapi = {
      source  = "Azure/azapi"
      version = "~> 2.0"
    }
  }
}

# Subscription that hosts the Foundry agent + collector identity (yours).
provider "azurerm" {
  features {}
  subscription_id = var.hub_subscription_id
}

# Subscription that owns the target AKS cluster being assessed.
# Same Entra tenant, so a single `az login` with rights in both subs is enough.
provider "azurerm" {
  alias           = "target"
  features {}
  subscription_id = var.target_subscription_id
}
