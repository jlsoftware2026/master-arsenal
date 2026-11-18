# Phase 4 — Distribution and release foundation

**Status:** Initiated  
**Base branch:** `develop`  
**Working branch:** `feature/phase-4-distribution-foundation`  
**Starting point:** Phase 3 merge commit `dec05d6040c10ad75faf3cedf024f6f335bbd4f8`

## Purpose

Turn the existing Python-first MASTER ARSENAL / MASTER ARSENAL Local Engine (MALE) into a dependable user-facing application that can be launched from one downloadable executable JAR, without requiring the user to install Python, create a virtual environment, run pip, or configure PATH manually.

Phase 4 is a release-readiness milestone, not the end of MASTER ARSENAL development. The MALE must remain modular and upgradeable after this phase.

## Scope

### P4.1 — Technical design and platform contract

- Specify supported operating systems and CPU architectures.
- Evaluate the Java bootstrapper and runtime-provisioning options against the existing Python-first implementation.
- Define runtime and dependency pinning, artifact provenance, checksum/signature verification, and failure behavior.
- Define online/offline installation behavior and network failure handling.
- Define the managed application directory, user-data directory, logs, reports, evidence, settings, and upgrade/rollback boundaries.
- Record the selected design in an Architecture Decision Record (ADR) before implementing runtime, dependency, packaging, signing, or deployment changes.

### P4.2 — Single-JAR bootstrapper

- Deliver one user-downloadable executable JAR as the entry point.
- Detect OS, architecture, disk capacity, network access, and runtime prerequisites.
- Provision or locate only explicitly supported, pinned runtimes and dependencies.
- Verify downloaded artifacts before use; fail closed on checksum/signature mismatch.
- Launch the MALE only after runtime, dependency, and application integrity checks pass.
- Never execute caller-supplied shell commands or arbitrary code.

### P4.3 — Managed data and safe upgrades

- Keep application binaries separate from persistent user data.
- Preserve reports, evidence manifests, settings, and logs across upgrades.
- Make upgrades repeatable and prevent silent dependency downgrades.
- Define backup/restore and rollback behavior before enabling destructive migrations.
- Keep optional user-supplied account-export files local-only and outside version control; their absence must not block pre-investment research workflows.

### P4.4 — Diagnostics and operational reliability

- Provide actionable diagnostics for unsupported platforms, missing prerequisites, insufficient disk space, network failures, integrity failures, and startup errors.
- Record version and runtime/dependency provenance in diagnostics without exposing secrets or private account data.
- Make startup and upgrade operations idempotent where practical.
- Ensure failures do not corrupt existing user data or leave the application in a falsely healthy state.

### P4.5 — Integration, security, and release validation

- Add deterministic tests for bootstrap decisions, platform detection, artifact verification, dependency pinning, data-directory isolation, upgrades, rollback, and failure paths.
- Add cross-platform CI for the supported OS/architecture matrix.
- Add an end-to-end smoke test that starts the packaged application and runs a harmless read-only MALE workflow.
- Verify the resulting JAR can be launched on a clean supported environment without a preinstalled Python toolchain.
- Publish a release manifest with artifact hashes, version, supported platforms, and known limitations.

## Explicit exclusions and preserved boundaries

- **No automated trading, order placement, or private exchange-account access.**
- **No API-key collection or storage.**
- Full portfolio accounting, PnL/cost-basis reconciliation, and transaction-history CSV ingestion are not Phase 4 acceptance requirements. The current project remains pre-investment research and decision support. No CSV is expected or required for the user's current workflow; missing account data is not an error and must never be interpreted as a zero balance.
- The optional local account-export parser remains optional and local-only.
- OpenJarvis integration and any planned Pro upgrades remain future roadmap items.
- Phase 4 does not freeze the MALE; subsequent improvements and additional phases remain expected.

## Delivery sequence and gates

1. **Design gate:** complete the platform contract and ADR. Do not make runtime, dependency, packaging, signing, or deployment architecture changes before the ADR is reviewed and approved.
2. **Bootstrap gate:** implement the smallest secure executable-JAR bootstrap path and prove artifact verification and clean startup.
3. **Data-safety gate:** prove persistent-data isolation, repeatable upgrades, and rollback/failure safety.
4. **Release gate:** pass the supported-platform CI matrix and clean-environment end-to-end smoke tests; publish a verifiable release manifest.

Each gate must have explicit tests and evidence. A passing offline unit suite alone does not establish clean-machine launchability or live-provider availability.

## Acceptance criteria

- A single executable JAR is the user's download and launch entry point.
- On each declared supported platform, a clean environment can launch the MALE without a manually installed Python environment or manual pip/PATH setup.
- Every provisioned runtime/dependency artifact is pinned and integrity-verified before execution.
- Reports, evidence, settings, and logs survive application upgrades.
- Upgrade, rollback, and startup failures are diagnosable and do not silently damage persistent user data.
- The packaged application passes the cross-platform automated tests and a clean-environment end-to-end smoke test.
- The release manifest identifies exact artifact hashes, version, supported platforms, and limitations.
- All existing pre-investment, read-only, evidence-provenance, and no-fabrication safeguards remain intact.

## Initial implementation status

This document and the Phase 4 working branch establish the milestone. No runtime strategy, dependency set, installer, signing process, or deployment mechanism is selected or implemented yet. Those decisions are the first design deliverable and require review before implementation.
