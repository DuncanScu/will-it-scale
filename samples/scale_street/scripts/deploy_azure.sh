#!/usr/bin/env bash
set -euo pipefail

: "${AZURE_SUBSCRIPTION_ID:?Set AZURE_SUBSCRIPTION_ID before deploying.}"
SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID}"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-ScaleStreet_RG}"
LOCATION="${AZURE_LOCATION:-eastus2}"
DEPLOYMENT_NAME="scale-street-$(date -u +%Y%m%d%H%M%S)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

az account set --subscription "${SUBSCRIPTION_ID}"
az group create \
  --name "${RESOURCE_GROUP}" \
  --location "${LOCATION}" \
  --tags project=will-it-scale workload=scale-street environment=hackathon \
  --output none

for provider in \
  Microsoft.Authorization \
  Microsoft.CognitiveServices \
  Microsoft.ContainerRegistry \
  Microsoft.ContainerService \
  Microsoft.Insights \
  Microsoft.ManagedIdentity \
  Microsoft.OperationalInsights; do
  az provider register --namespace "${provider}" --wait
done

az deployment group create \
  --name "${DEPLOYMENT_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --template-file "${APP_DIR}/infra/main.bicep" \
  --parameters "${APP_DIR}/infra/main.parameters.json" \
  --output none

deployment_output() {
  az deployment group show \
    --name "${DEPLOYMENT_NAME}" \
    --resource-group "${RESOURCE_GROUP}" \
    --query "properties.outputs.${1}.value" \
    --output tsv |
    tr -d '\r'
}

acr_name="$(deployment_output acrName)"
acr_login_server="$(deployment_output acrLoginServer)"
aks_name="$(deployment_output aksName)"
foundry_endpoint="$(deployment_output foundryProjectEndpoint)"
workload_client_id="$(deployment_output workloadIdentityClientId)"
image="${acr_login_server}/scale-street:latest"

acr_id="$(
  az acr show \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${acr_name}" \
    --query id \
    --output tsv |
    tr -d '\r'
)"
kubelet_object_id="$(
  az aks show \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${aks_name}" \
    --query identityProfile.kubeletidentity.objectId \
    --output tsv |
    tr -d '\r'
)"
az role assignment create \
  --assignee-object-id "${kubelet_object_id}" \
  --assignee-principal-type ServicePrincipal \
  --role AcrPull \
  --scope "${acr_id}" \
  --output none

az acr build \
  --registry "${acr_name}" \
  --image scale-street:latest \
  "${APP_DIR}" \
  --output none

az aks get-credentials \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${aks_name}" \
  --overwrite-existing

if ! command -v kubectl >/dev/null 2>&1 ||
  ! kubectl version --client >/dev/null 2>&1; then
  mkdir -p "${HOME}/.local/bin"
  kubectl_version="$(curl -L --silent https://dl.k8s.io/release/stable.txt)"
  curl -L \
    --fail \
    --output "${HOME}/.local/bin/kubectl" \
    "https://dl.k8s.io/release/${kubectl_version}/bin/linux/amd64/kubectl"
  chmod +x "${HOME}/.local/bin/kubectl"
  export PATH="${HOME}/.local/bin:${PATH}"
  hash -r
fi

temporary_manifest="$(mktemp)"
trap 'rm -f "${temporary_manifest}"' EXIT

sed \
  -e "s|SCALE_STREET_IMAGE|${image}|g" \
  -e "s|FOUNDRY_PROJECT_ENDPOINT_VALUE|${foundry_endpoint}|g" \
  -e "s|WORKLOAD_IDENTITY_CLIENT_ID|${workload_client_id}|g" \
  "${APP_DIR}/k8s/constrained/deployment.yaml" \
  >"${temporary_manifest}"

kubectl apply -f "${temporary_manifest}"
kubectl apply -f "${APP_DIR}/k8s/constrained/service.yaml"
kubectl rollout status deployment/scale-street --timeout=5m

external_ip=""
for _ in {1..30}; do
  external_ip="$(
    kubectl get service scale-street \
      --output jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true
  )"
  if [[ -n "${external_ip}" ]]; then
    break
  fi
  sleep 10
done

echo "Scale Street image: ${image}"
echo "Foundry project endpoint: ${foundry_endpoint}"
if [[ -n "${external_ip}" ]]; then
  echo "Scale Street URL: http://${external_ip}"
else
  echo "The LoadBalancer IP is still provisioning."
fi
