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
2. **AI reasoning (Azure AI Foundry)** consumes those grounded findings. Two
   front-ends build on them:
   - an **interactive investigation CLI** (`will-it-scale`) that captures workload
     requirements, then runs an investigator + architect agent pair over the
     grounded findings to stream a conversational scalability assessment;
   - a **deterministic runner** (`will_it_scale.assess`) with an optional
     interpretation pass that prioritizes findings.

   The model consumes the grounded findings as evidence — it does not replace them,
   and cannot reach the cluster or invent facts.

Access is via a read-only **managed identity**: Azure RBAC for the control plane,
Azure RBAC for Kubernetes for the data plane, and `Cognitive Services OpenAI User`
for the model. See the architecture diagram in [notes.md](notes.md).

## Azure AI Foundry configuration

The AI features use an Azure AI Foundry project. Defaults point at a **personal
subscription** for now:

- Project: `deploy-assess-foundry` / `deploy-assess-project`
- Model: `gpt-4.1`

> **This is temporary and will change.** The project currently lives in a personal
> subscription because access to the target team's subscription isn't available yet.
> When it is, repoint the agents by setting `FOUNDRY_PROJECT_ENDPOINT` and
> `FOUNDRY_MODEL` — no code change needed
> (see [src/will_it_scale/config.py](src/will_it_scale/config.py)).

## Layout

```
infra/terraform/            # identity, read-only RBAC, test AKS, Foundry (IaC)
src/will_it_scale/
  collectors/k8s.py         # reads workload facts from a live cluster
  collectors/manifest.py    # parses a manifest file into the same facts
  checks.py                 # deterministic rules -> findings
  interpret.py              # Foundry interpretation for the deterministic runner
  findings_store.py         # saves runs to findings/<label>/<timestamp>.json
  assess.py                 # deterministic runner: collect -> check -> (interpret) -> save
  agents/                   # investigator + architect agents (agent-framework)
  assessment.py             # orchestration: grounded findings -> agents -> report
  tui.py                    # interactive terminal UI (will-it-scale)
  config.py                 # Foundry endpoint/model (env-overridable)
findings/                   # saved assessment runs (JSON, git-ignored)
test_data/sample_service/   # deliberately-flawed demo app used as a fixture
tests/                      # pytest suites (checks, manifest, assessment, tui)
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

Two front-ends share the same deterministic evidence engine. Both are configured
through environment variables (defaults shown):

| Variable | Default | Purpose |
|----------|---------|---------|
| `AZURE_SUBSCRIPTION_ID` | — | Subscription of the target cluster |
| `TARGET_RG` | `deploy-assess-rg` | Resource group |
| `TARGET_CLUSTER` | `deploy-assess-aks` | AKS cluster name |
| `TARGET_NAMESPACE` | `kube-system` | Namespace to assess |
| `ASSESS_SOURCE` | `manifest` | `live` to assess a cluster namespace via the CLI |
| `FOUNDRY_PROJECT_ENDPOINT` | `deploy-assess-project` | Foundry project endpoint (CLI agents) |
| `FOUNDRY_MODEL` | `gpt-4.1` | Model for the CLI agents |
| `FOUNDRY_ENDPOINT` | account endpoint | Foundry endpoint (`assess` interpret mode) |
| `FOUNDRY_DEPLOYMENT` | `gpt-4.1` | Model deployment (`assess` interpret mode) |

The caller (managed identity in production, or your `az login` for local testing)
needs **AKS RBAC Reader** on the cluster; AI modes additionally need **Cognitive
Services OpenAI User** on the Foundry account.

### Granting yourself access (local testing)

When you run as your own identity rather than the collector managed identity, grant
the read roles first and remove them when finished. Live (data-plane) reads need
**AKS RBAC Reader**; `--interpret` additionally needs **Cognitive Services OpenAI
User**. Azure RBAC for Kubernetes caches authorization decisions, so allow up to
~5 minutes after granting before a live run succeeds.

```shell
PRINCIPAL=$(az ad signed-in-user show --query id -o tsv)
CLUSTER_ID=$(az aks show -g deploy-assess-rg -n deploy-assess-aks --query id -o tsv)
FOUNDRY_ID=$(az cognitiveservices account show -g deploy-assess-rg -n deploy-assess-foundry --query id -o tsv)

