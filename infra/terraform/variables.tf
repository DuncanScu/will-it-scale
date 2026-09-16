variable "hub_subscription_id" {
  type        = string
  description = "Subscription hosting the Foundry agent and the collector managed identity."
}

variable "target_subscription_id" {
  type        = string
  description = "Subscription that owns the target AKS cluster being assessed."
}

variable "location" {
  type        = string
  description = "Azure region for the hub resources (identity, Foundry)."
  default     = "eastus"
}

variable "name_prefix" {
  type        = string
  description = "Short prefix for all created resource names."
  default     = "deploy-assess"
}

variable "target_aks_id" {
  type        = string
  description = "Full ARM resource ID of an EXISTING target AKS cluster. Ignored when create_test_aks = true."
  default     = ""
}

variable "create_test_aks" {
  type        = bool
  description = "Create a throwaway AKS cluster to experiment against (single-subscription case)."
  default     = false
}

variable "test_aks_node_count" {
  type        = number
  description = "Node count for the test AKS default pool."
  default     = 1
}

variable "test_aks_vm_size" {
  type        = string
  description = "VM size for the test AKS default pool."
  default     = "Standard_D2s_v3"
}

variable "aks_rbac_namespace" {
  type        = string
  description = "Optional namespace to scope Kubernetes read access to. Empty string = whole cluster."
  default     = ""
}

variable "grant_subscription_reader" {
  type        = bool
  description = "Grant Reader at the target subscription scope so the collector can read vCPU/VM quotas."
  default     = true
}

variable "cosmos_account_id" {
  type        = string
  description = "Optional full ARM resource ID of the Cosmos DB account (for RU metrics). Empty = skip."
  default     = ""
}

variable "deploy_foundry" {
  type        = bool
  description = "Whether to provision the Azure AI Foundry account/project/model in this stack."
  default     = true
}

variable "foundry_model_name" {
  type        = string
  description = "Model to deploy for the reasoning agent."
  default     = "gpt-4.1"
}

variable "foundry_model_version" {
  type        = string
  description = "Model version for the deployment."
  default     = "2025-04-14"
}

variable "foundry_model_capacity" {
  type        = number
  description = "Deployment capacity in thousands of tokens per minute (TPM)."
  default     = 50
}
