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
- Workspace paths are resolved and checked against the configured root before directory creation; symlink escapes are rejected.
- Job state files are written atomically and lifecycle transitions use same-workspace atomic renames.
- Duplicate job identifiers are rejected.
- Lifecycle operations use per-workspace thread locks and native OS file locks (POSIX `flock`, Windows `msvcrt.locking`).
- Tests cover competing threads and separate spawned processes for duplicate submissions and job claims.
- CI exercises Python 3.11 and 3.12 on Ubuntu and Windows.

This is a development foundation, not a production-certified security boundary. Stronger Windows ACL policy, recovery of jobs left in the running state after abrupt worker termination, signed assistant-origin requests, and broader filesystem/platform hardening remain future work.

## Verification status

The GitHub Actions matrix is the authoritative cross-platform check for this branch. A green run validates the Binance and Local Engine unit suites on each configured operating-system/Python combination. Symlink tests may be skipped on Windows environments where directory symlink creation is not permitted by the runner policy; the implementation still performs the containment check.