# grant (read-only)
az role assignment create --assignee "$PRINCIPAL" --role "Azure Kubernetes Service RBAC Reader" --scope "$CLUSTER_ID"
az role assignment create --assignee "$PRINCIPAL" --role "Cognitive Services OpenAI User" --scope "$FOUNDRY_ID"

# remove when finished
az role assignment delete --assignee "$PRINCIPAL" --role "Azure Kubernetes Service RBAC Reader" --scope "$CLUSTER_ID"
az role assignment delete --assignee "$PRINCIPAL" --role "Cognitive Services OpenAI User" --scope "$FOUNDRY_ID"
```

### Interactive investigation (CLI)

The interactive terminal UI asks for your workload and reliability targets, runs the
deterministic checks, then investigates with the Foundry agents and streams a
scalability assessment you can ask follow-up questions about:

```shell
uv run will-it-scale
```

By default it assesses the bundled manifest fixture. To assess a **live namespace**
instead, use `--source live` with `--namespace` (or the `TARGET_*` variables):

```shell
uv run will-it-scale --source live --namespace demo
```

You can also switch source **while the CLI is running** with `/live <namespace>` and
`/manifest` (see the commands below). Each investigation prints an `Assessing …` line
naming exactly what it is evaluating — the manifest file or live cluster/namespace,
plus the deployment names discovered there.

### Deterministic checks

Findings only, no agents. Add `--interpret` for the Foundry executive summary and
prioritized risks, and `--source live --namespace <ns>` to assess a cluster:

```shell
uv run will-it-scale --checks                                  # findings, manifest fixture
uv run will-it-scale --checks --interpret                      # + AI interpretation
uv run will-it-scale --checks --source live --namespace demo   # live cluster namespace
```

> Everything runs through the single `will-it-scale` command. Flags take precedence
> over the equivalent `TARGET_*` / `ASSESS_SOURCE` environment variables.

### Try it against the sample fixture

`test_data/sample_service` is a deliberately-flawed order service (single replica,
no CPU/memory limits, a pinned HPA, and no liveness probe). Assess the bundled
manifest directly, or deploy it and assess the live namespace:

```shell
uv run will-it-scale --checks                                  # the manifest fixture
kubectl apply -n demo -f test_data/sample_service/kubernetes/deployment.yaml
uv run will-it-scale --checks --source live --namespace demo   # the deployed app
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

## Interactive CLI reference

The inline terminal UI first asks for the workload and reliability targets to assess,
then investigates the available configuration against those requirements. It streams a
short assessment and accepts follow-up questions in the same conversation.

Commands and controls:

- `/live <namespace>` switches to a live cluster namespace and re-investigates.
- `/manifest` switches back to the bundled manifest fixture.
- `/help` shows the available commands.
- `/clear` clears the visible transcript without resetting the conversation.
- `/retry` restarts a failed or cancelled initial investigation.
- `/exit` or `Ctrl+C` quits.
- `Esc` cancels the active investigation or response.

On startup the CLI prints a welcome listing these commands and the launch flags, plus
the source it is currently assessing.

### Blender Easter Egg

Enter `/game` at the chat prompt to catch falling Kubernetes resources with the
startup animation's blender. Use the left and right arrow keys to move, `Space`
to pause, `R` to restart, and `Esc` to return to the conversation. Each catch earns
10 points; three misses end the round, and the pace increases with your score.
The game needs a playing area of at least 24 columns by 12 rows (a 24 by 14
terminal in inline mode) and pauses automatically below that size. Your
assessment and conversation are preserved.

With `--debug`, diagnostic logs are written to `will-it-scale.log` so they do not
interfere with the terminal UI.
