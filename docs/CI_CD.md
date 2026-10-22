# Verification and deployment

`.github/workflows/ci.yml` runs on pushes, pull requests, and manual requests.
Python 3.11 installs all four agent requirements, executes the offline regression
suite, and compiles agent sources. A separate matrix builds all four Python
containers and the pinned upstream toolbox image with their actual build contexts. A failed test or container build
fails CI. No API key or running cloud service is required for the offline suite.

Run locally from the repository root:

```sh
python -m pip install -r vigil-system/transaction_monitor_agent/requirements.txt -r vigil-system/orchestrator_agent/requirements.txt -r vigil-system/investigation_agent/requirements.txt -r vigil-system/actuator_agent/requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q vigil-system
```

## GKE delivery

`deploy.yml` is manual and reruns CI for the selected revision before entering
the GitHub `production` environment. Configure required reviewers and restrict
that environment to your protected release branch. GitHub OIDC exchanges a
short-lived identity for a Google service account; no service-account JSON key
is stored. Bind trust to your repository and production environment.

Set these production environment variables:

- `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`
- `GCP_PROJECT_ID`, `GCP_REGION`, `GCP_ARTIFACT_REPOSITORY`
- `GKE_CLUSTER`, `GKE_LOCATION`, `K8S_NAMESPACE`
- `CLOUD_DEPLOYMENT_ENABLED=true` only after approved account/credits configuration.

The cloud gate defaults to disabled. No workflow guarantees zero billing; do not
enable it before the account owner confirms sufficient credits and billing controls.

Provision the cluster, Artifact Registry repository, Bank of Anthos, toolbox,
Gemini Kubernetes Secret, services, and four agent deployments first. The
workflow applies the monitor PVC and deployment volume/state-path configuration
using the freshly published revision image. Ensure the cluster has a default
storage class or bind the PVC to suitable pre-provisioned storage.
The service account needs registry push access, cluster credential access, and
namespace-scoped deployment update rights. This workflow only updates existing
agent images; it does not apply the upstream sample manifests with their
hardcoded cloud project and sample database credentials.

Images use the Git commit SHA. All five images publish before rollout begins.
Before rolling agents, deployment applies toolbox configuration and the
idempotent account-lock migration Job, waits for migration completion, and
restarts the toolbox to load its configuration. Namespace RBAC therefore also
needs ConfigMap/Job apply/read and toolbox deployment restart rights. Migration
failure blocks rollout. Use a new versioned Job name for future migrations;
a completed v1 Job is intentionally not rerun on every release.
Each rollout waits up to five minutes. Multi-service changes are not atomic;
on failure investigate logs and restore the previous known-good SHA using
`kubectl set image` followed by `kubectl rollout status`. The toolbox image is built from the pinned official 0.16.0 image and published
with the same Git SHA; its command is applied with its deployment manifest.

CI configuration is prepared locally. A workflow file is not proof that GitHub
Actions ran or that GKE was deployed. A live public URL requires a configured
Ingress/service and a successful smoke test of that exact deployment.

## PostgreSQL contract job

CI starts a disposable PostgreSQL 17 service and checks out the pinned Bank of
Anthos submodule recursively. The contract test loads the real ledger schema,
applies the migration twice, confirms that a locked local sender is rejected,
and confirms other senders/external routes remain valid. It uses an isolated
random schema and removes it afterwards. The service credentials are disposable
CI-only values. Locally this test is skipped unless `TEST_POSTGRES_DSN` points
to an explicitly disposable PostgreSQL database and psycopg 3.2.6 is installed.

## Local container validation, 22 October 2026

All four agent images built successfully on Linux ARM64 in the isolated
`colima-vigil-ci` Docker context, using the same repository/directory build
contexts declared in CI. Module imports passed inside each resulting image.
The monitor was rebuilt after its final acknowledgement handling change.

| Image | Local image ID |
| --- | --- |
| transaction monitor | `819230f5477f` |
| orchestrator | `bedf93151f04` |
| investigation | `135793083a3b` |
| actuator | `29536a19c1db` |

The Linux container regression run collected 24 tests: 23 passed and one
PostgreSQL contract test was explicitly skipped because that particular run
had no `TEST_POSTGRES_DSN`. The dedicated PostgreSQL CI job supplies it; the
separate real-database verification is recorded in the project validation
report. Local ARM64 builds do not establish that the GitHub-hosted AMD64 build
has run. No image was pushed and no cloud deployment occurred during these
checks. An initial base-image download failed with unexpected EOF and succeeded
on retry; final image builds exited successfully.
