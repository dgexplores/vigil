# Dependency review — 22 October 2026

Google ADK was upgraded from 1.14.1 to 1.39.1. FastAPI 0.140.0 and Starlette
1.9.0 satisfy ADK's dependency contracts; a newer FastAPI currently requires an
OpenTelemetry version beyond ADK's supported upper bound. Legacy A2A SDK 0.3.10
is retained for verified protocol compatibility. Fully pinned universal service
requirements record the resolved packages. The monitor has its own smaller lock.

The monitor dependency audit reports zero known vulnerabilities. The ADK service
audit reports one remaining advisory: **CVE-2026-114603**, an OpenTelemetry
tracestate-header parser denial of service. ADK caps `opentelemetry-api` at
1.41.1, below the reported fix in 1.45.1. The dependency advisory is not claimed
fixed.

Mitigation: all three ADK service entry points forcibly set `OTEL_PROPAGATORS`
to `none` before importing A2A or ADK. Untrusted remote trace context is not
extracted. A regression test supplies valid traceparent and an oversized crafted
tracestate and checks that no remote span context propagates. Local spans can
still be recorded. Do not add an independent remote header parser or remove this
policy until ADK permits the patched dependency and the image/endpoint suite has
been repeated. This trades distributed incoming trace correlation for closing
the affected input path.

CI audits the full lock and ignores only this named, documented mitigated
advisory. All other findings fail the job. Twenty-five tests pass with real
PostgreSQL, including the propagation policy. This review does not constitute
production banking certification or live Gemini/GKE verification.
