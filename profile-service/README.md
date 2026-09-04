# Owner profile domain foundation

This is a local-only, standard-library foundation for the
[proposed private profile-photo service](../system/OWNER_PROFILE_PHOTO_ARCHITECTURE.md).
It is not an HTTP service, storage provider, image decoder or working upload feature.
No dependencies are installed, credentials loaded, provider calls made or paid resources started.
Hosted activation still requires verified existing cost coverage and exact external-action approval;
see the [no-spending rule](../AGENTS.md#no-spending-requirement).

`profile_state.py` defines immutable photo snapshots, a compare-and-swap repository contract,
and create/replace/remove transitions. Revisions prevent stale writes and removal tombstones
prevent a delayed save from reviving an old photo. A failed write does not trigger automatic retry;
the caller must read metadata to reconcile an uncertain outcome. Missing state differs from storage failure.

The caller must already be authenticated and owner-bound, and supply bytes produced by an independently
validated image decoder. Size and JPEG-marker checks here are defense in depth, **not image validation**.
Do not expose this module directly as an upload endpoint. Authentication, origin checks, bounded streaming,
resource-limited decoding, metadata stripping, production persistence, UI, and device checks remain pending.
No production in-memory fallback is supplied. The in-memory repository exists only in tests.

`upload_input.py` adds local file-part intake: a 5 MiB actual-byte limit, optional file-length
consistency check, JPEG/PNG/WebP signature matching, a 15-second intake timeout and an 8192-chunk
budget. It rejects malformed streams and hides transport diagnostics; cancellation propagates.
Its output is still untrusted encoded input, **not** a normalized photo for `ProfileState`.
Signatures do not prove that a file decodes or is safe. A future authenticated HTTP adapter must
also bound multipart overhead, incoming chunk allocation, concurrency and connection lifetime.
Do not pass the enclosing multipart Content-Length as the file-part length.

From the repository root, use an existing Python 3.12+ interpreter:

```text
python -m unittest discover -s profile-service/tests -v
python -m compileall -q profile-service
```

Tests use synthetic byte fixtures, not photographs. Their fake JPEG markers deliberately do not claim
decoder acceptance. Repository tests cover stale mutations, concurrent creation, tombstones, storage
failures before/after commit, immutable snapshots, bounded normalized output and metadata minimization.
They do not prove cloud authorization, image safety, durable storage or successful deployment.
Intake tests additionally cover size boundaries, misleading lengths, signature mismatch, interruption,
timeout, cancellation and empty-chunk floods. All fixtures are synthetic; no image decoder is invoked.

A future storage adapter must make the entire revision check and write atomic across service instances,
return immutable consistent snapshots, and translate provider failures into generic boundary errors.
It must bind storage to the server-configured owner rather than accept an owner/path from the browser.
Never use process-local locks as a substitute for provider conditional writes in distributed deployment.
