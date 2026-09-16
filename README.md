# will-it-scale

A read-only **deployment assessment agent** for AKS. It reconciles what *should* be
running (replica floors, resource limits, health probes, autoscaling, disruption
budgets) against what *is* running, and produces findings for human review. It
recommends changes; it never deploys them.

> **Status:** experimental prototype. Validated end-to-end against a throwaway AKS
> cluster and the `test_data/sample_service` fixture. Read-only by design.

## How it works

Two layers keep the output trustworthy:

1. **Deterministic collectors + checks** gather grounded facts from the cluster and
   evaluate them into findings (`pass` / `warning` / `fail`) with evidence,
   severity, and remediation. This is the source of truth.
2. **AI interpretation (Azure AI Foundry)** takes those findings and prioritizes,
   groups, and explains them. The model only sees the findings — it cannot reach the
   cluster or invent facts, and output referencing unknown finding IDs is rejected.

Access is via a read-only **managed identity**: Azure RBAC for the control plane,
Azure RBAC for Kubernetes for the data plane, and `Cognitive Services OpenAI User`
for the model. See the architecture diagram in [notes.md](notes.md).

## Layout

```
infra/terraform/            # identity, read-only RBAC, test AKS, Foundry (IaC)
src/will_it_scale/
  collectors/k8s.py         # reads cluster + workload facts (control + data plane)
  checks.py                 # deterministic rules -> findings
  interpret.py              # Foundry interpretation layer
  findings_store.py         # saves runs to findings/<cluster>/<timestamp>.json
  assess.py                 # runner: collect -> check -> (interpret) -> save
findings/                   # saved assessment runs (JSON, git-ignored)
test_data/sample_service/   # deliberately-flawed demo app used as a fixture
tests/                      # pytest suite for the deterministic checks
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/), Terraform, and the Azure CLI (`az`)
- `az login` with rights to create resources and role assignments
- Install dependencies:

  ```shell
  uv sync
  ```

## Provision infrastructure

```shell
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars   # set subscription IDs, target, model
terraform init
terraform apply
```

This creates the collector managed identity, its read-only role assignments, an
optional throwaway AKS cluster (`create_test_aks = true`), and the Foundry account +
model deployment. Tear everything down with `terraform destroy`.

## Run the assessment

The runner targets a cluster via environment variables (defaults shown):

| Variable | Default | Purpose |
|----------|---------|---------|
| `AZURE_SUBSCRIPTION_ID` | — | Subscription of the target cluster |
| `TARGET_RG` | `deploy-assess-rg` | Resource group |
| `TARGET_CLUSTER` | `deploy-assess-aks` | AKS cluster name |
| `TARGET_NAMESPACE` | `kube-system` | Namespace to assess |
| `FOUNDRY_ENDPOINT` | account endpoint | Foundry endpoint (AI mode) |
| `FOUNDRY_DEPLOYMENT` | `gpt-4.1` | Model deployment name (AI mode) |

The caller (managed identity in production, or your `az login` for local testing)
needs **AKS RBAC Reader** on the cluster; AI mode additionally needs **Cognitive
Services OpenAI User** on the Foundry account.

### Deterministic only

Facts and findings, no model involved:

```shell
uv run python -m will_it_scale.assess
```

### With AI interpretation

Adds the Foundry-generated executive summary and prioritized risks:

```shell
INTERPRET=1 uv run python -m will_it_scale.assess
```

### Try it against the sample fixture

`test_data/sample_service` is a deliberately-flawed order service (single replica,
no CPU/memory limits, a pinned HPA, and no liveness probe). Deploy it to a cluster
and assess that namespace to watch the checks fire:

```shell
kubectl apply -n demo -f test_data/sample_service/kubernetes/deployment.yaml
TARGET_NAMESPACE=demo uv run python -m will_it_scale.assess
```

## Output

Each run prints a summary and writes a timestamped JSON file to
`findings/<cluster>/<timestamp>.json` containing the run summary, every finding
(schema: `id`, `status`, `evidence`, `confidence`, `severity`, `remediation`), and
the AI `interpretation` when enabled. Runs are diffed against the previous run to
surface new regressions.

## Testing

Run the deterministic check suite. It needs no cluster or Azure access — the checks
are exercised against constructed facts, so it is safe to run anywhere and in CI:

```shell
uv run pytest
```
