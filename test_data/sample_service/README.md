# Sample Service Investigation Fixture

This fixture represents an order service. Its target workload and reliability goals are
provided interactively when an assessment runs.

Primary concern: the database may become a bottleneck under peak traffic.

Evidence available to investigators:

- `app.py`: application request path and database access pattern.
- `kubernetes/deployment.yaml`: a single replica, very high CPU and memory requests with no limits, CPU-based autoscaling capped at one replica, and a pod disruption budget requiring one available pod.

Potential investigation questions:

- Is a database connection created for every request?
- Does the deployment have enough replicas and resource capacity?
- Is CPU-based autoscaling sufficient for database-bound work?
- Can the cluster schedule a pod requesting 8 CPUs and 32 GiB of memory?
- Does the single-replica PDB prevent voluntary disruption and reduce maintenance availability?
- What runtime telemetry would confirm or contradict the database concern?
