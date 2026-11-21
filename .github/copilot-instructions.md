# Repository-wide Copilot instructions — BeatBee

Read `SPEC.md` before code changes. Consult `docs/SEARCH_STRATEGY.md` for searching and `docs/PUBLISHING.md` for user-list publication. `docs/DECISIONS.md` records accepted choices; do not silently reinterpret them.

**Essential invariants:** input is an ordered list of raw Discogs search parameter dictionaries; one logical API search per element, with pagination; enforce `type=master`; classify based solely on complete distinct Master ID count; generate a full grouped summary; display three ranked suggestions for MULTIPLE without choosing one; block publication on any non-OK; the user edits JSON externally and reruns; never mutate the input.

Do not implement fuzzy scoring, alias lookup, multi-stage search strategies, manual overrides, interactive resolvers, implicit candidate selection, or unsupported Discogs API endpoints. Publishing is a separate feature-gated integration. Never report a list published without remote confirmation.

Use Python 3.11+, src layout, type annotations, small pure functions, clear errors, bounded network operations, environment-based secrets, mocked network tests, and explicit dependency injection. Prefer standard library unless a dependency earns its complexity. Preserve Unicode. Never commit credentials.

Work incrementally following `docs/ROADMAP.md`. Before each feature, identify affected files, acceptance criteria and edge cases. After coding, run focused tests and report any limitations. Do not generate unrelated project scaffolding.
