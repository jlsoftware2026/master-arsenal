# ADR-0001: Windows-first MALE distribution architecture

- **Status:** Accepted — self-contained Windows package approved; Windows 10 x64 and Windows 11 x64 support approved in principle, subject to release validation
- **Date:** 2026-11-18
- **Scope:** Phase 4 distribution foundation
- **Target branch:** `feature/phase-4-distribution-foundation`
- **Supported platform target:** Windows 10 22H2 x64 and Windows 11 x64, subject to clean-machine compatibility validation

## Context

MASTER ARSENAL is currently a Python application with the Binance Data Engine, Local Engine, and PDF Report Engine. The Phase 4 user-facing goal is a single-download Windows application that starts MALE on a clean PC without requiring preinstalled Java, Python, pip, or manual PATH configuration.

A JAR alone cannot meet this requirement: a JVM must already be running before Java code inside the JAR can execute. The user approved replacing the literal single-JAR download requirement with one self-contained Windows EXE/installer/application package that bundles the required runtimes. The existing JAR may remain an internal component, but it is not the user-facing launcher.

The developer's current machine has Java and Python installed. Those installations are useful for development and testing, but must not be treated as end-user prerequisites.

The application is an internet-connected research tool. Live market research, public-provider acquisition, current market snapshots, and update checks require network connectivity. The user explicitly confirmed that the product is not intended to perform live research without internet access. This does not mean the installer should download or install runtimes dynamically: the selected package should bundle its pinned runtimes and dependencies so the application does not rely on a separate Java/Python installation or pip-based first-run provisioning.

## Decision

Adopt a **self-contained Windows x64 application package** as the user-facing Phase 4 deliverable, targeting both Windows 10 22H2 x64 and Windows 11 x64.

The package must:
- Be distributed as one user-downloadable Windows installer/EXE or self-contained application package.
- Bundle a supported Java 21 x64 runtime and a private, pinned Windows x64 CPython runtime plus its complete prebuilt dependency bundle.
- Launch MALE without requiring users to install Java, Python, pip, or configure PATH.
- Keep the existing JAR, if retained, internal to the package.
- Keep the Python runtime and third-party dependencies isolated from system installations.
- Verify runtime and dependency artifacts before extraction or execution.
- Preserve reports, evidence, settings, and logs across application upgrades.
- Retain the existing read-only, pre-investment, no-trading, and no-credential-storage boundaries.
- Require internet connectivity for live market-data acquisition and other workflows that depend on external providers; show a clear, actionable network diagnostic when connectivity is unavailable.
- Avoid mandatory runtime downloads or pip installation during first launch.

This approval resolves the user-facing artifact and target-OS decisions. It does not approve an untested implementation, select exact runtime patch builds, or waive the technical, security, licensing, CI, and clean-machine validation gates below.

## Decision drivers

1. Provide a zero-prerequisite Windows user experience: no preinstalled Java, Python, pip, or manual PATH configuration.
2. Support both Windows 10 22H2 x64 and Windows 11 x64, verified on clean environments.
3. Preserve the existing Java/Python development workflow without making developer-machine installations runtime dependencies.
4. Keep Java, Python, and application dependencies private to the application package or managed runtime.
5. Pin every runtime and dependency artifact and verify SHA-256 (and publisher signatures where available) before use.
6. Keep persistent reports, evidence, settings, and logs outside replaceable application/runtime directories.
7. Make internet dependency explicit for live research, while keeping bundled runtime startup independent of pip or ad-hoc runtime downloads.
8. Preserve the existing read-only, no-trading, no-credential-storage, pre-investment boundaries.
9. Avoid administrator privileges unless a separately approved requirement makes them unavoidable.

## Options considered

### A. Self-contained Windows EXE/installer with bundled Java and Python — selected

A native Windows launcher/installer or self-contained Windows application package is the user-facing entry point. It includes a supported Java runtime and a private Windows x64 Python runtime/dependency bundle, verifies their integrity, and starts the MALE application. The existing JAR may be bundled internally where useful.

**Advantages**
- Meets the clean-PC requirement without user-managed Java or Python installations.
- Provides one straightforward Windows download and launch experience.
- Keeps Python isolated from system Python installations and PATH.
- Allows runtime and application upgrades to be staged and verified before activation.
- Fits the existing Python-first architecture while retaining the option to use the JAR internally.

**Costs / risks**
- Requires a Windows-specific packaging and release pipeline.
- Increases package size because supported runtimes and dependencies are bundled.
- Requires careful runtime licensing, provenance, integrity verification, and update design.
- Must be tested on clean Windows 10 and Windows 11 machines, not only the developer's configured PC.
- Live market-data and provider-dependent workflows require internet access; unavailable connectivity must be reported, not silently treated as valid market data.

### B. Executable JAR with Java prerequisite — rejected for Phase 4 delivery

This option distributes a JAR and requires a compatible Java runtime to be installed on the target PC.

**Reason for rejection**
- It cannot launch on a clean PC without Java and therefore violates the approved zero-prerequisite requirement.
- A JAR cannot install or start the JVM needed to execute itself.
- It would shift runtime installation and troubleshooting to the end user.

### C. Ask the user to install Java and/or Python and dependencies — rejected

This contradicts the Phase 4 goal of removing manual runtime, virtual-environment, pip, and PATH setup.

## Implementation direction

