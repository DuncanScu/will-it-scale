# Azure MCP Tool Policy

The Azure Scale Investigator uses an explicit allowlist rather than
`azure-mcp/*`. This keeps assessments repeatable and prevents unrelated Azure
capabilities from appearing during a run.

The Azure MCP server runs with:

```shell
npx -y @azure/mcp@3.0.0-beta.44 server start \
  --read-only \
  --mode namespace \
  --namespace subscription \
  --namespace group \
  --namespace insights \
  --namespace advisor \
  --namespace optimization \
  --namespace quota \
  --namespace resourcehealth \
  --namespace monitor \
  --namespace applicationinsights \
  --namespace applens \
  --namespace grafana \
  --namespace aks \
  --namespace acr \
  --namespace foundry \
  --namespace appservice \
  --namespace containerapps \
  --namespace functionapp \
  --namespace compute \
  --namespace cosmos \
  --namespace sql \
  --namespace postgres \
  --namespace mysql \
  --namespace redis \
  --namespace servicebus \
  --namespace eventhubs \
  --namespace storage \
  --namespace fileshares \
  --namespace kusto \
  --namespace search \
  --namespace eventgrid \
  --namespace signalr \
  --namespace iothub \
  --namespace servicefabric \
  --namespace datadog \
  --namespace workbooks
```

## Friendly labels and exact tool identifiers

Copilot may display a friendly label rather than the MCP identifier.

| Friendly label | Tool permission identifier | Purpose |
|---|---|---|
| Azure subscriptions | `azure-mcp/subscription_list` | Resolve accessible subscriptions and the current default |
| Azure Resource Manager MCP | `azure-mcp/group_list` | List resource groups in a resolved subscription |
| Azure Resource Manager MCP | `azure-mcp/group_resource_list` | Inventory resources within a resolved resource group |
| Azure infrastructure insights | `azure-mcp/insights` | Aggregate Resource Graph-backed infrastructure patterns |
| Azure Advisor | `azure-mcp/advisor` | Read applicable capacity, reliability, and optimization recommendations |
| Azure Optimization | `azure-mcp/optimization` | Explain right-sizing recommendations using observed utilization |
| Azure quota | `azure-mcp/quota` | Check regional availability, usage, and quota |
| Azure Resource Health | `azure-mcp/resourcehealth` | Read availability and service-health evidence |
| Azure Monitor | `azure-mcp/monitor` | Query metric definitions, metrics, activity, and logs |
| Azure Application Insights | `azure-mcp/applicationinsights` | Read Application Insights optimization recommendations |
| Azure AppLens | `azure-mcp/applens` | Read platform diagnostics for supported resources |
| Azure Managed Grafana | `azure-mcp/grafana` | Discover Grafana workspaces used for operational evidence |
| Manage Azure Kubernetes Service | `azure-mcp/aks` | Read AKS cluster and node-pool configuration |
| Azure Container Registry Services | `azure-mcp/acr` | Read registry and repository information |
| Microsoft Foundry MCP | `azure-mcp/foundry` | Read model deployment, project, monitoring, and capacity information |
| Azure App Service | `azure-mcp/appservice` | Read App Service configuration and diagnostics |
| Azure Container Apps | `azure-mcp/containerapps` | Read Container Apps resources |
| Azure Functions | `azure-mcp/functionapp` | Read Function App configuration |
| Azure Compute | `azure-mcp/compute` | Read VM, VMSS, and disk configuration and monitoring |
| Azure Cosmos DB | `azure-mcp/cosmos` | Read Cosmos DB configuration and query relevant metadata |
| Azure SQL | `azure-mcp/sql` | Read SQL server and database configuration |
| Azure Database for PostgreSQL | `azure-mcp/postgres` | Read server configuration and parameters |
| Azure Database for MySQL | `azure-mcp/mysql` | Read server configuration and parameters |
| Azure Cache for Redis | `azure-mcp/redis` | Read cache resources |
| Azure Service Bus | `azure-mcp/servicebus` | Read queues, topics, subscriptions, and runtime details |
| Azure Event Hubs | `azure-mcp/eventhubs` | Read namespaces, hubs, partitions, and consumer configuration |
| Azure Storage | `azure-mcp/storage` | Read storage account and container configuration |
| Azure Files | `azure-mcp/fileshares` | Read file-share configuration for stateful and shared-file workloads |
| Azure Data Explorer | `azure-mcp/kusto` | Read clusters, databases, schemas, and query operational data |
| Azure AI Search | `azure-mcp/search` | Read search indexes and service-backed query configuration |
| Azure Event Grid | `azure-mcp/eventgrid` | Read topics and event subscriptions |
| Azure SignalR | `azure-mcp/signalr` | Read real-time messaging service configuration |
| Azure IoT Hub | `azure-mcp/iothub` | Read hubs, devices, and runtime statistics for IoT workloads |
| Azure Service Fabric | `azure-mcp/servicefabric` | Read managed cluster and node state |
| Datadog | `azure-mcp/datadog` | Read Azure Datadog monitors and monitored-resource health |
| Azure Workbooks | `azure-mcp/workbooks` | Read operational dashboards used as assessment evidence |

