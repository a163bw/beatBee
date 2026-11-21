# Open questions / risks

These are **not** permission to change the accepted behavior in SPEC.md.

1. **Publishing feasibility (blocking):** Is a compliant and reliable method available to create a Discogs user list containing **Master** entries? Confirm with a technical spike before coding the publisher.
2. **Search result limits:** Full pagination may be expensive for broad user queries; what maximum result size should trigger `ERROR` and prompt the user to narrow their query? Never silently count truncated results.
3. **Meaning of “best three”:** The current deterministic exact-field ranking is a proposed display policy; approve or replace with another documented total ordering. This does not change cardinality-based status.
4. **Duplicate resolved Master IDs:** Two input entries could resolve to the same Master. Preserve both positions locally, but confirm whether Discogs user lists allow duplicate Master items and how that affects publishing.
5. **Publisher reruns:** Should successful `run` require interactive confirmation, a `--publish` flag, or an idempotent find-or-create check? Default must avoid surprise duplicates.
6. **Schema parameter types:** Lock the allowed query keys/value types to the verified Discogs API contract at implementation time; avoid unsupported assumed ranges or semantics.
7. **Failure code priority:** If some entries have unresolved status and others have API errors, choose a stable CLI exit-code priority while always reporting all entries.

Already decided: no automatic query refinement, no interactive selection, no manual overrides in the application, no multi-stage search, no title/year semantic verification after exactly one result.