- The user downloads and launches one Windows package; neither Java nor Python needs to be installed manually.
- Bundle a supported Java 21 x64 runtime and a private, pinned Windows x64 CPython runtime plus a complete prebuilt dependency bundle.
- Do not invoke pip on the user's machine.
- Build the Python runtime/dependency bundle in controlled Windows CI. Include a machine-readable lock/manifest with exact versions, artifact origins, SHA-256 digests, and build provenance.
- Verify all downloaded or bundled artifacts before extraction or execution. Fail closed on digest mismatch, unexpected archive members, path traversal, or unsupported platform.
- Install into versioned application directories and activate only after health checks pass.
- Store persistent user data separately (initial proposal: `%LOCALAPPDATA%\\MASTER-ARSENAL\\`), with reports, evidence, settings, and logs preserved across upgrades.
- Never write secrets or user account exports into the Git repository or application package.
- Keep rollback to the previous known-good runtime/application version until the new version passes startup and smoke checks.
- Treat network connectivity as a required capability for live market-data acquisition and provider-dependent research. Detect network/provider failures, expose source-specific diagnostics, and never convert unavailable or stale data into a successful live-market result.
- The installer/package should contain the runtime and dependency bundle. A first-run network connection may be needed for live market workflows, not to compensate for missing Java/Python installations.

## Runtime and dependency packaging notes

The official Python Windows documentation describes the embeddable distribution as isolated and intended to be embedded in another application. It does not include pip, and its documentation recommends treating third-party packages as part of the application. Therefore, the proposed design uses a prebuilt, versioned dependency bundle rather than depending on pip at first launch.

The exact CPython patch version, Java vendor/build, dependency lock, and bundle layout are not fixed in this ADR until the Windows CI prototype demonstrates compatibility with the repository's complete dependency graph. Runtime selection must also pass licensing and redistribution review.

## Security and data-safety requirements

- HTTPS-only artifact retrieval from explicitly allowlisted release origins.
- SHA-256 verification against a reviewed release manifest; authenticate the manifest through the trusted release/package-signing process.
- Verify publisher signatures when the selected runtime vendor provides them.
- Reject archive traversal, symlink escapes, unexpected executable payloads, and writes outside managed directories.
- No shell command construction from job input; invoke only fixed executable paths with argument arrays.
- No administrator privileges unless a separately approved requirement makes them unavoidable.
- Atomic staging and activation; preserve the previous working version until the new version passes health checks.
- No automatic trading, order placement, exchange-account access, API-key collection, or credential storage.

## Platform contract

- **Supported target operating systems:** Windows 10 22H2 x64 and Windows 11 x64.
- **Validation requirement:** clean-machine installation, launch, upgrade, and smoke tests on both OS families. If a specific Windows edition/build fails, document the limitation rather than implying universal compatibility.
- **Not in Phase 4 acceptance:** macOS, Linux, ARM64, and 32-bit Windows.
- **Java runtime:** bundled Java 21 x64 runtime; exact vendor/build to be selected after compatibility and licensing review.
- **Python runtime:** private CPython Windows x64 runtime/embeddable bundle; exact patch release pinned at release time.
- Windows 10 support must be evaluated against its OS lifecycle and applicable servicing/security-update status. The application must not imply that installing MALE restores operating-system security support.

## Required prototype and validation

1. Build the proposed Windows package on controlled Windows CI.
2. Prove the package starts on clean Windows 10 22H2 x64 and Windows 11 x64 machines with neither Java nor Python installed.
3. Prove the package launches MALE using only its bundled Java/Python runtimes and dependency bundle.
4. Prove a harmless read-only health-check job completes and produces expected diagnostics/artifacts without requiring live market-provider access.
5. Prove live market-data workflows succeed with internet connectivity and fail clearly, safely, and without fabricating data when connectivity/provider access is unavailable.
6. Prove a failed download, checksum mismatch, interrupted extraction, or failed startup leaves the previous installation and persistent user data intact.
7. Prove an upgrade preserves reports, evidence manifests, settings, and logs.
8. Prove unsupported OS/architecture and insufficient disk-space cases fail clearly and safely.
9. Record exact artifact hashes, runtime versions, licensing notices, and provenance in a release manifest.
10. Test install, launch, upgrade, uninstall, and data-retention behavior on clean Windows environments for both supported OS targets.

## Remaining decisions

No additional user decision is required to include Windows 10 22H2 x64 and Windows 11 x64 as Phase 4 target platforms or to require internet for live market research. The exact supported Windows builds/editions, runtime versions, installer technology, and any provider-specific network requirements remain implementation and validation details to be resolved through the prototype and release gates.

## Consequences

The user-facing distribution contract is approved: Phase 4 targets one self-contained Windows EXE/installer/package bundling Java and Python, with Windows 10 22H2 x64 and Windows 11 x64 as supported targets subject to clean-machine validation. Live market research requires internet connectivity; the runtime bundle itself must not depend on end users installing Java, Python, or pip.

Implementation may proceed on the Phase 4 branch, subject to the technical and security gates in this ADR.

This is a release milestone, not the final phase of MASTER ARSENAL. Future enhancements, additional releases, and possible macOS support remain possible. The current pre-investment, read-only scope remains unchanged; full portfolio accounting, transaction-history ingestion, OpenJarvis integration, and planned Pro upgrades remain future roadmap items.
