# ADR-0001: Windows-first MALE distribution architecture

- **Status:** Revised proposal — requires Sensei's review and approval
- **Date:** 2026-11-18
- **Scope:** Phase 4 distribution foundation
- **Target branch:** `feature/phase-4-distribution-foundation`
- **Platform baseline:** Windows 10/11, x64 (provisional; Windows 10 support requires explicit validation)

## Context

MASTER ARSENAL is currently a Python application with the Binance Data Engine, Local Engine, and PDF Report Engine. The user-facing goal for Phase 4 is a single-download Windows application that starts MALE on a clean PC without requiring preinstalled Java, Python, pip, or manual PATH configuration. A JAR alone cannot meet this requirement because it needs a JVM to start.

The existing Phase 4 plan requires a design/ADR gate before changes to runtime, dependencies, packaging, signing, or deployment. This ADR is a proposal only; it does not authorize those implementation changes.

## Decision drivers

1. Provide a zero-prerequisite Windows user experience: no preinstalled Java, Python, pip, or manual PATH configuration.
2. Preserve the existing Java/Python development workflow on the developer's machine without making those installations runtime dependencies.
3. Resolve the conflict between a literal standalone JAR and a clean-PC launch requirement before selecting the final user-facing artifact.
4. Keep Java, Python, and all application dependencies private to the application package or managed runtime.
5. Support Windows x64 first; do not make macOS a Phase 4 acceptance requirement.
6. Pin every runtime and dependency artifact and verify SHA-256 (and publisher signatures where available) before use.
7. Keep persistent reports, evidence, settings, and logs outside replaceable application/runtime directories.
8. Preserve the existing read-only, no-trading, no-credential-storage, pre-investment boundaries.
9. Do not require a user-managed Java/Python installation, pip, or manual PATH changes.

## Options considered

### A. Native Windows bootstrapper/package + bundled Java and Python runtimes

A small native Windows launcher or self-contained Windows application package is the user-facing entry point. It includes or securely provisions a pinned Java runtime and a private Windows x64 Python runtime/dependency bundle, verifies all artifacts, and then starts the existing MALE entry point. The Java/Python runtimes and application dependencies are isolated from system installations. User data remains in a separate stable data directory. The existing executable JAR can remain an internal application/bootstrap component, but cannot itself be the zero-prerequisite launcher.

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

### B. Standalone executable JAR with Java prerequisite

Distribute the executable JAR and privately provision Python, but require the target PC to already have a supported Java runtime.

**Advantages**
- Can avoid requiring Java to be installed by the user.
- Better native Windows launch and installation experience.

**Costs / risks**
- Does not satisfy the current single executable JAR deliverable literally.
- Produces a Windows-specific artifact and changes the user-facing distribution contract.
- Must be built and validated on Windows; macOS would require a separate package pipeline later.

### C. Ask the user to install Java and/or Python and dependencies

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
- **Java runtime:** bundled Java 21 x64 runtime; exact vendor/build to be selected after compatibility and licensing review.
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

1. **User-facing artifact:** Do you approve changing the literal single-JAR download to one self-contained Windows EXE/installer/package that bundles Java and Python, while optionally retaining the JAR internally? This is the only proposed path here that meets the clean-PC requirement.
2. **Windows 10:** Should Windows 10 x64 be a supported target, or should Phase 4 formally support Windows 11 x64 only?
3. **Initial setup:** Is an internet connection acceptable for first-time runtime provisioning, with offline installation considered as a later enhancement?

## Consequences

No runtime, dependency, packaging, signing, or deployment implementation should begin until this revised ADR and the user-facing artifact decision are reviewed and approved. Phase 4 remains an evolving release milestone; this decision does not limit later MALE enhancements or future macOS support.
