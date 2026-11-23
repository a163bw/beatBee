# BeatBee Web — Streamlit Frontend Specification

**Status:** Proposed implementation specification  
**Target:** GitHub Copilot implementation  
**Scope:** Web interface only; the existing BeatBee Python core remains the source of truth.

## 1. Goal

BeatBee Web is a lightweight Streamlit interface for creating and checking named, manually curated Discogs lists. It calls the same Python core used by the BeatBee CLI. It does **not** implement its own search, result-classification, or publishing rules.

Core workflow:

```text
User provides a named JSON list
    → BeatBee Core validates each query
    → Discogs Master searches run for all list items
    → Results are grouped in a summary
    → Any NOT_FOUND / MULTIPLE / ERROR? Show report and STOP
    → All OK? List is eligible for publishing
    → User explicitly confirms publication
    → Verified publisher implementation (only if supported)
```

The user resolves `NOT_FOUND` and `MULTIPLE` by manually changing the **input JSON**, then running validation again. BeatBee must never rewrite search parameters or pick a Master automatically from multiple results.

## 2. Boundaries and responsibilities

| Component | Responsible for | Must not do |
| --- | --- | --- |
| Streamlit UI | Input upload/editor, buttons, status display, links, downloads, publication confirmation | Call Discogs search endpoints directly; decide matches; change user queries |
| BeatBee Core | Schema validation, Discogs client, complete searches, deduplication, classification, deterministic candidate ordering, publishing gate | Depend on Streamlit |
| Publisher adapter | Publishing a validated ordered set of Master IDs by a verified supported mechanism | Invent undocumented Discogs write endpoints |

Both CLI and Web must call the same core functions and yield the same statuses for identical input and API response data.

## 3. Input contract

Use a JSON document with `list_name` and `records`. Every record is a dictionary of **Discogs Database Search API parameters**, not a free-text album description.

```json
{
  "list_name": "A 100 legfontosabb magyar lemez",
  "records": [
    {"artist": "Gábor Szabó", "release_title": "Dreams", "year": "1968"},
    {"artist": "Omega", "release_title": "10000 lépés", "year": "1969"}
  ]
}
```

- Default `type` to `master`; accept one or more of `master`, `release`, `artist`, and `label`. A selected release can contribute only a valid associated `master_id`; artist/label results are diagnostic.
- Reserve `page`, `per_page` and other client pagination controls for the core.
- Keep record order, string accents, input values, and duplicate list positions intact.
- Invalid JSON / unknown parameters produce clear validation errors **without issuing searches**.
- Support `.json` upload and an optional editable JSON text area. The text area is an **explicit user edit surface**: changes occur only when the user types them. Never apply inferred corrections or silently save edits back to an uploaded file.
- Provide a JSON export that adds `master_id` only to resolved records and preserves original JSON for unresolved records. The live input remains unchanged.

## 4. Screens and interaction

### 4.1 Header

- Product name: **BeatBee**
- Subtitle: **Build curated Discogs Master lists**
- Short explanation: one search-query dictionary per list element; each query must resolve to exactly one Master.

### 4.2 Input panel

- Upload a `.json` file or paste/edit JSON.
- Show and preserve `list_name` and record count after parsing.
- Primary action: **Validate list**.
- Optional action: **Download JSON + Master IDs**.
- Validation button is disabled while a run is active; guard against double submissions.

### 4.3 Progress

- Show progress for completed queries out of the total; optional current item index.
- Handle API rate limits and retries through the core, not in Streamlit.
- Do not declare success until all queries have been fully evaluated.

### 4.4 Summary

Always display the entire completed run, including all problems in one pass. Group **in this order**:

1. **OK** — exactly one unique Master Release; show input position, original query, Master title, Master ID and clickable Master URL.
2. **NOT_FOUND** — zero unique Masters; show input position and original query.
3. **MULTIPLE** — more than one unique Master; show the total count and **up to three best candidates**, each with title, year when available, Master ID and clickable Discogs URL. Ranking rules come exclusively from the core and must be deterministic. These links are suggestions, not clickable selection controls.
4. **ERROR** — technical/incomplete searches; show position and actionable diagnostic. Never misclassify an API failure as `NOT_FOUND`.

