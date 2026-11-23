# BeatBee — normative specification

## Product goal

Create a named Discogs user list from an ordered array of user-authored search queries. Search Masters first and use a release/album search only when the complete Master search finds none. No recommendation, fuzzy matching, query refinement, interactive resolution, or implicit selection.

## Input contract

```json
{
  "list_name": "A 100 legfontosabb magyar lemez",
  "records": [
    {"artist": "Omega", "release_title": "10000 lépés", "year": "1969"},
    {"artist": "Syrius", "release_title": "Az ördög álarcosbálja"}
  ]
}
```

- `list_name`: nonempty Unicode string, preserved exactly.
- `records`: nonempty ordered array; each element is a nonempty object mapping **supported Discogs Database Search parameters** to their supported scalar values, except `type`, which may be an array. No external `position`, `status`, `weight`, or `params` wrapper.
- `type` may be omitted (default `master`), supplied as one resource type, or as a nonempty array of resource types: `master`, `release`, `artist`, and `label`. Each selected type is searched independently with pagination; when selected, `master` is searched first.
- `master_id` is optional export metadata. It is validated as a positive integer and never used to choose or override a search result.
- `page` and `per_page` are reserved for the application, not accepted inside a record.
- Unknown keys, invalid values, malformed JSON and empty queries are input errors, never silently dropped.
- The input JSON is immutable; the user edits it between runs. Record order and duplicate input positions are retained.

## Execute

1. Validate the entire input before API calls.
2. For **every** element, run one paginated Discogs Database Search per selected `type`. If `master` is selected, search it first. When no `type` is specified, search `master`.
3. Aggregate unique Master IDs from selected Master results and, when `release` was explicitly selected, valid associated `master_id` values in the release results. Artist and label results are diagnostic only. If a selected Master search completes with zero IDs, the existing automatic `type=release` fallback still runs; fallback results remain diagnostic and cannot qualify an element. Never run the fallback after a Master search error or when one or more Masters were found.
4. Classify the element **only after all selected type searches and any required fallback complete successfully**:
   - `OK`: exactly one unique Master ID.
   - `NOT_FOUND`: zero unique Master IDs. Artist/label results, unassociated releases, and automatic fallback releases are diagnostic only.
   - `MULTIPLE`: more than one unique Master ID.
   - `ERROR`: timeout, rate limit exhaustion, incomplete pagination, malformed API response, or unverified completeness in either required search.
5. Always produce a full summary, grouped in this order: `OK`, `NOT_FOUND`, `MULTIPLE`, `ERROR` (only when errors exist). Preserve original positions within groups.
6. `MULTIPLE` displays total unique Master count and three best candidates (or all if only two), each with Master ID, title, year if available, and clickable URL. Ranking is deterministic, documented in SEARCH_STRATEGY.md, and is **display-only**. `NOT_FOUND` may show up to three deterministic release/album fallback links, never as Master candidates.
7. If any selected type search is incomplete or fails, classify the element as `ERROR`. If any element is not `OK`, terminate with a nonzero code. No publishing side effects. Automatic fallback release results never qualify an element as `OK` or enter a Master manifest.
8. If all are `OK`, produce an ordered Master manifest and proceed to the publishing interface. Never claim success unless Discogs confirms the list was created and its contents verified.

## User-driven resolution loop

The user opens the input JSON, changes parameters or the selected `type` values for `NOT_FOUND` or `MULTIPLE`, saves, and restarts. The web editor offers the resource types as checkboxes and searches each selected type. BeatBee never selects a Master automatically or stores manual master-selection overrides. JSON export adds `master_id` only to `OK` records; unresolved records retain their original JSON. The automatic `type=release` fallback remains application-controlled and diagnostic only.

## Determinism

Given identical input, settings, and a fixed snapshot of API responses, produce identical grouping, candidate order, manifest order, and textual summary. Use stable tie breakers; do not depend on API ordering. Live Discogs search can change over time; record response timestamps and support snapshots for reproducibility.

## Publishing gate

`all(records) are OK` is necessary but not sufficient for a successful publication. Publishing must also be supported by a **verified** mechanism, use authenticated account ownership, avoid silently creating duplicates, and confirm actual persisted ordered Master IDs. Preserve list title and order. Publishing is a separately gated integration (see PUBLISHING.md).

## Commands

- `beatbee validate <input.json>`: search, write an HTML summary, never publish. Exit `0` iff all records are OK; otherwise nonzero.
- `beatbee run <input.json>`: search and summarize; publish only after all OK and a verified publisher has been configured; otherwise report unavailable / fail safely.

Recommended exit codes: `0` success, `1` unresolved search(es), `2` invalid input, `3` search/API incomplete or failed, `4` publishing failed/unavailable. If multiple failure types apply, use a documented stable priority, while showing all errors.

## Output contracts

- Human-readable HTML summary beside the input, including list name, total count, group counts, status, and per-entry results. The terminal reports its path and search progress.
- Machine-readable summary JSON embedded in the HTML and ordered Master manifest embedded on successful validation.
- Store source index and original query for every result.
- No fabricated Master IDs, metadata, or URLs.

## Acceptance tests

- `0`, `1`, and `>1` unique Master IDs; duplicate results across pages; fallback only after a complete zero-Master search.
- All records checked even after early failures; grouped summary and input positions.
- `MULTIPLE` top three stable across shuffled API response order; no auto-selection.
- Invalid keys/`type`, Unicode, empty lists, duplicate input entries; omitted `type` defaults to `master`, and multiple types run independently.
- A selected release result contributes only its valid associated Master ID; an automatic fallback release never qualifies an item.
- Every selected type search completes before classification; any selected-type failure remains `ERROR`.
- API errors/incomplete pages in either required search never map to `NOT_FOUND` or `OK`; fallback releases never become Master IDs or pass the publish gate.
- No publish invoked if any non-OK result; input state is not mutated. JSON export adds Master IDs only to resolved records and preserves unresolved records as originally supplied.
- Exactly one found Master is classified `OK` **without semantic title/year verification** (intentional product rule).
- Publishing unavailability never reports success.
