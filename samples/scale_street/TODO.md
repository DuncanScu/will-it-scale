# Scale Street remaining work

Status as of September 16, 2026.

## Blocked on AKS provisioning

The retained cluster in North Central US remains in `Creating`. Its
control plane and system node pool remain in `Creating`; it has an OIDC issuer
but no kubelet identity or managed node resources.

When the cluster reaches `Succeeded`:

1. Capture the kubelet identity object ID.
2. Assign the kubelet identity `AcrPull` on the deployed ACR.
3. Retrieve cluster credentials with `az aks get-credentials`.
4. Render and apply the constrained Kubernetes Deployment, service account,
   and LoadBalancer Service.
5. Wait for the pod rollout and external IP.
6. Run health, readiness, Foundry advice, opening-bell, and load tests against
   the AKS endpoint.
7. Compare the AKS results with the ACI baseline.

The `scale-street-aks` federated credential already references racer 3's OIDC
issuer and the Linux `kubectl` client is installed.

## Operational follow-up

1. Escalate the stuck create through FDPO or AKS support if the cluster remains
   in `Creating`. Include the deployment operations, correlation IDs, regions,
   timestamps, and archived diagnostics.
2. After AKS validation, decide whether to retain either ACI deployment.
3. Downgrade or remove ACR Premium only after ACI managed-identity image pulls
   are no longer needed.
4. Push `DemoWebApp` and open a pull request only after explicit approval.