Also show a compact status bar: `Total`, `OK`, `NOT_FOUND`, `MULTIPLE`, `ERROR`, and overall `BLOCKED` / `READY_TO_PUBLISH`.

Within each group, retain original input order. Show the original index even though the summary is grouped.

### 4.5 Correction loop

When any item is not `OK`:

- Show **BLOCKED — no list published**.
- Do not show a functioning publish action.
- Tell the user to revise the JSON queries manually and click **Validate list** again.
- On any input edit, invalidate the previous validation result immediately. Never reuse a `READY_TO_PUBLISH` state for modified input.

### 4.6 Publishing panel

Only when **all** items have `OK` status:

- Show **READY_TO_PUBLISH** and the exact list name and record count.
- Display a publication preview with the ordered Master IDs/links.
- Require explicit confirmation by the user before any write operation.
- Enable publishing only when a **verified, tested** publisher adapter is available and the user is properly authenticated.
- If no supported publisher exists, show **Publishing not available** and offer a downloadable manifest of list name + ordered Master IDs; do **not** claim the list was created.
- Handle existing-list conflicts explicitly; never overwrite or create duplicates silently.

## 5. Search and validation rules (delegated to core)

- Execute one complete paginated search per selected resource type; `master` is the default and is searched first if selected.
- Use only the supplied search arguments plus the selected resource type and API controls.
- Search every selected type completely; deduplicate resource IDs per type and Master IDs across eligible Master results.
- Count Master IDs from selected Master results and associated Master IDs from explicitly selected release results: `0 → NOT_FOUND`; `1 → OK`; `>1 → MULTIPLE`.
- Artist/label results and automatic release-fallback results are diagnostic only.
- Failed, truncated or rate-limited searches that never complete → `ERROR`.
- Process **all** records before the global validation gate, rather than exiting after the first invalid result.
- `can_publish = records are nonempty AND every result is OK with a valid Master ID`.
- No fuzzy matching, automatic query refinement, automatic Master selection, user override table or in-app resolution wizard.

## 6. Suggested integration API (illustrative names)

The core owns these contracts; adapt names to existing modules rather than duplicate logic:

```python
# beatbee.web invokes functions from beatbee.core; functions remain UI-independent.
validate_input(document: dict) -> ValidatedList
search_all(validated_list: ValidatedList) -> SearchReport
can_publish(report: SearchReport) -> bool
build_manifest(report: SearchReport) -> PublicationManifest
```

The report should include immutable copies of the input positions/queries, grouped statuses, candidate counts, and the top-three display candidates. Store the full normalized result set only as needed for correct counting and validation; avoid unnecessary large session payloads.

## 7. Streamlit architecture and state

Suggested future implementation path:

```text
src/beatbee/
  core/                # headless rules and workflows (CLI and web share these)
  discogs/             # API client + publisher interface
  cli.py               # existing CLI interface
  web.py               # Streamlit entry point, UI only
```

Use `st.session_state` for the current editor text, a stable input hash, current report and transient UI state. A report is valid only for the exact input hash used to generate it. When a user edits JSON, clear the prior report and publishing eligibility.

Use `st.file_uploader`, `st.text_area` (or `st.code` for display), `st.button`, `st.progress`, `st.metric`, `st.expander`, `st.link_button` / Markdown hyperlinks, and `st.download_button`. These are UI suggestions; choose accessible components that work in the deployed Streamlit version.

Do not use global state to store per-user credentials or reports. Keep cross-user cached data separate from session-specific input.

## 8. Security and privacy

