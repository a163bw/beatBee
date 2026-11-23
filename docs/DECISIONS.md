# Architecture Decision Record — accepted decisions

| ID | Decision | Rationale |
|---|---|---|
| D-001 | Input is a named ordered list of **Discogs search-parameter dictionaries**. | Allows any supported API search combination. |
| D-002 | `type` defaults to `master`; users may select multiple Discogs resource types. Only Master IDs resolve list entries. | Broader search diagnostics while retaining Master-list output. |
| D-003 | Run one paginated logical search per selected type; search Master first when selected. | Make type selection explicit and deterministic. |
| D-004 | Exactly 1 distinct qualifying Master ID => `OK`; 0 => `NOT_FOUND`; >1 => `MULTIPLE`. | Preserve Master-ID cardinality semantics across selected searches. |
| D-005 | The user edits input and reruns to fix `NOT_FOUND` and `MULTIPLE`. | No interactive resolver or automatic selection. |
| D-006 | Show top three candidates for MULTIPLE with URLs, but never select them. | Diagnostic support without hidden decisions. |
| D-007 | Always show a complete grouped summary: OK, NOT_FOUND, MULTIPLE, ERROR. | All issues visible in one run. |
| D-008 | Exit without publishing if **any** result is non-OK. | Hard validation gate. |
| D-009 | Intended destination is a Discogs user-created list, not Collection/Wantlist. | Clear product scope. |
| D-010 | Publishing is gated on a verified supported mechanism; no undocumented API calls. | Avoid invented implementation. |
| D-011 | No fuzzy/AI matching, aliases or candidate auto-picking. | Minimal deterministic engine. |
| D-012 | Freeze API snapshots for strong reproducibility; live results may change. | External database is mutable. |
| D-013 | Only Markdown planning files at this phase; no code skeletons generated. | Architecture first, Copilot implementation later. |
| D-016 | Explicitly selected release results may contribute their associated `master_id`; the automatic release fallback remains diagnostic only. | A user-selected release search can resolve a Master, without promoting fallback releases. |
| D-017 | JSON export adds `master_id` only to `OK` records and retains original JSON for unresolved records. | Persist confirmed results without rewriting unresolved queries. |
