# Phase 4 — Windows distribution and release foundation

**Status:** In progress — distribution architecture approved  
**Base branch:** `develop`  
**Working branch:** `feature/phase-4-distribution-foundation`  
**Starting point:** Phase 3 merge commit `dec05d6040c10ad75faf3cedf024f6f335bbd4f8`  
**Architecture decision:** `docs/adr/0001-windows-first-distribution.md`

## Purpose

Turn the existing Python-first MASTER ARSENAL / MASTER ARSENAL Local Engine (MALE) into a dependable Windows-first user-facing application distributed as one self-contained Windows EXE/installer/application package. The package must bundle the Python runtime and all required application dependencies so an end user does not need to install Java, Python, pip, create a virtual environment, or configure PATH manually.

The current repository contains no Java source tree or JAR dependency; the package therefore does not bundle an unused Java runtime or JAR. The existing Python-first engines are packaged as Windows executables.

Phase 4 targets Windows 10 22H2 x64 and Windows 11 x64, subject to clean-machine compatibility validation. Live market research and provider-dependent workflows require internet connectivity. The application must diagnose network/provider failures and must never fabricate or silently substitute missing live data.

Phase 4 is a release-readiness milestone, not the end of MASTER ARSENAL development. MALE must remain modular and upgradeable after this phase.

## Scope

### P4.1 — Technical design and platform contract

- Specify supported Windows operating systems and CPU architectures, targeting Windows 10 22H2 x64 and Windows 11 x64.
- Implement the accepted self-contained Windows package architecture recorded in ADR-0001.
- Select and pin the Python runtime, application dependencies, and packaging toolchain after compatibility, security, and licensing review. Revisit Java only if a Java component is introduced.
- Define runtime and dependency pinning, artifact provenance, checksum/signature verification, and failure behavior.
- Define network requirements for live data, provider timeouts, retry/backoff, and user-facing offline diagnostics.
- Define managed application directories, persistent user-data directories, logs, reports, evidence, settings, and upgrade/rollback boundaries.

### P4.2 — Self-contained Windows launcher/package

- Deliver one user-downloadable Windows EXE/installer or self-contained application package.
- Bundle the private Windows x64 CPython runtime and complete prebuilt dependency bundle inside the packaged executables.
- Launch MALE without requiring end users to install Python, pip, or configure PATH; Java is not a dependency of the current Python-only codebase.
- Detect OS, architecture, disk capacity, and runtime/package integrity before launch.
- Verify all runtime and dependency artifacts before extraction or execution; fail closed on checksum/signature mismatch.
- Launch MALE only after runtime, dependency, and application integrity checks pass.
- Never execute caller-supplied shell commands or arbitrary code.

### P4.3 — Managed data and safe upgrades

- Keep application binaries and the bundled Python runtime separate from persistent user data.
- Preserve reports, evidence manifests, settings, and logs across upgrades.
- Make upgrades repeatable and prevent silent dependency downgrades.
- Define backup/restore and rollback behavior before enabling destructive migrations.
- Keep optional user-supplied account-export files local-only and outside version control; their absence must not block pre-investment research workflows.

### P4.4 — Diagnostics and operational reliability

- Provide actionable diagnostics for unsupported platforms, insufficient disk space, network failures, provider outages, integrity failures, and startup errors.
- Record version and runtime/dependency provenance in diagnostics without exposing secrets or private account data.
- Make startup and upgrade operations idempotent where practical.
- Ensure failures do not corrupt existing user data or leave the application in a falsely healthy state.
- Distinguish local engine health from live-provider connectivity: an offline health check may pass while live market acquisition is unavailable.

### P4.5 — Integration, security, and release validation

- Add deterministic tests for bootstrap decisions, platform detection, artifact verification, dependency pinning, data-directory isolation, upgrades, rollback, and failure paths.
- Add Windows CI for Windows 10 22H2 x64 and Windows 11 x64 compatibility where runners permit; supplement hosted CI with clean-machine VM evidence when runner images do not match the exact supported baseline.
- Add an end-to-end smoke test that starts the packaged application on clean Windows machines with neither Java nor Python installed and runs a harmless read-only MALE workflow.
- Test live market-data acquisition with internet access and safe, explicit failure behavior without connectivity.
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

1. **Design gate:** ADR-0001 records the approved self-contained Windows distribution contract, Windows 10/11 targets, and internet requirements for live research. Exact runtime versions and licensing must be settled before release packaging is finalized.
2. **Packaging prototype gate:** build the Windows package with bundled runtimes; prove artifact verification and clean-machine startup on both target OS families.
3. **Data-safety gate:** prove persistent-data isolation, repeatable upgrades, and rollback/failure safety.
4. **Connectivity gate:** prove live market acquisition when connected and clear, safe behavior when offline or providers fail.
5. **Release gate:** pass the supported-Windows CI/VM matrix and clean-environment end-to-end smoke tests; publish a verifiable release manifest.

Each gate must have explicit tests and evidence. A passing offline unit suite alone does not establish clean-machine launchability or live-provider availability.

## Acceptance criteria

- A single self-contained Windows EXE installer is the user's download entry point; it installs the packaged Local Engine and Binance Engine executables with their private Python runtimes.
- On clean Windows 10 22H2 x64 and Windows 11 x64 environments, MALE launches without a manually installed Python runtime, pip, or manual PATH setup; no Java runtime is required by the current codebase.
- Every bundled or provisioned runtime/dependency artifact is pinned and integrity-verified before execution.
- Live market-data workflows require internet connectivity; network/provider failures are explicit and cannot result in fabricated or falsely complete data.
- Reports, evidence, settings, and logs survive application upgrades.
- Upgrade, rollback, and startup failures are diagnosable and do not silently damage persistent user data.
- The packaged application passes automated Windows tests and clean-machine end-to-end smoke tests for both target OS families.
- The release manifest identifies exact artifact hashes, runtime/dependency versions, provenance, supported platforms, and limitations.
- All existing pre-investment, read-only, evidence-provenance, and no-fabrication safeguards remain intact.

## Initial implementation status

Phase 4 architecture approval is recorded in ADR-0001. The accepted user-facing artifact is a self-contained Windows EXE/installer/application package bundling the Python runtime and dependencies, targeting Windows 10 22H2 x64 and Windows 11 x64. Live research requires internet connectivity. This plan records the revised delivery contract; it records the packaging prototype now under implementation; code signing, clean Windows 10 VM validation, upgrade/rollback certification, and production release remain outstanding. Those are the implementation and validation work remaining in Phase 4.
