# Azure Scale Investigator

Azure Scale Investigator is a read-only GitHub Copilot custom agent that
answers **"Will it scale?"** for the application in the developer's current
working directory.

It combines:

- Local project evidence such as source code, Bicep, Terraform, Kubernetes,
  deployment scripts, configuration, and architecture documents.
- Live Azure resource configuration and telemetry through Azure MCP.
- Cross-resource reasoning about capacity, elasticity, throughput, latency,
  resilience, state, networking, quotas, and observability.

The agent is separate from every application it inspects. `Scale Street` under
`samples/scale_street/` is only the first evaluation target.

## Repository organization

```text
will-it-scale/
├── .github/
│   └── agents/
│       └── azure-scale-investigator.agent.md
├── agents/
│   └── azure-scale-investigator/
│       ├── README.md
│       ├── checks/
│       │   ├── resource-classification.md
│       │   └── tool-policy.md
│       ├── schemas/
│       │   └── assessment-report.schema.json
│       ├── scripts/
│       │   ├── install-user-agent.sh
│       │   └── run-assessment.sh
│       └── tests/
│           ├── cases/
│           │   ├── monitor-error.md
│           │   └── scale-street.md
│           ├── validate_agent.py
│           ├── validate_installer.py
│           ├── validate_mcp_tools.py
│           └── validate_report_runner.py
└── samples/
    └── scale_street/
```

The custom-agent profile is intentionally self-contained. Files under
`agents/azure-scale-investigator/` document and test the profile, but are not
required in a project being assessed.

## Developer workflow

Start Copilot CLI in the project to inspect:

```shell
cd /path/to/project
copilot
```

Select the agent:

```text
/agent azure-scale-investigator
```

Then ask:

```text
Will it scale?
```

The agent:

1. Inspects the current project.
2. Creates an expected Azure resource manifest.
3. Resolves the likely tenant, subscription, resource group, and environment.
4. Stops live inspection and reports candidates if Azure scope is ambiguous.
5. Correlates declared resources with live Azure resources.
6. Classifies every resource by scale relevance.
7. Deeply inspects only relevant resources.
8. Evaluates cross-resource bottleneck chains.
9. Returns a read-only assessment with evidence labels and explicit unknowns.

The agent can also be called non-interactively:

```shell
copilot \
  --agent azure-scale-investigator \
  --allow-all-tools \
  --no-ask-user \
  --no-custom-instructions \
  --prompt "Will it scale?"
```

`--allow-all-tools` approves only tools visible to this agent profile. The
profile exposes local read/search tools and the read-only Azure MCP server; it
does not expose shell execution or file editing. This avoids per-tool approval
prompts without granting the agent additional capabilities.

`--no-ask-user` prevents interactive clarification prompts. If Azure scope is
ambiguous, the agent returns a partial static assessment, lists the candidate
scopes, and explains what must be supplied for a deterministic rerun.

The profile pins `gpt-5.4` so users do not unknowingly compare assessments
produced by different default models.

The launcher also uses `--no-custom-instructions` so unrelated `AGENTS.md`,
`CLAUDE.md`, `GEMINI.md`, or repository Copilot instructions cannot alter the
assessment workflow. The investigator can still read architecture and
deployment documents as project evidence.

## Installation scopes

### Repository development

The profile in `.github/agents/` is available while Copilot CLI is running in
this repository. Restart Copilot CLI after adding or changing the profile.

### User installation

Install the profile into `~/.copilot/agents/` to make it available from any
local project:

```shell
agents/azure-scale-investigator/scripts/install-user-agent.sh
```

Preview the operation without copying:

```shell
agents/azure-scale-investigator/scripts/install-user-agent.sh --dry-run
```

A user-level profile with the same filename takes precedence over a
repository-level profile.

The installer also creates:

```text
~/.local/bin/will-it-scale-azure
```

Run an uninterrupted assessment from any project:

```shell
cd /path/to/project
will-it-scale-azure .
```

By default, the terminal shows only an estimated completion percentage and the
saved report path. The percentage is a launcher activity estimate because
Copilot CLI does not expose authoritative phase completion. It advances while
the assessment process is running, never reports 100% early, and displays 100%
only after a successful assessment.

The launcher also prevents quiet hangs:

- It stops the run after five minutes without Copilot process I/O.
- It stops the run after 30 minutes of total execution time.
- Small heartbeat writes do not reset the idle timer; at least 4 KiB of
  additional Copilot I/O is required to count as meaningful activity.
- It terminates the Copilot process group, including Azure MCP children.
- It writes the timeout reason and partial output to a `_failed.md` report.

Override these limits when a deliberately long assessment requires it:

