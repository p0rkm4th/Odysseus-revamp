# Hades Security Assessment Foundation V1

Source baseline: `4ded405973a605fc6b5303e41e447b0ef7b3703a`.

Candidate image: `odysseus-odysseus:security-assessment-v1-20260823`, digest
`sha256:f351eaf3f5ae93728c8249c396c942aa7a270eb7f71932855e59500f6df70786`.

## Boundary

V1 provides owner-scoped durable engagements, independent authorization
records, explicit include/exclude scopes, canonical CMDB/inventory reference
fields, targets, bounded run plans, provenance-rich evidence, findings and
status lifecycle, and reports as projections over stored state.

It does not provide exploit execution, credential attacks, persistence,
arbitrary shell, privileged containers, Docker access, or arbitrary public
scanning. The agent binding is read-only in V1. Mutating workflow is exposed
through authenticated API routes and remains subject to current Hades policy.

## Migration

`20260823_003_security_assessment_v1` adds:

- `security_engagements`
- `security_authorizations`
- `security_scopes`
- `security_targets`
- `security_runs`
- `security_evidence`
- `security_findings`
- `security_reports`

Fresh, rerun, and copied-application-database rehearsals passed. CMDB tables
were not changed.

## Verification

- Focused security/capability/CMDB tests: 155 passed.
- Relevant regression suite: 5737 passed, 4 skipped, 0 failed; 108 hardware-fit
  catalog tests deselected from this environment.
- Full collected suite: 5829 passed, 4 skipped, 16 failures confined to stale
  hardware-fit catalog expectations unrelated to this domain.
- Authenticated live workflow: unauthorized run blocked; authorized bounded
  record-only run completed; evidence, finding confirmation, report generation,
  UI exposure, owner authentication, and restart persistence passed.

The live test deliberately performed no network scan or mutation.
