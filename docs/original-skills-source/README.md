Original Claude skill source provenance

The manifest records the SHA-256 and byte size of the four original .skill ZIP uploads supplied in the MASTER ARSENAL conversation on 2026-11-16, along with the single SKILL.md member and its SHA-256.

All four uploaded originals were reopened during the current development session. Each archive contains exactly one `<skill-name>/SKILL.md` member; archive byte counts and archive/SKILL.md SHA-256 values were recomputed and matched the manifest. These checks were performed against the original uploaded files in the development workspace.

The ZIP payloads themselves are not committed to this repository. Therefore:
- The recorded hashes are supported by a direct verification of the uploaded originals in this development session; the runtime cannot repeat that check after installation because the ZIP payloads are not included.
- The runtime audit verifies the manifest structure and the identity of the four ChatGPT adaptation files.
- The runtime audit correctly reports original archive payload integrity as NOT VERIFIED, because it cannot recompute archive hashes without the exact ZIP bytes.
- Do not change a recorded hash unless the original source package is re-supplied and independently re-hashed.

The original uploaded files remain the authoritative source. The adapted files live under skills/.
