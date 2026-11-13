# MASTER ARSENAL Local Engine — Phase 2 Foundation

## Scope

Introduces the versioned job protocol, local workspace layout, job lifecycle manager, explicit approval gate, allowlisted dispatcher, and CLI diagnostics. Binance report jobs, PDF generation, MCP adapters, and Windows packaging are not included in this phase.

## Source-checkout usage

```bash
python -m pip install -e .
ma-local --workspace ./MASTER-ARSENAL-LOCAL init
ma-local --workspace ./MASTER-ARSENAL-LOCAL new-job engine.health_check --output health-check-job.json
ma-local --workspace ./MASTER-ARSENAL-LOCAL submit health-check-job.json
ma-local --workspace ./MASTER-ARSENAL-LOCAL validate JOB_UUID
ma-local --workspace ./MASTER-ARSENAL-LOCAL approve JOB_UUID
ma-local --workspace ./MASTER-ARSENAL-LOCAL run JOB_UUID
ma-local --workspace ./MASTER-ARSENAL-LOCAL status JOB_UUID
```

Approval is a separate user action. A job cannot run until validated and explicitly approved.

## Protocol

The protocol identifier is `ma.job/v1`. It rejects unknown top-level fields, unsupported job types, non-UTC timestamps, absolute output paths, path traversal, malformed UUIDs, and invalid approval flags. Only predefined job identifiers are accepted. The dispatcher never evaluates job-supplied code or shell commands.

## Implemented handler

- `engine.health_check`: reports engine, runtime, platform, and workspace diagnostics.

Market reports, skills audit, and snapshot validation are reserved protocol identifiers but have no execution handlers in this phase. If submitted and approved, they fail explicitly as not implemented.

## Security notes

- No inbound network listener.
- No subprocess or shell execution.
- No Binance credentials or account endpoints.
- Workspace paths are resolved and checked against the configured root.
- Job state files are written atomically.
- Duplicate job identifiers are rejected.

This is a development foundation, not a production-certified security boundary. Concurrent multi-process execution, stronger Windows ACL handling, crash recovery, and signed assistant-origin requests remain future validation items.
