Original Claude skill source provenance

The manifest records the SHA-256 and byte size of the four original .skill ZIP uploads supplied in the MASTER ARSENAL conversation on 2026-11-16, along with the single SKILL.md member and its SHA-256.

The ZIP payloads themselves are not committed to this repository. Therefore:
- The intake-time hashes are provenance records.
- The runtime audit verifies the manifest structure and the identity of the four ChatGPT adaptation files.
- The runtime audit correctly reports original archive payload integrity as NOT VERIFIED, because it cannot recompute archive hashes without the exact ZIP bytes.
- Do not change a recorded hash unless the original source package is re-supplied and independently re-hashed.

The original uploaded files remain the authoritative source. The adapted files live under skills/.
