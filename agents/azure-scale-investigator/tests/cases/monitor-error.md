# Azure Monitor Failure-Containment Test

## Scenario

Azure Monitor returns:

```text
HTTP 400: Metric ClientErrors does not support the requested aggregation,
interval, or dimension.
```

Other Azure resources remain accessible.

## Expected behavior

The agent must:

1. Keep the assessment running.
2. Query metric definitions for the affected resource.
3. Retry once with a supported metric configuration when one is available.
4. Never repeat the same invalid request.
5. Mark the metric Unknown if the corrected request fails.
6. Continue checking independent resources.
7. Include a Tool execution notes record containing:
   - phase
   - `azure-mcp/monitor`
   - affected resource
   - status code `400`
   - sanitized error
   - recovery performed
   - confidence impact
8. Avoid converting missing metric evidence into a healthy conclusion.

## Passing outcome

The final assessment is produced with reduced confidence for the affected
metric, while configuration, inventory, health, quota, and other available
telemetry findings remain present.
