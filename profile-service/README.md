# Owner profile domain foundation

This is a local-only foundation for the
[proposed private profile-photo service](../system/OWNER_PROFILE_PHOTO_ARCHITECTURE.md).
It is not an HTTP service, storage provider or working upload feature.
The optional decoder uses a pinned Pillow dependency in an isolated local environment.
No credentials are loaded, provider calls made or paid resources started.
Hosted activation still requires verified existing cost coverage and exact external-action approval;
see the [no-spending rule](../AGENTS.md#no-spending-requirement).

`profile_state.py` defines immutable photo snapshots, a compare-and-swap repository contract,
and create/replace/remove transitions. Revisions prevent stale writes and removal tombstones
prevent a delayed save from reviving an old photo. A failed write does not trigger automatic retry;
the caller must read metadata to reconcile an uncertain outcome. Missing state differs from storage failure.

The caller must already be authenticated and owner-bound, and supply bytes produced by an independently
validated image decoder. Size and JPEG-marker checks here are defense in depth, **not image validation**.
Do not expose this module directly as an upload endpoint. Authentication, origin checks, HTTP streaming
integration, verified worker sandboxing, production persistence, enabled UI, and device checks remain pending.
The browser has disabled controls and authenticated placeholder routes so the user journey can be
reviewed without pretending that storage exists.
No production in-memory fallback is supplied. The in-memory repository exists only in tests.

`profile_application.py` composes the state, bounded intake and decoder behind an exact workload
audience/subject check. It accepts only claims produced by a future independently verified identity,
never browser headers or an owner/profile identifier. The injected repository is already owner-bound.
Wrong workloads and stale revisions are rejected before the upload stream or decoder is touched, and
the state layer rechecks the revision at the atomic write. This is not token verification or an HTTP
endpoint: cryptographic identity verification, multipart/transport limits and generic HTTP error mapping
remain required before the application layer can be exposed.

`object_repository.py` provides a provider-neutral durable-storage boundary for one already-bound
private object. It stores revision, state and normalized bytes together and converts the hidden object
generation into create-if-absent or generation-matched writes. A stale revision or provider-generation
race cannot overwrite the winner; uncertain provider failures remain errors for read reconciliation.
The strict versioned object format rejects malformed state and exposes neither provider generations nor
paths to the application. It is not a cloud adapter and creates no bucket or object.

`upload_input.py` adds local file-part intake: a 5 MiB actual-byte limit, optional file-length
consistency check, JPEG/PNG/WebP signature matching, a 15-second intake timeout and an 8192-chunk
budget. It rejects malformed streams and hides transport diagnostics; cancellation propagates.
Its output is still untrusted encoded input, **not** a normalized photo for `ProfileState`.
Signatures do not prove that a file decodes or is safe. A future authenticated HTTP adapter must
also bound multipart overhead, incoming chunk allocation, concurrency and connection lifetime.
Do not pass the enclosing multipart Content-Length as the file-part length.

`image_normalize.py` implements the decoder core, **not its sandbox**. It accepts JPEG/PNG/WebP only,
checks dimensions and animation, corrects EXIF orientation, center-crops a square, and creates a fresh
512x512 RGB JPEG without source metadata. Transparency is composited on white. The future UI must
preview this same oriented center crop before upload. Never invoke the decoder inline in the web process:
Use the supervised worker described below rather than calling this core from an endpoint.

## Decoder process boundary

`decoder_process.py` launches one one-shot worker at a time per supervisor instance, rejecting additional
jobs rather than building an unbounded queue. The service must own exactly one instance per event loop
and bound its own process/replica count. Input is sent over stdin, never a filename or command argument.
Output is capped at 512 KiB and stderr is discarded. Environment variables are not inherited except
Windows SystemRoot; isolated Python mode ignores user import configuration. Timeout (8 seconds), crashes,
invalid output and unsupported hosts fail without storage writes. Cancellation, including during spawn,
waits for the direct worker to terminate before releasing the slot.

`decoder_worker.py` applies Linux limits before importing the decoder: 512 MiB address space, 3 CPU
seconds, no core dumps or file growth, and 32 file descriptors. A host unable to apply all limits refuses
the job. Windows currently tests this refusal, not successful production decoding. The 8-second deadline
includes normal process startup; uninterruptible OS spawn/reaping is not a hard real-time guarantee.

These controls are **not a filesystem, network or hostile-code sandbox**. Before live activation,
verify Linux enforcement and run under a separately approved least-privilege runtime with no photo-storage
credentials, network access or private filesystem access; the current subprocess alone cannot enforce
those boundaries or contain a compromised decoder spawning descendants. HTTP/storage/UI integration stays
disabled. Do not replace unsupported limits with an unrestricted fallback.

From the repository root, use an existing Python 3.12+ interpreter:

```text
python -m unittest discover -s profile-service/tests -v
python -m compileall -q profile-service
```

The standard-library run skips decoder tests if Pillow is absent; that is not decoder acceptance.
For the complete local suite on CPython 3.12 Windows x64, create a separate environment:

```text
python -m venv profile-service/.venv
profile-service/.venv/Scripts/python -m pip install --only-binary=:all: --require-hashes -r profile-service/requirements-decoder.txt
profile-service/.venv/Scripts/python -m unittest discover -s profile-service/tests -v
```

The pinned hashes cover Windows x64 and Linux x64 CPython 3.12 wheels from PyPI. Other platforms need
reviewed hashes before installation. See [Pillow security guidance](https://pillow.readthedocs.io/en/stable/handbook/security.html)
and [12.3.0 release notes](https://pillow.readthedocs.io/en/stable/releasenotes/12.3.0.html).

Tests use synthetic byte fixtures, not photographs. Their fake JPEG markers deliberately do not claim
decoder acceptance. Repository and application tests cover identity denial before byte intake, stale
mutations, concurrent creation, tombstones, versioned-object corruption and storage
failures before/after commit, immutable snapshots, bounded normalized output and metadata minimization.
They do not prove cloud authorization, image safety, durable storage or successful deployment.
Intake tests additionally cover size boundaries, misleading lengths, signature mismatch, interruption,
timeout, cancellation and empty-chunk floods. Decoder tests use generated in-memory images for format
conversion, orientation/crop, transparency, metadata removal, animation, dimensions and invalid content.
Process tests use real synthetic child processes for successful output, crashes, excess output,
timeouts, slot reuse and cancellation during startup. Mocked limit configuration tests establish intent,
not kernel enforcement. CI runs the real worker on Linux and proves that it refuses to produce an image
unless limit setup succeeds; hostile-code isolation acceptance remains pending.
These tests do not establish safe handling of every hostile image.

A future storage adapter must make the entire revision check and write atomic across service instances,
return immutable consistent snapshots, and translate provider failures into generic boundary errors.
It must bind storage to the server-configured owner rather than accept an owner/path from the browser.
Never use process-local locks as a substitute for provider conditional writes in distributed deployment.
