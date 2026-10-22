# Deployment readiness and route guide

The local implementation is verified with 25 tests, including real PostgreSQL
ledger enforcement. Gemini responses are stubbed in offline tests. A live GKE
release is not claimed; one ADK-constrained telemetry advisory is mitigated and
tracked in `DEPENDENCY_REVIEW.md`.

## Reproduce first

With Python 3.11 and Make installed, run `make install` then `make test`.
Initialize the Bank of Anthos submodule for database contracts. Set
`TEST_POSTGRES_DSN` only for a disposable PostgreSQL instance, following
`LOCAL_VERIFICATION.md`. Without it, that test is explicitly skipped.

## Service routing

| Service | Internal Kubernetes address | Routes |
|---|---|---|
| Orchestrator | `http://orchestrator-agent-service` | `POST /`, `POST /a2a/send-message`, `GET /health` |
| Investigation | `http://investigation-agent-service` | A2A routes plus `POST /investigate`, `GET /health` |
| Actuator | `http://actuator-agent-service` | A2A routes plus `POST /execute`, `GET /health` |
| Toolbox | `http://genal-toolbox-service` | Parameterized PostgreSQL tools |
| Transaction monitor | Background worker | No user-facing web route |

Services listen on container port 8000; Kubernetes services map port 80 where
applicable. For a local operator health check on an approved cluster use
`kubectl port-forward service/orchestrator-agent-service 8000:80` and request
`http://localhost:8000/health`. An uninitialized service returns 503. Internal
A2A routes are service-to-service demo contracts and have no public-user login;
keep them private to the cluster and apply suitable network policy/identity
controls before exposing any endpoint. Bank of Anthos supplies the banking UI.

## Cloud prerequisites and order

1. Obtain a billing-enabled GCP project with an explicitly approved budget, a GKE cluster, Artifact Registry, compatible Bank of Anthos databases and namespace storage.
2. Configure database connections for the actual demo environment; inherited sample database passwords and image names are not production credentials.
3. Create the Gemini Kubernetes Secret from the example, using your own key outside Git.
4. Deploy toolbox configuration, then the ledger migration Job and wait for completion. The lock trigger must exist before starting enforcement.
5. Deploy all four agents and services plus the single-monitor PVC, using your own image references. Review component build contexts in CI. Keep one monitor replica with the supplied Recreate strategy.
6. Configure the repository's `production` environment and repository-scoped GCP OIDC trust using `CI_CD.md`. Keep `CLOUD_DEPLOYMENT_ENABLED` absent/false while spending authorization is ₹0.
7. After approved deployment, submit synthetic below/above-threshold transactions, confirm investigation, acknowledge delivery, confirm the actual lock row and blocked future local outgoing transfer. Check failure/retry behavior, restarts and service readiness.

This pipeline updates an existing cluster; it does not provision one or guarantee
zero charges. Service rollouts are not atomic. Keep a known-good image SHA and
review logs/rollback steps. Only record live recruiter links after the deployed
revision passes the above checks. No free substitute for GKE or Gemini was added.
