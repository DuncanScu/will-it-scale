# Will It Scale? Project Context

## Purpose

Will It Scale? is an AI-assisted production-readiness investigation tool. It turns a stakeholder interview and distributed technical evidence into an explainable assessment of what is most likely to prevent an application from supporting a target workload.

The central question is:

> Given the expected workload, known concerns, documented architecture, implementation, deployment configuration, and observed production behavior, what is most likely to prevent this system from scaling?

The product should answer:

- Can the application plausibly support the target workload?
- Which component or dependency is most likely to fail first?
- What evidence supports or contradicts that conclusion?
- Are the engineer's concerns confirmed, handled, or still unknown?
- What additional risks were discovered?
- What should the team change or measure next?

## Product Principles

- Evidence-backed reasoning is more valuable than generic architecture advice.
- Important conclusions should cite their source, observed evidence, assumptions, and confidence.
- The system must be willing to conclude that there is insufficient evidence.
- Facts, assumptions, unknowns, and proposed validations must remain distinct.
- The intake interview creates hypotheses, but baseline analysis must still discover concerns that were not raised.
- Controlled exported artifacts are the initial integration boundary; live enterprise connectors are stretch goals.

## Investigation Workflow

1. Interview an engineer or TPM about the service, target workload, success criteria, known symptoms, and concerns.
2. Create a concern ledger. Each concern becomes an investigation hypothesis.
3. Locate evidence sources, owners, versions, and access constraints.
4. Build a compact model of the system, dependencies, and critical workload path.
5. Analyze repository code, Kubernetes configuration, architecture documents, Confluence exports, and bounded telemetry.
6. Correlate evidence across sources and identify contradictions or missing information.
7. Produce a verdict, confidence assessment, prioritized findings, and validation plan.

### Intake topics

The required opening questions should establish:

- Application or service under assessment.
- Target and current scale: users, RPS, concurrency, data volume, jobs, or agent executions.
- Traffic pattern and future growth.
- Latency, availability, throughput, and error-rate targets.
- Primary concern: capacity, reliability under load, recovery, cost, or a combination.
- Most important user journey or workload.
- Existing symptoms, incidents, load tests, or suspected failure points.
- Locations of the repository, Kubernetes files, SAD, Confluence material, and telemetry.
- People who can clarify missing or conflicting information.

Follow-up questions should be conditional. For example, queue growth should prompt questions about arrival rate, processing rate, backlog, retries, and dead-letter queues.

## Finding Model

The concern ledger uses these statuses:

- **Confirmed concern**: evidence supports a concern raised during intake.
- **Handled concern**: implementation or operating model appears to mitigate it.
- **New finding**: investigation found a material risk not raised during intake.
- **Unknown**: evidence is missing, inaccessible, stale, or contradictory.
- **Next validation**: a measurement or test is needed to confirm the conclusion.

A shared finding should contain, at minimum:

```json
{
  "concernId": "database-capacity",
  "category": "runtime",
  "status": "confirmed",
  "finding": "Database throttling begins during peak traffic",
  "evidence": [
    {
      "source": "telemetry",
      "reference": "cosmos-errors.json",
      "observation": "429 responses increase after 1,500 requests/second"
    }
  ],
  "impact": "Requests experience retries and higher latency",
  "recommendation": "Review partitioning and provisioned throughput",
  "confidence": 0.91
}
```

## Evidence Sources

### Repository and Kubernetes

Inspect critical request paths, blocking or expensive work, concurrency limits, connection reuse, retries, timeouts, circuit breakers, caching, batching, pagination, database access, queue consumers, deployments, services, ingress, jobs, replica counts, HPA, resource requests and limits, probes, disruption budgets, affinity, topology spread, and rollout configuration. Cite exact files and lines whenever possible.

### SAD and Confluence

Treat the SAD as documented architectural intent and a compliance baseline. Extract components, dependencies, deployment topology, resilience and scaling requirements, data stores, integration points, capacity assumptions, constraints, approved deviations, owners, and reviewers.

Use Confluence exports for architecture decisions, operational runbooks, known limitations, capacity results, incidents, dependency quotas, release notes, prior reviews, and links to authoritative SADs. Record title, modification date, and status because documentation may be stale or contradictory.

### Telemetry and operational evidence

Analyze bounded exports of exception signatures, timeouts, throttling, latency percentiles, throughput, error rates, CPU, memory, garbage collection, restarts, OOM kills, queue depth, processing delay, retries, dead-letter activity, database latency and connection exhaustion, cache hit rate, external dependency latency, autoscaling events, and deployment-correlated regressions.

