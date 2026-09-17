# Scale Street remaining work

Status as of September 17, 2026.

## AKS deployment completed

The retained `scalestreet-aks-racer3` cluster in North Central US is running.
The deployment required registration of the
`Microsoft.Network/AllowBringYourOwnPublicIpAddress` subscription feature.

Completed validation:

1. Assigned the AKS kubelet identity `AcrPull` on the deployed ACR.
2. Built and pushed `scale-street:latest`.
3. Applied the constrained Kubernetes Deployment, service account, and
   LoadBalancer Service.
4. Added explicit requests of 200m CPU and 256Mi memory so the application can
   schedule alongside the system workloads on the single constrained node.
5. Verified `/health` and `/ready`.
6. Verified a Foundry-backed advice request completed successfully.
7. Ran the documented 250-customer, concurrency-40 client load test. The client
   timed out after starting 43 requests; 5 completed and 38 failed, with
   observed p95 latency of 134.1 seconds.
8. Ran the built-in opening-bell test with 20 customers and concurrency 5. It
   completed with 8 successes and 12 failures, with p95 latency of 133.3
   seconds. Pod logs confirmed the failures were Foundry model HTTP 429 rate
   limits.
9. Deleted both Azure Container Instances fallbacks after AKS validation.
10. Downgraded ACR from Premium to Basic and verified a fresh AKS image pull.

## Operational follow-up

1. Compare the AKS results with any archived ACI baseline data.
2. Decide whether to increase Foundry capacity or add application
   back-pressure, retries, and bounded timeouts before larger load tests.
3. Add application telemetry instrumentation. The Application Insights and
   Log Analytics resources exist, but no application request records were
   available for this validation run; pod logs provided the failure evidence.
4. Push `DemoWebApp` and open a pull request only after explicit approval.