- Do not log Discogs tokens, passwords, session cookies or raw authorization headers.
- Do not store user tokens in Git, source files, public logs or downloadable reports.
- Never expose one user's input/report/token to another user's session.
- Validate upload size and JSON structure; do not execute uploaded content.
- Keep secrets in deployment secrets/environment variables, not in the repository.
- Decide the per-user Discogs authentication flow **before implementing account publishing**. A shared server token must never be used to publish into arbitrary user accounts.
- Review Discogs API terms, rate limits, and the feasibility/permission of the proposed publishing mechanism before deployment.

## 9. Deployment to Streamlit Community Cloud

A public GitHub repository can host a Streamlit app on Community Cloud within its current free-tier limits. Actual limits and terms must be checked at deployment time.

Recommended entry point: `src/beatbee/web.py` (or a thin root `app.py` that imports it). Declare dependencies in `pyproject.toml` or the deployment-supported requirements format and pin compatible versions. Configure the package so the Streamlit app can import the headless BeatBee core.

No server database is required for v0.1. Cache public Discogs responses carefully and avoid caching authorization-bearing responses across users. Treat persistence and shared multi-user accounts as future work.

**Publishing caveat:** Community Cloud hosts the web UI but does not supply a documented Discogs list-writing API. A browser-based workaround must not be assumed feasible or allowed. Until a publisher is verified, deploy validation + download functionality only.

## 10. Tests and acceptance criteria

Automate unit tests for the core and UI/integration tests with mocked Discogs responses. No live Discogs token required in CI.

Acceptance criteria:

1. The UI accepts the specified JSON input and preserves all query dictionaries and their order.
2. Invalid input prevents searches and shows specific errors.
3. One run processes all entries and displays a complete summary.
4. Summary order is `OK`, `NOT_FOUND`, `MULTIPLE`, then `ERROR` if needed.
5. `MULTIPLE` displays exactly `min(3, total_count)` deterministic candidates with working Master URLs.
6. No candidate-selection or automatic correction controls exist.
7. Any non-`OK` record blocks publishing.
8. Editing JSON invalidates a prior successful run.
9. Export retains the list name and original record order.
10. The Web UI and CLI use the same core classification and gating logic.
11. No publishing claim or write action exists without a verified publisher and explicit confirmation.
12. Different browser sessions cannot see each other's input or credentials.

## 11. Copilot implementation plan

**Phase W1 — UI skeleton:** Streamlit entry point, file upload/editor, input validation, list preview, download.

**Phase W2 — Validation integration:** Call real BeatBee core (with mocked API in tests), show progress, summary groups, top-three Master links, and errors.

**Phase W3 — State safety:** Input-hash invalidation, sessions, retries surfaced from core, tests for no accidental publication.

**Phase W4 — Publishing readiness:** All-OK preview and manifest download. Do **not** implement publishing until an adapter is verified.

**Phase W5 — Deployment:** Publish validation-only web app on Streamlit Community Cloud, confirm availability, resource limits, security, and logs.

**Phase W6 — Optional account publishing:** Only after an independently verified compliant Discogs publishing mechanism and per-user authorization design are available.

## 12. Open decisions

- Do users paste JSON only, upload only, or use both? **Recommendation: both.**
- What happens for a query with more results than can be fully paginated under reasonable limits? **Recommendation: ERROR / incomplete; never falsely OK.**
- What determines the three *best* Masters for arbitrary Discogs search fields? **Must be specified in core's deterministic ranking policy before implementation.** For fields that cannot be verified from returned metadata, never invent equality claims.
- Should publishing run from a public web server at all? **Unresolved** until the Discogs writing mechanism and authorization model are proven.
- How to handle duplicate input queries / duplicate Master IDs in the published list? **Preserve input entries; publishing behavior must be verified and documented.**

## 13. Out of scope for Web v0.1

- A separate web search algorithm or matching engine.
- An interactive candidate-selection workflow.
- AI/fuzzy matching or automatic query correction.
- User accounts, database-backed persistent projects, or collaborative editing.
- Unsupported Discogs write endpoints or unverified browser automation.
