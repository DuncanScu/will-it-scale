# Sample Service Investigation Fixture

This fixture represents an order service. Its target workload and reliability goals are
provided interactively when an assessment runs.

Primary concern: the database may become a bottleneck under peak traffic.

The request path intentionally contains scalability problems for an investigation agent
to identify: new database connections are opened for order and customer queries, each
order triggers a customer lookup (an N+1 query pattern), and related orders are counted
by comparing every order to every other order (O(n^2) work per request).

## Run the API

Install the fixture dependencies and start the service:

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

The API is available at `http://127.0.0.1:8000`, with interactive OpenAPI docs at
`http://127.0.0.1:8000/docs`. The order endpoint is `GET /orders`.

Evidence available to investigators:

- `app.py`: application request path and database access pattern.
- `kubernetes/deployment.yaml`: a single replica, very high CPU and memory requests with no limits, CPU-based autoscaling capped at one replica, and a pod disruption budget requiring one available pod.

Potential investigation questions:

- Is a database connection created for every request?
- Does `GET /orders` make a database query for every returned order?
- Does order enrichment perform O(n^2) work as result sets grow?
- Does the deployment have enough replicas and resource capacity?
- Is CPU-based autoscaling sufficient for database-bound work?
- Can the cluster schedule a pod requesting 8 CPUs and 32 GiB of memory?
- Does the single-replica PDB prevent voluntary disruption and reduce maintenance availability?
- What runtime telemetry would confirm or contradict the database concern?
