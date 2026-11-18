# Phase 4 — Windows distribution and release foundation

**Status:** In progress — distribution architecture approved  
**Base branch:** `develop`  
**Working branch:** `feature/phase-4-distribution-foundation`  
**Starting point:** Phase 3 merge commit `dec05d6040c10ad75faf3cedf024f6f335bbd4f8`  
**Architecture decision:** `docs/adr/0001-windows-first-distribution.md`

## Purpose

Turn the existing Python-first MASTER ARSENAL / MASTER ARSENAL Local Engine (MALE) into a dependable Windows-first user-facing application distributed as one self-contained Windows EXE/installer/application package. The package must bundle the required Java and Python runtimes so an end user does not need to install Java, Python, pip, create a virtual environment, or configure PATH manually.

The existing executable JAR may remain an internal component, but it is not the user-facing launch artifact.

Phase 4 is a release-readiness milestone, not the end of MASTER ARSENAL development. MALE must remain modular and upgradeable after this phase.

## Scope

### P4.1 — Technical design and platform contract

- Specify supported Windows operating systems and CPU architectures.
- Implement the accepted self-contained Windows package architecture recorded in ADR-0001.
- Select exact Java/Python runtime builds and dependency pins after compatibility, security, and licensing review.
- Define runtime and dependency pinning, artifact provenance, checksum/signature verification, and failure behavior.
- Define online/offline installation behavior and network failure handling.
- Define managed application directories, persistent user-data directories, logs, reports, evidence, settings, and upgrade/rollback boundaries.

### P4.2 — Self-contained Windows launcher/package

- Deliver one user-downloadable Windows EXE/installer or self-contained application package.
- Bundle a supported Java 21 x64 runtime and a private, pinned Windows x64 CPython runtime with its complete prebuilt dependency bundle.
- Launch MALE without requiring end users to install Java, Python, pip, or configure PATH.
- Detect OS, architecture, disk capacity, and runtime/package integrity before launch.
- Verify all runtime and dependency artifacts before extraction or execution; fail closed on checksum/signature mismatch.
- Launch MALE only after runtime, dependency, and application integrity checks pass.
- Never execute caller-supplied shell commands or arbitrary code.

### P4.3 — Managed data and safe upgrades

- Keep application binaries and bundled runtimes separate from persistent user data.
- Preserve reports, evidence manifests, settings, and logs across upgrades.
- Make upgrades repeatable and prevent silent dependency downgrades.
- Define backup/restore and rollback behavior before enabling destructive migrations.
- Keep optional user-supplied account-export files local-only and outside version control; their absence must not block pre-investment research workflows.

### P4.4 — Diagnostics and operational reliability

- Provide actionable diagnostics for unsupported platforms, insufficient disk space, network failures, integrity failures, and startup errors.
- Record version and runtime/dependency provenance in diagnostics without exposing secrets or private account data.
- Make startup and upgrade operations idempotent where practical.
- Ensure failures do not corrupt existing user data or leave the application in a falsely healthy state.

### P4.5 — Integration, security, and release validation

- Add deterministic tests for bootstrap decisions, platform detection, artifact verification, dependency pinning, data-directory isolation, upgrades, rollback, and failure paths.
- Add Windows CI for the declared supported OS/architecture matrix.
- Add an end-to-end smoke test that starts the packaged application on a clean Windows machine with neither Java nor Python installed and runs a harmless read-only MALE workflow.
- Publish a release manifest with artifact hashes, runtime/dependency versions, provenance, supported platforms, and known limitations.

## Explicit exclusions and preserved boundaries

- **No automated trading, order placement, or private exchange-account access.**
- **No API-key collection or storage.**
- Full portfolio accounting, PnL/cost-basis reconciliation, and transaction-history CSV ingestion are not Phase 4 acceptance requirements. The current project remains pre-investment research and decision support. No CSV is expected or required for the user's current workflow; missing account data is not an error and must never be interpreted as a zero balance.
- The optional local account-export parser remains optional and local-only.
- OpenJarvis integration and any planned Pro upgrades remain future roadmap items.
- macOS support is a possible future enhancement, not a Phase 4 acceptance requirement.
- Phase 4 does not freeze the MALE; subsequent improvements and additional phases remain expected.

## Delivery sequence and gates

1. **Design gate:** ADR-0001 records the approved self-contained Windows distribution contract. Exact runtime versions, licensing, and installation behavior must be settled before release packaging is finalized.
2. **Packaging prototype gate:** build the smallest Windows package with bundled runtimes; prove artifact verification and clean-machine startup.
3. **Data-safety gate:** prove persistent-data isolation, repeatable upgrades, and rollback/failure safety.
4. **Release gate:** pass the supported-Windows CI matrix and clean-environment end-to-end smoke tests; publish a verifiable release manifest.

Each gate must have explicit tests and evidence. A passing offline unit suite alone does not establish clean-machine launchability or live-provider availability.

## Acceptance criteria

- A single self-contained Windows EXE/installer/application package is the user's download and launch entry point; the existing JAR may be included internally.
- On each declared supported Windows x64 environment, a clean machine can launch MALE without a manually installed Java or Python runtime, pip, or manual PATH setup.
- Every bundled or provisioned runtime/dependency artifact is pinned and integrity-verified before execution.
- Reports, evidence, settings, and logs survive application upgrades.
- Upgrade, rollback, and startup failures are diagnosable and do not silently damage persistent user data.
- The packaged application passes the Windows automated tests and a clean-machine end-to-end smoke test.
- The release manifest identifies exact artifact hashes, runtime/dependency versions, provenance, supported platforms, and limitations.
- All existing pre-investment, read-only, evidence-provenance, and no-fabrication safeguards remain intact.

## Initial implementation status

Phase 4 architecture approval is recorded in ADR-0001. The accepted user-facing artifact is a self-contained Windows EXE/installer/application package bundling Java and Python. This plan records the revised delivery contract; it does not claim that packaging, runtime bundling, signing, or deployment has already been implemented. Those are the implementation and validation work remaining in Phase 4.
