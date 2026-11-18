# ADR-0001: Windows-first MALE distribution architecture

- **Status:** Proposed — requires Sensei's review and approval
- **Date:** 2026-11-18
- **Scope:** Phase 4 distribution foundation
- **Target branch:** `feature/phase-4-distribution-foundation`
- **Platform baseline:** Windows 10/11, x64 (provisional; Windows 10 support requires explicit validation)

## Context

MASTER ARSENAL is currently a Python application with the Binance Data Engine, Local Engine, and PDF Report Engine. The user-facing goal for Phase 4 is one downloadable executable JAR that starts MALE without requiring the user to install Python, create a virtual environment, run pip, or edit PATH.

The existing Phase 4 plan requires a design/ADR gate before changes to runtime, dependencies, packaging, signing, or deployment. This ADR is a proposal only; it does not authorize those implementation changes.

## Decision drivers

1. Preserve the requested single-JAR download and launch entry point.
2. Keep Python and all Python dependencies private to the application.
3. Support Windows x64 first; do not make macOS a Phase 4 acceptance requirement.
4. Pin every runtime and dependency artifact and verify SHA-256 (and publisher signatures where available) before use.
5. Keep persistent reports, evidence, settings, and logs outside replaceable application/runtime directories.
6. Preserve the existing read-only, no-trading, no-credential-storage, pre-investment boundaries.
7. Do not require pip, a user-managed Python installation, or manual PATH changes.

## Options considered

### A. Java executable JAR bootstrapper + managed private Python runtime

The JAR acts as the user-facing bootstrapper. It validates the host, creates an application-managed installation, downloads or reuses a pinned Windows x64 Python runtime bundle, verifies its digest, and starts the existing MALE entry point. The Python runtime and dependency bundle are installed under an application-owned versioned directory. User data remains in a separate stable data directory.

**Advantages**
- Preserves the requested JAR entry point.
- Keeps Python isolated from system Python installations and PATH.
- Allows runtime and application upgrades to be staged and verified before activation.
- Fits the existing Python-first architecture and minimizes changes to tested business logic.

**Costs / risks**
- A JAR requires a compatible Java runtime to start. A JAR cannot provision Java before the JVM has launched.
- The project must decide whether Java 21 x64 is a documented prerequisite or whether the deliverable requirement should change to a native Windows launcher/package.
- The Python embeddable distribution does not include pip. Its third-party packages should be treated as application-vendored content; a prebuilt, versioned dependency bundle is preferable to runtime pip installation.
- Initial setup requires network access unless a complete offline bundle is separately distributed.

### B. Native Windows package with bundled Java/Python runtimes

Use a Windows-native launcher/package (for example, a self-contained application image or installer) and include the required Java runtime and managed Python runtime.

**Advantages**
- Can avoid requiring Java to be installed by the user.
- Better native Windows launch and installation experience.

**Costs / risks**
- Does not satisfy the current single executable JAR deliverable literally.
- Produces a Windows-specific artifact and changes the user-facing distribution contract.
- Must be built and validated on Windows; macOS would require a separate package pipeline later.

### C. Ask the user to install Python and dependencies

Rejected. It contradicts the Phase 4 goal of removing manual Python, virtual-environment, pip, and PATH setup.

## Proposed direction

Proceed with **Option A**, subject to explicit approval of its Java prerequisite:

- The sole initial download remains the executable JAR.
- The JAR requires a supported Java 21 x64 runtime already installed on Windows. If it is absent or incompatible, the JAR must stop with a clear, actionable diagnostic; it must not attempt to execute an unverified installer.
- The JAR provisions a private, pinned Windows x64 Python runtime and a prebuilt dependency bundle. It does not invoke pip on the user's machine.
- Build the Python runtime/dependency bundle in controlled Windows CI. Include a machine-readable lock/manifest with exact versions, artifact URLs, SHA-256 digests, and build provenance.
- Verify all downloaded artifacts before extraction or execution. Fail closed on digest mismatch, unexpected archive members, path traversal, or unsupported platform.
- Install into versioned application directories and activate only after health checks pass.
- Store persistent user data separately (initial proposal: `%LOCALAPPDATA%\\MASTER-ARSENAL\\`), with reports, evidence, settings, logs, and optional local account-export files preserved across upgrades.
- Never write secrets or user account exports into the Git repository or application package.
- Keep rollback to the previous known-good runtime/application version until the new version passes startup and smoke checks.

## Runtime and dependency packaging notes

The official Python Windows documentation describes the embeddable distribution as isolated and intended to be embedded in another application. It does not include pip, and its documentation recommends treating third-party packages as part of the application. Therefore, the proposed design uses a prebuilt, versioned dependency bundle rather than depending on pip at first launch.

The exact CPython patch version, Java vendor/build, dependency lock, and bundle layout are intentionally not fixed in this ADR until the Windows CI prototype demonstrates compatibility with the repository's complete dependency graph.

## Security and data-safety requirements

- HTTPS-only artifact retrieval from explicitly allowlisted release origins.
- SHA-256 verification against a manifest pinned in the signed/reviewed JAR release.
- Verify publisher signatures when the selected runtime vendor provides them.
- Reject archive traversal, symlink escapes, unexpected executable payloads, and writes outside managed directories.
- No shell command construction from job input; invoke only fixed executable paths with argument arrays.
- No administrator privileges unless a separately approved requirement makes them unavoidable.
- Atomic staging and activation; preserve the previous working version until the new version passes health checks.
- No automatic trading, order placement, exchange-account access, API-key collection, or credential storage.

## Proposed platform contract

- **Initial supported platform:** Windows 11 x64.
- **Compatibility candidate:** Windows 10 x64, only if the CI and clean-machine test matrix proves it and the user accepts its operating-system support status.
- **Not in Phase 4 acceptance:** macOS, Linux, ARM64, and 32-bit Windows.
- **Java prerequisite:** Java 21 x64 runtime; exact vendor/build to be selected after compatibility and licensing review.
- **Python runtime:** private CPython Windows x64 embeddable/runtime bundle; exact patch release pinned at release time.

## Required prototype and validation before implementation approval

1. Prove the JAR starts on a clean Windows x64 machine with Java 21 installed and no Python installation.
2. Prove the JAR reports a clear error on a machine without the required Java runtime.
3. Build and verify the complete private Python runtime/dependency bundle on Windows CI.
4. Prove the bundled MALE can initialize its workspace and execute a harmless read-only health-check job.
5. Prove a failed download, checksum mismatch, interrupted extraction, or failed startup leaves the previous installation and persistent user data intact.
6. Prove an upgrade preserves reports, evidence manifests, settings, and logs.
7. Record exact artifact hashes and provenance in a release manifest.

## Open decisions requiring user approval

1. **Java prerequisite:** Is requiring Java 21 x64 to be installed acceptable while keeping the single-JAR requirement, or should the user-facing artifact eventually become a self-contained Windows EXE/installer?
2. **Windows 10:** Should Windows 10 x64 be a supported target, or should Phase 4 formally support Windows 11 x64 only?
3. **Initial setup:** Is an internet connection acceptable for first-time runtime provisioning, with offline installation considered as a later enhancement?

## Consequences

No runtime, dependency, packaging, signing, or deployment implementation should begin until this ADR is reviewed and approved. Phase 4 remains an evolving release milestone; this decision does not limit later MALE enhancements or future macOS support.
