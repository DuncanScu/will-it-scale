# Azure Resource Classification and Checks

This rubric supports development and review of the Azure Scale Investigator
profile. The runtime instructions remain in the `.agent.md` profile so the
agent can be installed independently of this repository.

## Classification rules

### Direct capacity resource

A resource is direct capacity when it:

- accepts application traffic
- executes request or background work
- stores or queries application data
- buffers asynchronous work
- imposes request, token, connection, partition, throughput, or concurrency
  limits

Examples include AKS, App Service, Container Apps, Functions, API Management,
Azure AI deployments, databases, caches, Service Bus, and Event Hubs.

### Scale-path dependency

A resource is a scale-path dependency when it can affect startup, scale-out,
networking, authentication, configuration, or deployment but is not normally
the steady-state request processor.

Examples include Container Registry, Key Vault, managed identity, private
endpoints, DNS, NAT Gateway, and virtual networks.

### Operational evidence resource

A resource is operational evidence when it provides the measurements required
to verify scalability.

Examples include Application Insights, Log Analytics, diagnostic settings,
metric alerts, workbooks, and action groups.

### Administrative or non-scaling resource

A resource is administrative when it groups, authorizes, governs, or labels
other resources and has no meaningful configurable runtime throughput.

Examples include resource groups, role assignments, resource locks, tags, and
most policy assignments.

## Inspection matrix

| Resource family | Classification | Configuration checks | Runtime evidence |
|---|---|---|---|
| AKS | Direct capacity | Node pools, VM SKU, nodes, autoscaler bounds, zones, max pods, replicas, HPA, requests and limits, probes, PDB, ingress, outbound networking | CPU, memory, pending pods, restarts, replica changes, request latency, errors |
| App Service | Direct capacity | Plan SKU, worker count, autoscale, always-on, deployment slots, runtime limits | CPU, memory, requests, queue, response time, HTTP errors, instance count |
| Container Apps | Direct capacity | Environment, min/max replicas, scale rules, concurrency, CPU, memory, revisions | Replicas, requests, latency, CPU, memory, restarts, scale events |
| Functions | Direct capacity | Plan, instance limits, concurrency, timeout, triggers, always-ready instances | Executions, latency, failures, throttles, instances, queue age |
| Azure AI deployment | Direct capacity | Model, version, deployment type, SKU, capacity, regional quota, shared use | Tokens, requests, latency, HTTP 429, utilization |
| API Management | Direct capacity | Tier, units, regional deployment, policies, backend timeout, rate limits | Capacity, requests, latency, throttling, backend errors |
| Cosmos DB | Direct capacity | RU/s, autoscale ceiling, partition key, consistency, regions | Consumed RU, throttling, latency, hot partitions, availability |
| Azure SQL | Direct capacity | Tier, vCores or DTUs, connections, replicas, zones, storage | CPU, data IO, log IO, workers, sessions, deadlocks, storage |
| PostgreSQL/MySQL | Direct capacity | Tier, compute, storage, IOPS, connections, pooling, replicas | CPU, memory, IO, connections, storage, replication lag |
| Storage account | Direct capacity or scale-path dependency | Service type, SKU, redundancy, network access, access pattern | Transactions, latency, throttling, availability, egress |
| Redis | Direct capacity | Tier, memory, shards, replicas, connections, eviction | Server load, memory, connections, cache misses, evictions |
| Service Bus | Direct capacity | Tier, messaging units, partitions, sessions, duplicate detection | Queue depth, age, dead letters, throttling, incoming and outgoing messages |
| Event Hubs | Direct capacity | Tier, partitions, throughput units, auto-inflate, retention | Incoming and outgoing throughput, throttling, consumer lag |
| Front Door/Application Gateway | Direct capacity or scale-path dependency | SKU, origins, health probes, timeout, WAF, routing | Requests, latency, origin health, errors, capacity |
| Load Balancer/Ingress | Scale-path dependency | SKU, rules, probes, backend pools, idle timeout | Health, flow count, SNAT usage where available |
| NAT Gateway | Scale-path dependency | Public IPs, subnets, idle timeout | SNAT ports, connections, packet and byte counts |
| Virtual network/private endpoint/DNS | Scale-path dependency | Address space, subnet capacity, links, endpoint and DNS topology | Resolution or connection failures when available |
| Container Registry | Scale-path dependency | Tier, network access, replication, image references | Pull failures, request count, storage, regional availability |
| Key Vault | Scale-path dependency | Network access, references, identity access model | Request volume, latency, throttling, failures |
| Managed identity | Scale-path dependency | Assignment and dependency references | Usually no direct scale metric; inspect application token behavior separately |
| Application Insights | Operational evidence | Connection, sampling, retention, daily cap | Requests, dependencies, traces, exceptions, custom metrics |
| Log Analytics | Operational evidence | Diagnostic coverage, retention, daily cap | Queryable operational and platform evidence |
| Diagnostic settings | Operational evidence | Enabled categories, destinations, retention | Whether required evidence is actually arriving |
| Resource group | Administrative | Correlation and ownership only | None |
| Role assignment | Administrative | Whether read access exists; do not inspect as capacity | None |
| Lock, tag, policy assignment | Administrative | Governance and correlation only | None |

## Cross-resource questions

For each end-to-end path, answer:

1. What controls ingress capacity?
2. What controls application concurrency?
3. Where does work wait?
4. Which dependency has fixed capacity?
5. Does application scale-out increase pressure on that dependency?
6. Where is state stored?
7. Can multiple replicas process work consistently?
8. Which network boundary limits connections or egress?
9. Which quota is shared by multiple applications?
10. Which telemetry proves or disproves the hypothesis?

## Exclusion language

Use explicit explanations rather than silently omitting resources:

> Managed identity was inventoried as a scale-path dependency. It has no
> configurable request capacity and therefore received no direct sizing check.
> Token acquisition behavior in the application remains an application-level
> consideration.

> The resource group was inventoried as administrative. It groups resources
> but does not process runtime traffic.

> The role assignment was inventoried as administrative. It controls access
> but does not determine request throughput.
