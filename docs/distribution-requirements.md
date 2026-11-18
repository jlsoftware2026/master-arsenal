# Windows distribution requirements

**Status:** Approved Phase 4 user-facing contract  
**Architecture decision:** [ADR-0001 — Windows-first MALE distribution architecture](adr/0001-windows-first-distribution.md)

## Mandatory user-facing delivery

The Phase 4 desktop distribution must be delivered as **one self-contained Windows EXE/installer/application package**. The package must bundle the supported Java and Python runtimes and all required application dependencies. A user must not need to install Java, Python, run pip, create a virtual environment, configure PATH, or execute manual setup commands.

The existing executable JAR may be retained as an internal component, but it is not the user-facing download or launcher. A JAR alone cannot launch on a clean PC without an already-running JVM.

The Windows package must:
- Detect and validate the operating system, architecture, available disk space, and package integrity before installation or launch.
- Support Windows 10 22H2 x64 and Windows 11 x64, subject to the clean-machine validation matrix and documented edition/build limits.
- Bundle a supported Java 21 x64 runtime and a private, pinned Windows x64 CPython runtime with a complete prebuilt dependency bundle.
- Avoid invoking pip on the user's PC.
- Verify runtime/dependency artifacts using reviewed SHA-256 manifests and publisher signatures where available before extraction or execution.
- Use managed, versioned application directories and keep reports, evidence, settings, and logs in persistent user-data storage outside replaceable application files.
- Support safe, repeatable upgrades and rollback without deleting user data or silently downgrading dependencies.
- Produce clear, actionable diagnostics when installation, integrity checks, runtime initialization, startup, or network access fails.
- Start MALE only after runtime, dependency, and application integrity checks succeed.
- Pass clean-machine validation on supported Windows x64 environments with neither Java nor Python preinstalled.

## Connectivity requirements

- Internet connectivity is required for live market-data acquisition, current market snapshots, and workflows that depend on external data providers.
- The application must detect and clearly report unavailable network access, DNS/TLS failures, rate limits, timeouts, and provider outages.
- A network/provider failure must never be represented as a successful live-data result or silently replaced with fabricated, stale, or incomplete data.
- Local functions that do not require a provider may remain available offline where practical; the UI/CLI must distinguish local engine health from live-provider connectivity.
- The installer/package should bundle Java, Python, and pinned dependencies. Users should not need internet access merely to compensate for missing runtimes or to run pip on first launch. Internet is required when MALE performs live research and when it retrieves updates or remote data.

## Data and privacy boundary

- The current product remains a pre-investment research and decision-support system.
- No transaction-history CSV is expected or required for the current workflow.
- Full portfolio accounting, PnL/cost-basis reconciliation, and transaction-history ingestion are future extensions, not Phase 4 distribution acceptance requirements.
- Missing account data must be classified as not applicable, never as a zero balance or a distribution error.
- If optional account-export support is retained, files remain local-only, outside version control and application binaries, and must never be uploaded to a private API.
- Never collect or store exchange API keys, credentials, or other secrets.
- No automated trading, order placement, or private exchange-account access.

## Architecture and platform boundary

- The implementation is Python-first today; Java is used only where justified by the approved Windows launcher/package architecture.
- Supported target platforms for Phase 4: Windows 10 22H2 x64 and Windows 11 x64, subject to clean-machine validation.
- macOS, Linux, ARM64, and 32-bit Windows are outside Phase 4 acceptance. macOS may be considered in a future milestone.
- Exact Java/Python builds, dependency versions, packaging technology, signing process, update channel, and provider/network behavior must be documented and tested before release.
- Windows 10 support does not imply that MALE extends Microsoft's operating-system security servicing; users remain responsible for their Windows servicing and security status.
- OpenJarvis integration and planned Pro upgrades remain future roadmap items.

## Scope separation

- These are Phase 4 distribution requirements, not a claim that packaging, CI/CD, installer, signing, or deployment is already implemented.
- Runtime and dependency changes must follow ADR-0001 and pass the defined security, licensing, CI, and clean-machine validation gates.
- Phase 4 is an evolving release milestone, not the final update to MASTER ARSENAL.
