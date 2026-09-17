# Scale Street

Scale Street is a deliberately constrained financial-services demo application
for the **Will It Scale?** investigation agents.

The application simulates a trading floor where financial agents analyze paper
portfolios during an opening-bell traffic spike. It is intentionally configured
with several explainable scalability risks so source-code, Foundry, AKS, Azure
resource, architecture, and telemetry checkers can correlate evidence.

## Run locally

```shell
uv sync
uv run uvicorn scale_street.main:app --reload
```

Open <http://127.0.0.1:8000>.

By default, the application uses a deterministic simulated financial advisor.
To use Microsoft Agent Framework with a model deployed in Microsoft Foundry:

```shell
export SCALE_STREET_AGENT_MODE=foundry
export FOUNDRY_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
export FOUNDRY_MODEL=gpt-5-mini
az login
uv run uvicorn scale_street.main:app
```

The runtime identity needs both **Foundry User** and
**Cognitive Services OpenAI User** on the Foundry account.

## Azure Container Instances fallback

Azure Container Instances were used temporarily while AKS provisioning was
blocked. Both fallback container groups were removed on September 17, 2026
after the AKS deployment passed health, readiness, and Foundry validation.
The templates remain available if a fallback is needed again. ACR must use the
Premium SKU for ACI managed-identity image pulls.

```shell
az deployment group create \
  --resource-group ScaleStreet_RG \
  --name scale-street-aci \
  --template-file infra/container-instance.bicep \
  --parameters \
    location=eastus2 \
    containerGroupName=scalestreet-aci \
    dnsNameLabel=<globally-unique-label> \
    acrName=<registry-name> \
    foundryProjectEndpoint=<project-endpoint> \
    agentMode=foundry
```

Set `agentMode=simulated` for a deterministic backup that does not consume
Foundry quota.

## Intentional findings

The constrained profile is designed to expose these findings:

- A synchronous request/response dependency on the Foundry financial agent.
- No queue or back-pressure boundary between HTTP traffic and agent calls.
- Recommendation history held in process memory and not shared across replicas.
- A single application replica in the constrained Kubernetes deployment.
- A single-node AKS cluster with no workload redundancy.
- No Horizontal Pod Autoscaler or Pod Disruption Budget.
- A target-state architecture document that does not match the deployed state.

The `k8s/improved` directory contains an improved deployment shape for
comparison. It is not applied by the default deployment script.

## Load generation

```shell
uv run python load_tests/market_open.py \
  --base-url http://127.0.0.1:8000 \
  --customers 250 \
  --concurrency 40
```

## Tests and linting

```shell
uv run ruff check .
uv run pytest
```

See `TODO.md` for the remaining AKS-only deployment and validation steps.
