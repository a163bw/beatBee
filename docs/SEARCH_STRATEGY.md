# Discogs search contract

## Query construction

Each `records[i]` dictionary is passed as search parameters to `GET /database/search`, along with application-managed `type`, `page`, and `per_page`. An omitted `type` defaults to `master`; a type may be one resource name or a nonempty array from `master`, `release`, `artist`, and `label`. Run one complete paginated search per selected type, searching `master` first when selected. The `type` value itself is removed from the remaining query parameters. Reject unknown keys and type values. User query fields are not rewritten or augmented to broaden or narrow searches.

## Exhaustiveness

Request all result pages for each selected type and deduplicate numeric resource IDs. Reject unexpected resource types, malformed IDs, or truncated responses as `ERROR`. If configurable result/page caps are reached, label incomplete (not `MULTIPLE` by default). Avoid retry loops without bounds; respect 429/Retry-After and stable retry policy. A failed selected type search makes the overall item `ERROR`, even if another selected type returned results.

## Classification

- Count distinct Master IDs from selected `master` results and from associated `master_id` values in explicitly selected `release` results.
- `0` Master IDs => `NOT_FOUND`; `1` => `OK`; `>=2` => `MULTIPLE`, with no auto-pick.
- `artist` and `label` results are displayed as per-type diagnostics but never resolve a list item. A `release` result without an associated Master ID also cannot resolve it.
- Any incomplete/failed search => `ERROR`.
- If `master` is selected and its complete search returns no Masters, the application-controlled release fallback still runs. Fallback release IDs are diagnostic only and never count as Master IDs; an explicitly selected `release` search may use valid associated Master IDs.

## Top-three display ranking

The user requested the **three best** candidates. Search API relevance ordering is not a reproducible contract and may change, so BeatBee uses the following stable, display-only rules:

1. For fields the user supplied **and that can be reliably compared to available candidate metadata**, count exact normalized equality matches. Normalization: NFKC, casefold, trim and collapse whitespace; keep diacritics. For a field absent from candidate data, award no match and do not infer one.
2. Sort by **descending number of exact field matches**.
3. Among ties, prioritize exact `release_title` and then `artist` equality where both input and comparable metadata exist; next exact `year` equality.
4. Final tie-breaker: ascending numeric Master ID.

This ranking has no influence on classification. Do not use fuzzy distance or AI and do not automatically choose the first candidate. Where artist metadata cannot reliably be compared from a search result, fetch Master details only if needed for ranking and cache those reads. Document API field mapping in tests before coding.

## Summary formatting

Always show `OK` first, then `NOT_FOUND`, `MULTIPLE`, and `ERROR` if applicable. Every result includes its original 1-based input index, original query JSON, and a per-type status for every selected search. `MULTIPLE` shows unique Master count plus up to three Master URLs. Group order is fixed; within a group input order is fixed.

The JSON export annotates only `OK` records with their resolved `master_id`; unresolved records are copied from the original input. `master_id` is metadata, is ignored when constructing API search parameters, and never overrides a later search result.

## API snapshot behavior

For byte-for-byte reproducible summaries, support fixed response snapshots and avoid adding runtime timestamps to deterministic summary text. Live search results are not guaranteed invariant as Discogs is editable.
