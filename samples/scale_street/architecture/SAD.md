# Scale Street Solution Architecture Document

## Purpose

Scale Street provides paper-portfolio analysis during high-volume financial
market events. It uses a Microsoft Agent Framework financial agent backed by a
model deployed in Microsoft Foundry.

## Target workload

- 10,000 customers during the opening-bell period.
- 250 concurrent portfolio-analysis requests.
- p95 response latency below 2 seconds for accepted work.
- Graceful back-pressure when Foundry quota is exhausted.
- No single-node or single-pod failure may interrupt the service.

## Approved target architecture

- AKS spans multiple availability zones with at least three nodes.
- The web application runs at least three replicas.
- Horizontal Pod Autoscaling responds to CPU and request demand.
- Portfolio-analysis requests are queued and processed asynchronously.
- Equivalent portfolio analyses are cached for a bounded period.
- Runtime state is stored outside the application pods.
- Microsoft Foundry calls use workload identity and bounded concurrency.
- Application Insights records request, dependency, exception, and custom
  opening-bell metrics.

## Release-review questions

1. Does the deployed state meet the availability and scaling requirements?
2. Are Foundry model quota and request concurrency appropriate for the target?
3. Can runtime state survive pod scaling and replacement?
4. Do telemetry and load-test evidence support the stated capacity?

## Known release deviation

The hackathon deployment intentionally represents an early release with one
AKS node, one application replica, synchronous agent calls, and in-process
state. The Will It Scale? investigation should detect and explain this drift.
