# Architecture

Keep architecture simple: `input validation -> Discogs search adapter -> per-entry classification -> grouped summary -> all-OK gate -> publisher port`.

## Planned Python modules (not created yet)

- `models`: input and output types; strict validation.
- `discogs_client`: authenticated HTTP client, pagination, bounded retries and cache/snapshots.
- `search_service`: one user query per input position, distinct Master ID aggregation, completeness checks.
- `summary`: stable grouping, display-only top-three candidate ordering, JSON and terminal output.
- `gate`: pure all-OK predicate.
- `publisher`: independent capability-gated publishing interface; initial implementation exports a manifest only.
- `cli`: `validate` and `run`, stable exit codes and orchestration.

The command `run` searches **every** entry before deciding whether to proceed. No auto-correction engine, no alias machinery required, no fuzzy matching, and no interactive menu. The user edits JSON and reruns.

## Invariants

1. One input element -> exactly one output result, even on errors.
2. Search fields are not mutated (except internal `type=master` and paging controls in transport).
3. `OK` iff complete search returned precisely one unique Master ID.
4. All non-OK entries block publishing.
5. Output ordering is stable and input positions never move.
6. Candidate ranking never silently selects a Master.
7. An unavailable publisher is a hard publishing limitation, not a fake success.

## Boundaries

Use dependency injection for HTTP requests and publisher, allowing tests without live accounts or network. Cache raw responses with request params and page identifiers; a snapshot makes reruns reproducible. Never store tokens in output.
