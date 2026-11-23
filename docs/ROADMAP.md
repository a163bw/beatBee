# Roadmap for Copilot

## Phase 0 — Specification review

Use `architect.agent.md`. Validate SPEC/SEARCH_STRATEGY/PUBLISHING consistency and resolve explicit open questions without generating code. Deliver a short plan with acceptance tests.

## Phase 1 — Input + CLI foundation

Implement strict JSON schema, `beatbee validate` entry point, input immutability, and tests. No real API calls yet. Provide a fake search adapter for testing.

## Phase 2 — Discogs search client

Implement authenticated requests, verified search params, `type=master`, complete pagination, deduplicated Master IDs, retry/rate-limits, and fixed snapshots. Test all failure paths with mocked responses.

## Phase 3 — Classification + summary

Implement all-entries execution, statuses, group order, top-three deterministic diagnostics, links, summary JSON and terminal output, and exit behavior.

## Phase 4 — Publishing gate + manifest

Implement pure all-OK predicate, ordered manifest export, `run` command, publisher port, and fail-safe unavailable state. Test that no publisher action occurs on non-OK entries.

## Phase 5 — Publishing feasibility research

Verify actual Discogs user-list write capability and account/ordering behavior. Do not write production publishing code until confirmed. Record evidence and decision.

## Phase 6 — Optional publisher

Only if Phase 5 confirms a permitted mechanism: implement authenticated creation, duplication protection, remote verification, failure recovery and tests. Otherwise keep manifest/manual workflow.

## Phase 7 — Interactive Web Application (IMPLEMENTED)

Implement local Flask web server with interactive browser interface for:
- JSON upload and editing
- Validation and search execution
- Review of unresolved entries (NOT_FOUND, MULTIPLE, ERROR)
- Editing search parameters and re-running searches
- Multi-selecting search resource types and exporting Master IDs only for resolved entries
- Table of resolved (OK) results
- JSON and HTML export
- ZIP archive download

Completed features:
- Local Python web server with Flask
- Interactive HTML/CSS/JavaScript interface
- Session management for validation state
- API endpoints for load, validate, reset, download
- File export (JSON, HTML, ZIP)
- 18 automated tests
- All 57 existing tests still passing

Limitations:
- No persistent storage (session data in memory)
- No publishing integration (use manifest export)
- Local server by default (security first)
- No multi-user support

At each phase: read current docs, write minimal code, add tests, run tests, summarize deviations. Use the reviewer agent for independent spec review.

