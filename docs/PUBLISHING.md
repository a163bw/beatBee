# Publishing a Discogs user list — feasibility gate

## User goal

Create a named list **inside the user's Discogs account**, with an ordered entry for each resolved Master ID.

## Known limitation

Current publicly documented Discogs User Lists API resources provide list-reading operations, but no confirmed supported endpoint for creating/editing a user list. **Do not invent a POST endpoint** or treat collection folders/wantlists as Discogs user lists. Verify again against official up-to-date documentation before implementation.

## Required feasibility spike

1. Verify a documented, supported creation/edit path for Discogs user lists and whether it accepts **Master** IDs (not only release IDs).
2. Verify authentication requirements, ordering, title, duplicate handling, and list contents readback.
3. If a supported API is not available, assess whether browser-driven creation is permitted and stable under Discogs terms and site behavior; no account credentials in source or logs.
4. Document evidence and a small throwaway test outcome. Until completed, publisher must be disabled by default.
5. If no permitted reliable automation method exists, output a full ordered manifest and clear manual-publication instructions. Never label export as published.

## Safety / idempotency

- Never publish on failed/incomplete search validation.
- Avoid accidental duplicate lists on reruns: require explicit confirmation or a verified idempotency/reconciliation mechanism before any remote write.
- Never overwrite or mutate an existing user list implicitly.
- Verify remote list title, item count, Master IDs and order, then report published URL or a hard failure.
- If full verification is not possible, report partial/unverified state, not success.

## Implementation boundary

`Publisher.publish(list_name, ordered_master_ids)` is a separate port behind a capability/feature gate. Initially implement `ManifestExporter`, not a fake API writer. Automated publishing is an explicit later milestone, dependent on verified technical feasibility.
