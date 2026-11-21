# Publishing feasibility spike

Date: 2026-11-20

## Result

**No-Go for API publishing.** The Discogs API documentation and live read endpoints
verify User Lists only for reading. No verified, documented write endpoint is
available for creating a list, editing list metadata, or adding/removing items.

## Evidence

1. The official developer documentation dump documents:
   - `GET /users/{username}/lists`
   - `GET /lists/{list_id}`
2. The Live API accepts read requests:
   - `/users/example/lists` returned a valid paginated read response.
   - `/lists/1` returned a list and item data.
3. The documented List item types include releases and artists; no Master write
   contract is documented.
4. No supported create/edit/add/remove endpoint is documented for User Lists.

Sources:

- Official documentation dump: `https://raw.githubusercontent.com/wyattowalsh/discogs-api-spec/main/discogs-api-dev-docs.md`
- Live read endpoint: `https://api.discogs.com/users/example/lists`
- Live read endpoint: `https://api.discogs.com/lists/1`
- Official API terms: `https://support.discogs.com/hc/articles/360009334593-API-Terms-of-Use`

The GitHub dump is a documentation mirror, not a replacement for Discogs
documentation. The live endpoints provide corroborating API behavior, but a live
read endpoint does not establish write capability.

## Decision

- Keep `Publisher` disabled by default.
- Never invent `POST`, `PUT`, or `DELETE` endpoints for User Lists.
- Do not browser-automate Discogs list creation in this project.
- Export a complete ordered Master manifest for all-OK validation.
- Report publishing unavailable and return exit code 4.
- Revisit only if an official supported write contract appears and supports
  account ownership, duplicates, ordering, and readback verification.
