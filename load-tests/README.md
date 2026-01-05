# Load tests

Locust tests for MCP tool latency and throughput.

## Run

```bash
locust -f locustfile.py --host http://localhost:8080
```

Environment variables:

- `MCP_CLIENT_JWT`
- `GRAPH_SESSION_ID`