## Required order

1. Local `search` and `read`
2. `subscription_list` only when project evidence does not provide one unique
   subscription
3. `group_list` only when resource-group resolution needs it
4. `group_resource_list` for the correlated inventory
5. `insights`, `advisor`, `optimization`, `quota`, and `resourcehealth` when
   applicable
6. Resource-specific namespace tools for resources selected for deep
   inspection
7. `monitor` for fixed one-hour and 24-hour metric or log windows
8. `applicationinsights`, `applens`, `grafana`, `datadog`, or `workbooks` only
   when discovered

## Intentionally excluded

| Namespace | Reason |
|---|---|
| `loadtesting` | Assessments must not create or execute load tests |
| `deploy` | Assessments must not deploy or modify infrastructure |
| `keyvault` | The agent must not retrieve secrets or sensitive values |
| `communication` | Sending email or SMS is unrelated to scale assessment |
| `resilience` | The namespace includes drill and mutation operations; use configuration, Resource Health, Advisor, and Monitor evidence instead |
| `policy` | Policy assignments are administrative unless a specific assessment later requires them |
| `role` | Role assignments are inventoried as administrative and do not need separate scale tooling |
| `marketplace` | Marketplace discovery is unrelated to deployed workload capacity |
| `extension` | Extension installation and generated CLI actions are not permitted |

The server is still started with `--read-only`, even for allowlisted
namespaces. The allowlist controls visibility; read-only mode controls server
operations.

The package version is pinned to prevent the namespace and tool contract from
changing between users during comparative testing. Upgrade it deliberately,
then rerun `tests/validate_mcp_tools.py` before distributing the profile.

## Permission behavior

The agent profile controls which tools are available but cannot approve its
own tools. Approval is a Copilot CLI security boundary.

For uninterrupted runs, use:

```shell
will-it-scale-azure .
```

The launcher passes `--allow-all-tools`, which approves only the tools visible
through the profile's allowlist. It does not grant file editing, shell
execution, unrestricted paths, or unrestricted URLs.

Starting Copilot normally and selecting the agent with `/agent` may still
prompt for first-time tool approval. A user can run `/allow-all`, but that is
broader than the supplied launcher and is not the recommended standardized
workflow.

## Error handling

Tool failures are assessment evidence, not a reason to discard the entire
report.

The agent uses bounded recovery:

| Error | Handling |
|---|---|
| Unsupported metric or aggregation (`400`) | Read metric definitions, correct once, then record Unknown |
| Other request validation (`400`) | Retry once only when the response provides a clear correction |
| Authentication or authorization (`401`/`403`) | Do not retry; record inaccessible evidence |
| Resource not found (`404`) | Refresh inventory once, then mark unable to verify |
| Timeout, throttling, or service failure (`408`/`429`/`5xx`) | Retry once with server delay when supplied |
| Empty result | Record no data; do not infer healthy behavior |
| Unexpected response | Record a tool-contract issue and continue |

Every unresolved failure appears in the final **Tool execution notes** section.
Independent resources and checks continue.
