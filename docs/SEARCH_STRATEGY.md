# Discogs search contract

## Query construction

Each `records[i]` dictionary is passed unchanged to the primary `GET /database/search` with application-managed `type=master`, `page`, and `per_page`. If—and only if—the complete primary search returns zero unique Masters, run a second search with the same user parameters and `type=release`; this is the album/release fallback. Pagination can require several HTTP requests in either search. Reject unknown keys using the currently documented API parameter allowlist (e.g. `q`, `artist`, `release_title`, `title`, `year`, `genre`, `style`, `country`, `format`, `label`, `catno`, `barcode`, `track`, `credit`, `anv`, `submitter`, `contributor`, `type`). API documentation must be checked for current validity during implementation. Do not modify user fields; only the internal `type` differs for the fallback.

## Exhaustiveness

Request all result pages for each required search and deduplicate by numeric resource ID. Prefer the search response pagination total as a consistency check, not as a substitute for successful retrieval. Reject unexpected resource types, malformed IDs, or truncated responses as `ERROR`. If configurable result/page caps are reached, label incomplete (not `MULTIPLE` by default), unless the product explicitly revises the classification contract. Avoid retry loops without bounds; respect 429/Retry-After and stable retry policy. Do not start the release fallback when the Master search is incomplete or returns any Master IDs.

Every live HTTP attempt, including pagination and retries, is spaced at least 1.25 seconds apart per client. A lower `X-Discogs-Ratelimit` increases the spacing; when `X-Discogs-Ratelimit-Remaining` is at most five, the client slows down further, waiting 60 seconds when it reaches zero. On HTTP 429, honor `Retry-After` (seconds or HTTP date); if absent or invalid, wait 60 seconds. At most three retries are made by default. A server-requested wait over 300 seconds is reported as an error rather than retried early, and the cooldown remains in effect for later searches. Snapshots do not consume the network rate limit.

## Classification

- `0` Master IDs => `NOT_FOUND`
- `1` Master ID => `OK`, irrespective of whether the search matched the user's intended album. The user owns the query's specificity.
- `>=2` Master IDs => `MULTIPLE`; no auto-pick.
- Any incomplete/failed search => `ERROR`.

These counts apply only to Master IDs. After zero Masters, release IDs from the album fallback remain diagnostic: the result stays `NOT_FOUND`, and those IDs cannot be exported or published as Masters. A failure in the required fallback is `ERROR`.

## Top-three display ranking

The user requested the **three best** candidates. Search API relevance ordering is not a reproducible contract and may change, so BeatBee uses the following stable, display-only rules:

1. For fields the user supplied **and that can be reliably compared to available candidate metadata**, count exact normalized equality matches. Normalization: NFKC, casefold, trim and collapse whitespace; keep diacritics. For a field absent from candidate data, award no match and do not infer one.
2. Sort by **descending number of exact field matches**.
3. Among ties, prioritize exact `release_title` and then `artist` equality where both input and comparable metadata exist; next exact `year` equality.
4. Final tie-breaker: ascending numeric Master ID.

This ranking has no influence on classification. Do not use fuzzy distance or AI and do not automatically choose the first candidate. Where artist metadata cannot reliably be compared from a search result, fetch Master details only if needed for ranking and cache those reads. Document API field mapping in tests before coding.

Release/album fallback results are not Master candidates and are not ranked by this rule. Report the total number of distinct releases and up to three links in ascending numeric release-ID order; these links are diagnostic only.

## Summary formatting

Always show `OK` first, then `NOT_FOUND`, `MULTIPLE`, and `ERROR` if applicable. Every result includes its original 1-based input index and original query JSON. `MULTIPLE` shows unique result count plus up to three Master URLs. `NOT_FOUND` indicates zero Masters and may include the release fallback count and up to three release URLs. Group order is fixed; within a group input order is fixed.

## API snapshot behavior

For byte-for-byte reproducible summaries, support fixed response snapshots and avoid adding runtime timestamps to deterministic summary text. Live search results are not guaranteed invariant as Discogs is editable.
