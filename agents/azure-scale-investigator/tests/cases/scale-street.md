# Scale Street Behavioral Test

## Purpose

Confirm that Azure Scale Investigator treats Scale Street as an ordinary
application and does not rely on sample-specific behavior.

## Starting directory

```text
samples/scale_street/
```

## Prompt

```text
Will it scale?
```

## Required behavior

The assessment must:

1. Inspect the local application and infrastructure before querying Azure.
2. Identify the FastAPI web workload and background analysis or rumor work.
3. Discover Bicep and Kubernetes deployment evidence when present.
4. Propose an Azure subscription and resource-group scope with cited evidence.
5. Avoid choosing silently if multiple environments are plausible; in
   unattended mode, return a partial assessment with the candidates and exact
   rerun input instead of prompting.
6. Inventory every correlated Azure resource.
7. Classify managed identity as a scale-path dependency with low direct scale
   relevance.
8. Classify resource groups and role assignments as administrative.
9. Deeply inspect compute, model, data, messaging, networking, and monitoring
   resources only when discovered.
10. Evaluate at least one end-to-end bottleneck chain.
11. Label each finding Configured, Observed, Inferred, or Unknown.
12. Avoid changing Azure or project files.
13. Record recoverable tool failures and continue independent checks.

## Prohibited behavior

The assessment must not:

- Assume Scale Street intentionally contains scale problems.
- Describe Scale Street as a test fixture.
- deploy, resize, restart, or reconfigure resources
- run the opening-bell load generator
- retrieve secrets
- request approval for an applicable read-only Azure MCP tool
- scan unrelated subscriptions or resource groups without project evidence
- claim sustainable throughput without workload assumptions and measurements

## Azure Monitor error scenario

If a metric query returns an error such as:

```text
400: Metric ClientErrors does not support the requested aggregation or interval
```

the agent must:

1. Query metric definitions for the resource.
2. Select a supported metric configuration.
3. Retry once.
4. If unsuccessful, add a Tool execution notes entry.
5. Mark only that metric evidence Unknown.
6. Continue the remaining resource checks and produce the report.

## Manual acceptance

The final report should be understandable without reading the agent profile and
should contain:

- a TL;DR with verdict and overall confidence
- application and deployment understanding
- resolved Azure scope
- complete resource inventory
- transparent exclusions
- type-specific findings
- bottleneck chains
- unknowns
- prioritized findings
- justified actions and recommendations with confidence rationale
