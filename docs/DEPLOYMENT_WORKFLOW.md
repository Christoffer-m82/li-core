# Deployment workflow

## Scope and authority

This is a release review checklist, not an executable deployment script. The detailed, component-
specific sources remain authoritative:

- [Backend deployment and verification](../README.md#secure-remote-deployment)
- [Web staging deployment](../frontend/README.md#staging-deployment)
- [Native Gateway deployment gate](../deployment/cloud-run/native-gateway.md)
- [Artifact retention enforcement](../deployment/cloud-run/artifact-retention.md)
- [Governed proactivity scheduler](../deployment/cloud-run/governed-proactivity.md)

Repository assets describe Google Cloud Run in `europe-west1`, but tracked files do not prove the
current state of any external environment.

## Release record

Before acting, record the environment, Git commit, immutable image digest, included migrations,
operator, planned time, user impact, rollback target, and links to approval evidence. Record secret
*version identifiers* where policy permits, never secret values.

## Workflow

### 1. Establish scope

- Start from a clean or fully understood worktree.
- Review the complete commit range and identify application, schema, configuration, identity/IAM,
  secret-reference, scheduler, and data-retention changes separately.
- Confirm the target service: backend, web BFF, Native Gateway, retention job, or scheduler. Do not
  implicitly deploy adjacent components.
- Confirm external state with authorized read-only checks. Mark anything not checked as unknown.

### 2. Pass prerequisite gates

- Complete the applicable tests in [Testing and audit](TESTING_AND_AUDIT.md).
- Complete the boundary review in [Security boundaries](SECURITY_BOUNDARIES.md).
- For schema-dependent code, complete [Migration workflow](MIGRATION_WORKFLOW.md) and verify the
  required schema version in the target database before application rollout.
- The `codex/li-os-improvement-blueprint` backend requires migrations 037 and 038 before rollout.
  Migration 038 is forward-compatible with the preceding backend; deploying the new action-recovery
  code against schema 0.37 can leave an uncertain provider write without its required durable state.
  This ordering note does not authorize either external operation.
- Build from the repository root using the component Dockerfile and retain the immutable digest.
- Inspect rendered configuration without exposing values. Reject unresolved placeholders,
  unauthenticated backend access, wildcard production CORS, unpinned rollout inputs where pinning is
  required, and unexpected service-account or secret-reference changes.

### 3. Deploy narrowly

- Deploy to staging or another non-production environment with synthetic/minimal data first.
- Use the intended dedicated runtime identity and least-privilege secret references.
- Keep backend IAM private. Treat the gateway's network reachability and application authentication
  as separate controls.
- Provision proactivity jobs paused. Resume only the owner-approved matching rhythm.
- Do not combine migration execution and service deployment into an opaque command.

### 4. Verify

Run component-specific smoke tests from the authoritative source. At minimum verify:

- unauthenticated requests fail where expected;
- public health reveals no sensitive integration state;
- authenticated readiness succeeds;
- a normal read path works;
- denial paths for owner, gateway, or scheduler-only routes remain denied to ordinary authority;
- provider absence degrades as documented and partial sensitive configuration fails safely;
- logs contain request correlation but no credentials or sensitive payloads; and
- the deployed revision and image digest match the release record.

Use harmless reads for provider smoke tests. Do not send mail, create consequential calendar data,
activate rhythms, or write personal memory merely to prove deployment health.

### 5. Promote or stop

Promote only the already-tested immutable image and reviewed configuration. Stop on schema mismatch,
unexpected IAM diff, secret-reference mismatch, failed denial test, sensitive logging, unexplained
data changes, or inability to name a safe rollback target.

### 6. Roll back

For an application-only failure, shift traffic to the last known-good immutable revision as
described in the [README rollback guidance](../README.md#rotation-and-rollback). Database rollback is
a separate, data-preserving decision: follow [Migration workflow](MIGRATION_WORKFLOW.md), do not edit
or rerun historical SQL, and do not assume an application rollback reverses schema or data changes.

### 7. Close out

Record results, deviations, operator-verified external state, smoke-test evidence, the final traffic
revision, and remaining risks. Keep failed revisions at zero traffic for diagnosis unless retention
policy requires later cleanup. Update operating docs only when repository evidence or an explicitly
verified operational fact has changed.