```shell
will-it-scale-azure \
  --idle-timeout 600 \
  --max-runtime 3600 \
  --activity-bytes 4096 \
  /path/to/project
```

The corresponding environment variables are
`WILL_IT_SCALE_IDLE_TIMEOUT_SECONDS` and
`WILL_IT_SCALE_MAX_RUNTIME_SECONDS`. The meaningful-I/O threshold can be
configured with `WILL_IT_SCALE_ACTIVITY_THRESHOLD_BYTES`.

To display the full assessment and Copilot diagnostics in addition to the
running status:

```shell
will-it-scale-azure --verbose .
```

Each completed run writes its final Markdown response to:

```text
reports/willitscale/willitscale_results_YYYYMMDD_HHMMSS_<unique>.md
```

The timestamp uses UTC. A random suffix generated by `mktemp` prevents
collisions when assessments start within the same second or run concurrently.
The Markdown is printed to the terminal only in verbose mode.

Or provide explicit scope in the prompt when a project has multiple
environments:

```shell
will-it-scale-azure . \
  "Will it scale? Use subscription <subscription-id> and resource group <name>."
```

The launcher runs:

```shell
copilot \
  -C <project> \
  --agent azure-scale-investigator \
  --allow-all-tools \
  --no-ask-user \
  --no-custom-instructions \
  --no-color \
  --silent \
  --stream off \
  --prompt "Will it scale?"
```

It deliberately uses `--allow-all-tools`, not `--allow-all`. Project path
access remains limited to the selected working directory, and arbitrary URL
access is not enabled.

The launcher, rather than the model, creates the report directory and file.
The agent therefore remains unable to edit arbitrary project files. If the
Copilot process fails, partial output is retained with a `_failed.md` suffix
and an incomplete-assessment warning at the top instead of being mistaken for
a completed report. Copilot diagnostics are hidden from the terminal by
default and included on screen in verbose mode. Raw diagnostics are not stored
in reports because they can contain sensitive operational context. Idle and
maximum-runtime failures include the watchdog reason in the report. A
zero-status Copilot exit is also treated as failed unless the output begins
with the required report title and contains the TL;DR and recommendations
sections. Pressing Ctrl+C terminates the Copilot/Azure MCP process group and
preserves the interrupted run as a failed report.

## Permission prompts and Azure MCP elicitation

Copilot CLI normally asks before using tools that have not been approved for
the session. A prompt such as **Manage Azure Kubernetes Service** is the
Copilot tool-permission gate for the Azure MCP namespace tool.

The unattended launcher suppresses those prompts by approving the agent's
filtered tool set at startup. Tool availability and approval remain separate:

- The profile's `tools` list determines what the model can see.
- `--allow-all-tools` approves those visible tools without prompting.
- The profile omits `execute` and `edit`.
- Azure MCP starts with `--read-only`.

Azure MCP also supports a separate elicitation mechanism for high-risk
operations such as returning secrets. The agent does not disable that safety
mechanism. Secret retrieval is prohibited by the profile, so a correct
assessment should never invoke it.

For consistent comparisons across users:

- Use the installed launcher rather than manually approving tools.
- Supply subscription and resource group explicitly when the repository does
  not identify one unique environment.
- Use the same agent profile revision.
- Keep the profile's pinned `gpt-5.4` model unless all comparison runs are
  deliberately moved to another shared model.
- Compare structured report sections and findings rather than raw tool-call
  order. Model inference is not byte-for-byte deterministic, but fixed tool
  availability, scope, workflow, sorting, metric windows, and report structure
  substantially reduce variation.

### Organization distribution

After validation, publish the approved profile as:

```text
agents/azure-scale-investigator.agent.md
```

in the organization's `.github` or `.github-private` repository. Keep this
repository as the source, documentation, test fixtures, and release history.

## Azure access

The profile starts the official Azure MCP Server with:

```shell
npx -y @azure/mcp@3.0.0-beta.44 server start --read-only --mode namespace
```

Prerequisites:

- Node.js and `npx`
- An authenticated Azure identity, normally through Azure CLI
- Reader access at the narrowest scope needed for the assessment
- Additional monitoring read access when Azure Monitor data is required

The server is explicitly read-only. The agent also prohibits Azure mutation,
secret retrieval, deployments, restarts, and load generation.

The agent exposes a curated set of Azure MCP namespaces rather than all Azure
tools. See [`checks/tool-policy.md`](checks/tool-policy.md) for the exact
permission identifiers, friendly display names, usage order, and excluded
namespaces.

The profile defines its own `azure-mcp` server. Do not add a second global
server with the same name. If startup fails, verify Node.js, `npx`, Azure
authentication, and network access, then run
`tests/validate_mcp_tools.py` to isolate server startup from the assessment.

