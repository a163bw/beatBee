# Architecture Decision Record — accepted decisions

| ID | Decision | Rationale |
|---|---|---|
| D-001 | Input is a named ordered list of **Discogs search-parameter dictionaries**. | Allows any supported API search combination. |
| D-002 | Search with `type=master` first; only after a complete zero-Master result, search with `type=release` as an album fallback. | Prioritize Masters while still finding release-level album entries. |
| D-003 | One primary Master search per element, with pagination; a conditional release fallback is a second paginated search only after zero Masters. | Keep the priority explicit and avoid unnecessary searches. |
| D-004 | Exactly 1 distinct Master => `OK`; 0 => `NOT_FOUND`; >1 => `MULTIPLE`. Release fallback results are diagnostic only and never satisfy the Master gate. | Preserve Master-only manifests and publishing safety. |
| D-005 | The user edits input and reruns to fix `NOT_FOUND` and `MULTIPLE`. | No interactive resolver or automatic selection. |
| D-006 | Show top three candidates for MULTIPLE with URLs, but never select them. | Diagnostic support without hidden decisions. |
| D-007 | Always show a complete grouped summary: OK, NOT_FOUND, MULTIPLE, ERROR. | All issues visible in one run. |
| D-008 | Exit without publishing if **any** result is non-OK. | Hard validation gate. |
| D-009 | Intended destination is a Discogs user-created list, not Collection/Wantlist. | Clear product scope. |
| D-010 | Publishing is gated on a verified supported mechanism; no undocumented API calls. | Avoid invented implementation. |
| D-011 | No fuzzy/AI matching, aliases or candidate auto-picking. | Minimal deterministic engine. |
| D-012 | Freeze API snapshots for strong reproducibility; live results may change. | External database is mutable. |
| D-013 | Only Markdown planning files at this phase; no code skeletons generated. | Architecture first, Copilot implementation later. |
| D-014 | Discogs User List API publishing remains disabled until an official write contract is verified. | The documented/live-checked User List resources expose read operations only; no supported create/edit/add/remove contract is confirmed. |
| D-015 | A release/album fallback never becomes a Master result, even when it finds one or more releases. | Release IDs are not Master IDs and must not enter the Master manifest. |