The strongest findings correlate signals. For example: increased request volume, rising database latency, multiplied retries, and subsequent timeouts form a stronger conclusion than any one signal alone.

## Cross-Source Reasoning Examples

The investigation should detect conclusions such as:

- The SAD says the service is horizontally scalable, but Kubernetes has no HPA.
- Documentation claims a dependency supports 5,000 RPS, but telemetry shows throttling at 1,500 RPS.
- The engineer is worried about the database, but a downstream API is the current bottleneck.
- The architect describes asynchronous processing, but the repository performs part of the workflow synchronously.
- Kubernetes limits look reasonable, but production shows repeated OOM kills.
- A regional resilience requirement exists, but only one regional deployment is defined.

## Recommended Architecture

The hackathon recommendation is a single Investigation Architect agent backed by modular, structured skills. A full multi-agent swarm is intentionally out of scope for the first version because coordination, latency, debugging, and reliability add risk.

Planned skills:

- Intake: adaptive interview and assessment brief.
- Source locator: artifact locations, owners, versions, and access state.
- Repository: application and Kubernetes analysis.
- Document: SAD and exported Confluence analysis.
- Telemetry: bounded runtime and error analysis.
- Correlation: support, contradiction, and missing-evidence detection.
- Report: verdict, concern ledger, recommendations, and validation plan.

A hybrid pipeline is also a good long-term shape: deterministic analyzers collect structured evidence, then one agent synthesizes the narrative.

## Current Repository State

This repository currently implements a narrow vertical slice:

- `src/will_it_scale/tui.py` provides the Textual inline chat experience, splash screen, status updates, slash commands, cancellation, retry behavior, and follow-up conversation.
- `src/will_it_scale/assessment.py` reads the constrained Scale Street Kubernetes manifest, invokes Kubernetes and application-performance investigators, and passes their findings plus user requirements to the Investigation Architect.
- `src/will_it_scale/agents/investigation_architect.py` creates the Foundry-backed `InvestigationArchitect` agent using `gpt-4.1-mini` and Azure default credentials.
- `src/will_it_scale/agents/kubernetes_investigator.py` contains the Kubernetes specialist agent.
- `samples/scale_street/` is the controlled sample service and deployment fixture used by the CLI assessment flow.
- `tests/` covers the assessment flow and TUI behavior.

The current opening prompt asks for target throughput, latency and availability objectives, and traffic pattern or growth. The report is intentionally short, streamed, and limited to the most important concerns, unknowns, and next validation steps.

The current slice does **not** yet implement the full interview, concern ledger, source locator, SAD or Confluence analysis, telemetry analysis, structured finding schema, cross-source correlation, or evidence-rich final report described above.

## Three-Day Hackathon Scope

### Commit

- Guided engineer or TPM intake.
- Concern ledger.
- One sample repository with Kubernetes files.
- One representative SAD document.
- One small Confluence export or captured page.
- One telemetry and error dataset.
- Repository/Kubernetes, document, and telemetry analysis skills.
- Cross-source correlation.
- Evidence-backed final report.
- Simple visual investigation timeline.

### Simulate or stage

- Confluence authentication.
- Word document retrieval.
- Architect interaction.
- Datadog or other telemetry authentication.
- Live Kubernetes access.

### Stretch goals

- Convert one analyzer into a genuine specialist agent.
- Execute analyzers in parallel.
- Compare problematic and improved deployments.
- Generate an observability improvement patch.
- Connect one live enterprise source.
- Add LLM and token-consumption analysis.

Avoid attempting a full agent swarm, live access to every enterprise system, an Observability Rewriter, and precise mathematical capacity forecasting within the initial three-day event.

## Demonstration Story

The engineer says: "I am worried Cosmos DB will not handle 100,000 users."

The system captures workload, critical journey, symptoms, and evidence locations. It analyzes the repository, Kubernetes configuration, SAD, Confluence export, and telemetry. The SAD claims the service and database design support horizontal scaling. Repository analysis finds no major connection problem. Kubernetes shows appropriate application autoscaling. Telemetry confirms database throttling at peak traffic. The report confirms the database concern and discovers a more immediate downstream API rate limit, while separating handled, confirmed, new, and unknown items.

## Definition Of Success

A convincing demo should show that:

- Intake materially changes the investigation.
- Every important conclusion points to visible evidence.
- At least one engineer concern is confirmed or refuted.
- At least one additional risk is discovered.
- At least two sources contradict or qualify one another.
- Facts, assumptions, and missing evidence are clearly separated.
- The scenario runs deterministically within the demo window.
- Recommendations include concrete changes, measurements, or load tests.

The strongest narrow product is one that reliably identifies what is likely to fail first and proves the conclusion with visible evidence.
