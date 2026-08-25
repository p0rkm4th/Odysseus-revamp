# Career foundation

Career is a module under the Work workspace, not a top-level workspace or a
provider-owned database. Its canonical concepts are `CAREER_PROFILE`,
`JOB_SEARCH`, `JOB_OPPORTUNITY`, `APPLICATION`, and `INTERVIEW`.

Durable owner-scoped state lives in the Career service and references existing
Work tasks, Contacts, Email, Calendar, Documents/Resume, and Notifications.
External job providers are adapters. Their records are normalized and
deduplicated before becoming owner-owned opportunity projections; provider
APIs never own application lifecycle state.

The current provider state is `NOT_CONFIGURED`. The UI and read contract make
that explicit and return no fabricated listings. Read operations use the
generic IntentFrame -> DomainContract -> ActionSpec -> ToolBinding path and
normally require no approval. Provider mutations (`submit_application`,
`send_message`, and `book_interview`) are declared as exact-approval actions;
no autonomous application submission is implemented.

Evidence level: E2 focused-tested after the Career batch; owner-live provider
acceptance remains pending external configuration.
