# Distribution requirements (roadmap)

## Mandatory user-facing delivery

The final desktop distribution must be delivered as **one downloadable executable JAR**. A user should not have to install Python, run pip, create a virtual environment, configure PATH, or execute manual setup commands.

The JAR must provide a first-run bootstrap flow that:
- Detects the operating system, architecture, available disk space, network access, and required runtime capabilities.
- Checks for a compatible Java runtime and clearly reports/provisions it according to the approved deployment design.
- Provisions a compatible Python runtime and every pinned project dependency if Python remains part of the implementation.
- Verifies downloaded runtime/dependency artifacts using trusted checksums or signatures before execution.
- Uses a managed application directory and keeps user reports, evidence, settings, and account exports outside replaceable application files.
- Creates a fixed `data/account_exports/` import directory for user-supplied Binance transaction-history CSV files. These files are local-only, excluded from version control, and never uploaded to a private API or embedded in application binaries.
- The current parser supports the common `User_ID, UTC_Time, Account, Operation, Coin, Change, Remark` transaction-history schema; Binance export formats vary, so unsupported headers are marked partial rather than guessed. It omits User_ID and Remark from report evidence, stores only file hashes and aggregate event/asset amounts, and explicitly marks ambiguous UTC timestamps as an assumption. See [Binance Report Center export types](https://www.binance.com/en/support/faq/detail/efe336a96f704afdb939905ad3adba21); the exact CSV header should be checked against the user's downloaded file.
- Supports safe, repeatable upgrades without deleting user data or silently downgrading dependencies.
- Produces clear, actionable diagnostics when installation, network access, or runtime validation fails.
- Starts the local engine only after dependency and integrity checks succeed.

## Architecture boundary

The current implementation is Python-first. A Java bootstrapper JAR that provisions and launches the Local Engine is a candidate design, not an approved implementation. The exact Java-runtime strategy, Python distribution, dependency bundling/provisioning, signing, update channel, and offline behavior require a separate technical specification and explicit approval before architecture, dependency, or deployment changes are made.

## Scope separation

- This is a mandatory release requirement, not a Phase 3 PDF-engine completion claim.
- No packaging, CI/CD, installer, signing, or deployment changes are authorized by this documentation entry.
- OpenJarvis remains a future roadmap integration and is not part of the current Phase 3 implementation.