## Scope resolution

The agent derives Azure scope from the project before querying live resources.
It uses:

1. Full Azure resource IDs
2. Explicit subscription and resource-group configuration
3. Infrastructure-as-code parameters and outputs
4. Azure Developer CLI environment configuration
5. Deployment scripts and documentation
6. Current Azure CLI context only as a candidate

It must not silently select between plausible environments or scan an entire
subscription without project evidence.

## Resource classification

Every correlated Azure resource receives one classification:

| Classification | Meaning |
|---|---|
| Direct capacity resource | Serves traffic, executes work, stores data, buffers work, or imposes throughput limits |
| Scale-path dependency | Affects startup, networking, authentication, configuration, or deployment |
| Operational evidence resource | Supplies metrics, logs, traces, diagnostics, or alerts |
| Administrative or non-scaling resource | Organizes, authorizes, tags, locks, or governs resources |

Managed identity is normally a scale-path dependency rather than a direct
capacity resource. The identity has no configurable throughput to size, but
application token acquisition and caching may still warrant separate review.

See [`checks/resource-classification.md`](checks/resource-classification.md)
for the full inspection matrix.

## Evidence model

All findings use one evidence label:

| Label | Meaning |
|---|---|
| Configured | Established from project files, IaC, Kubernetes, or Azure resource properties |
| Observed | Supported by metrics, logs, activity, or runtime state |
| Inferred | Reasoned from architecture but not directly measured |
| Unknown | Required evidence was unavailable |

The agent must never treat missing telemetry as evidence that a resource is
healthy.

## Assessment output

The report contains:

1. Report metadata
2. TL;DR
3. Application and deployment understanding
4. Azure scope
5. Complete resource inventory
6. Relevant resource findings
7. Cross-resource bottleneck chains
8. Excluded resources and rationale
9. Unknowns and missing evidence
10. Tool execution notes
11. Prioritized findings
12. Actions and recommendations

The TL;DR provides the verdict, overall confidence, highest-impact findings,
and highest-value next actions before the detailed analysis.

Every recommendation includes:

- the finding or unknown that motivated it
- why it should improve scaling or assessment confidence
- the expected scale benefit
- High, Medium, or Low confidence
- a justification for that confidence rating

The agent remains read-only. The standardized launcher persists its final
response under `reports/willitscale/`.

The JSON schema under `schemas/` documents the equivalent structured report
contract for validation and future integrations. The current launcher saves
the human-readable Markdown report rather than JSON.

### Fail-soft behavior

An individual Azure error does not terminate the assessment. The agent records
the tool, resource, status, sanitized message, attempted recovery, and effect
on confidence, then continues with independent checks.

For Azure Monitor, the agent lists metric definitions before issuing a metric
query. If a metric such as `ClientErrors` does not support the requested
aggregation or interval, it selects a supported combination and retries once.
If that retry fails, the metric is marked Unknown and the rest of the
assessment continues.

Authentication failures, missing resources, throttling, timeouts, empty
results, and unexpected responses each have bounded handling documented in
[`checks/tool-policy.md`](checks/tool-policy.md). No failed call is retried in
an open-ended loop.

## Testing

Validate the package:

```shell
python3 agents/azure-scale-investigator/tests/validate_agent.py
python3 agents/azure-scale-investigator/tests/validate_installer.py
python3 agents/azure-scale-investigator/tests/validate_report_runner.py
```

Validate that the pinned Azure MCP release still exposes exactly the approved
tool contract:

```shell
python3 agents/azure-scale-investigator/tests/validate_mcp_tools.py
```

The validation checks structural and safety invariants, including report
filename uniqueness, successful Markdown capture, and failed-run preservation.
Behavioral test cases
under `tests/cases/` describe expected outcomes for representative projects.

The first manual pilot is Scale Street:

```shell
cd samples/scale_street
copilot
```

Then select `azure-scale-investigator` and ask `Will it scale?`.

## Design principles

- Project first, Azure second
- Explicit Azure scope
- Complete inventory with transparent exclusions
- Type-specific checks instead of generic recommendations
- Cross-resource bottleneck analysis
- Separate capacity, elasticity, resilience, and observability
- Evidence-backed conclusions
- Read-only behavior
- No dependency on Scale Street or any other sample

## References

- [GitHub Copilot custom agents configuration](https://docs.github.com/en/copilot/reference/custom-agents-configuration)
- [Creating custom agents for Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli)
- [Azure MCP Server](https://learn.microsoft.com/azure/developer/azure-mcp-server/)
- [Azure MCP Server tools](https://learn.microsoft.com/azure/developer/azure-mcp-server/tools/)
