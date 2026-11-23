# BeatBee Interactive Web Application

## Overview

The BeatBee Web Application keeps the existing Python Core initial search and adds a Web-only interactive resolution workflow. It allows users to:

- Paste or edit JSON search configurations
- Validate searches against the Discogs API
- Review every unresolved position together in one nIO section
- Edit and search each unresolved position independently
- Select and explicitly confirm one Master, Release, Artist, or Label result
- Sort the combined automatic/manual iO table
- Download a Web-specific JSON export
- Export combined results as a ZIP file

## Running the Web Server

### Quick Start

```bash
python web.py
```

The server will start at `http://localhost:5000/`.

### Advanced Options

```bash
python web.py --port 8080 --host 0.0.0.0 --debug
```

Options:
- `--port PORT` - Bind to port (default: 5000)
- `--host HOST` - Bind to host (default: localhost)
- `--debug` - Enable Flask debug mode

Alternatively, use the CLI:

```bash
python main.py web --port 8080
```

## User Interface

### Input & Control Panel

**JSON List Definition**
- Paste or edit your JSON search configuration
- Must include `list_name` and `records` array
- Each record is a Discogs search parameter dictionary; `type` defaults to `master` and may be a value or a list of `master`, `release`, `artist`, and `label`

**Actions:**
- **Load JSON** - Parse and validate the input
- **Validate & Search** - Run the initial search through the existing Python Core
- **Reset** - Restore to original loaded JSON
- **Download JSON** - Export confirmed Web state; unresolved records remain original
- **Download All (ZIP)** - Save JSON and results

### Validation Status Panel

Shows:
- **Status Box** - Validation status messages
- **Summary Cards** - Core status counts plus live automatic iO, manual iO, and open nIO counts; manual confirmation does not rewrite Core statuses
- **nIO** - One combined section for all unresolved positions, regardless of technical status
- Each nIO panel shows the original record, technical status, editable search fields, selected resource types, search results, radio selection, and confirmation action

### Resolved Results Table

- Contains automatic Master results and manually confirmed results
- Displays original position, Artist/Name, Title, Year, resource type, Discogs ID, and URL
- Defaults to original input order; sorting never changes export order
- Click "View" to open Discogs page

## Workflow

1. **Prepare JSON**
   - Create or edit `discogsList.json`
   - Define list name and search records

2. **Load & Validate**
   - Open web interface
   - Paste JSON or use example
   - Click "Load JSON"
   - Click "Validate & Search"

3. **Review Results**
   - View summary statistics
   - Review all unresolved records together in nIO
   - See automatic Master results in the combined iO table

4. **Edit & Retry** (Optional)
   - Edit the search parameters inside one unresolved position's panel
   - Choose one or more of Master, Release, Artist, or Label
   - Click **Search**; the Web layer makes one separate paginated search per selected type
   - Browse every result, select exactly one with its radio button, then click **Confirm Selection**
   - Manual confirmation moves that position to iO without changing the Core technical classification
   - A new search clears only that position's unconfirmed selection; it does not overwrite a prior confirmation

5. **Save & Export**
   - **Download JSON** - Automatically resolved records retain their original query and get `master_id`; manually confirmed records use the confirmed query, one string `type`, and a `selected_result` reference; unresolved records remain unchanged
   - **Download All (ZIP)** - Get JSON + summary in one file

## REST API

The web server provides a JSON API for programmatic access:

### POST /api/load
Load and validate a JSON document.

Request:
```json
{
  "list_name": "Example",
  "records": [{"artist": "Test"}]
}
```

Response:
```json
{
  "status": "ok",
  "list_name": "Example"
}
```

### POST /api/validate
Run the initial validation and search through the existing Core.

Response:
```json
{
  "list_name": "Example",
  "total": 1,
  "all_ok": true,
  "counts": {"OK": 1, "NOT_FOUND": 0, "MULTIPLE": 0},
  "results": [...],
  "resolved": [...]
}
```

### POST /api/reset
Reset to original input.

### GET /api/state
Return the combined nIO positions and iO table. Optional `sort_by` values are `position`, `artist`, `title`, `year`, `resource_type`, or `resource_id`; `direction` is `asc` or `desc`.

### POST /api/record/search
Search one input position independently. The request contains `record_index`, editable `params`, and a nonempty `search_types` array. The response includes the first page; all results remain available through the pagination route.

### GET /api/record/results
Get a result page for one position using `record_index` and `page` query parameters.

### POST /api/record/select
Save the selected `resource_type` and `resource_id` for one position. The result must belong to that position's latest search.

### POST /api/record/confirm
Explicitly confirm the selected result and move the position from nIO to iO.

### GET /api/download/json
Download the Web-specific JSON export. It is allowed while nIO records remain.

### GET /api/download/zip
Download JSON and summary as ZIP.

## Architecture

### Session Management (`web_server.py`)

`InteractiveSessionManager` manages the state of a validation session:

- Preserves original input separately from each position's draft
- Stores selected resource types, complete latest search results, radio selection, and confirmed result independently per position
- Removes `selected_result` Web metadata from the validation copy before passing input to the Core

### Flask Application (`web_app.py`)

`create_app()` creates a Flask application with:

- HTML interface template
- REST API endpoints
- File download handlers
- ZIP export functionality

### Key Design Decisions

1. **Per-browser state** - A signed Flask session cookie references a server-side `InteractiveSessionManager`; users do not share mutable workflow state
2. **No Database** - State is in memory and is lost when the server restarts
3. **Local-First** - Server runs locally by default for security and simplicity
4. **Preserved Order** - Original JSON record order is maintained in exports regardless of table sorting
5. **Explicit manual choice** - The Web layer confirms one result; it never changes the Python Core classification

## Features

### Complete Discogs Integration
- Uses existing BeatBee Discogs client
- Respects rate limits and retry behavior
- Supports all validated search parameters
- Pagination handled transparently

### Interactive Resolution
- One combined nIO list with independent per-position editing
- Sequential one-per-type paginated searches using the existing search adapter
- Complete result lists with Web pagination
- Radio selection and explicit confirmation for all four resource types
- Combined iO table for automatic and manual results, with stable sorting

### Result Export
- JSON preserves original positions, duplicates, and order
- Automatic results include `master_id`; manual results include one selected `type` and `selected_result`
- Unresolved records are copied unchanged; unconfirmed drafts are excluded
- ZIP package for easy sharing

### Responsive Design
- Mobile-friendly interface
- Works in modern browsers
- Real-time validation feedback
- Progress indicators for long searches

## Limitations and Notes

### No Publishing from Web UI
- Publication to Discogs is not implemented
- Download manifest and import manually to Discogs
- Use `python main.py export` for manifest-only export

### No Persistent Storage
- Session data is not saved to disk and is lost on server restart
- Browser refresh retains state while the server process and its signed session cookie remain available
- Multiple worker processes do not share this in-memory state

### Local Server Only (Default)
- Default configuration binds to localhost
- Not suitable for untrusted network without authentication
- Token management handled via environment or file
- Do not expose the development server to an untrusted network; add authentication and shared server-side session storage before remote deployment

### Browser Compatibility
- Requires modern browser with fetch API
- JavaScript must be enabled
- Tested on Chrome, Firefox, Safari, Edge

## Troubleshooting

### "No module named 'flask'"
Install Flask:
```bash
pip install flask
```

### "DISCOGS_TOKEN unavailable"
Set token via environment variable or file:
```bash
$env:DISCOGS_TOKEN = "your_token_here"
python web.py
```

### Server won't start on port 5000
Port already in use. Try different port:
```bash
python web.py --port 8080
```

### Results not showing after validation
- Check browser console for errors (F12)
- Ensure Discogs API is accessible
- Check rate limit status
- Verify JSON is valid (reload if unsure)

## Development

### Running Tests
```bash
$env:PYTHONPATH = "src"
python -m pytest tests/test_web_app.py -v
```

### File Structure
```
src/beatbee/
  web_server.py        - Session management
  web_app.py          - Flask application and routes
  cli.py              - CLI integration with 'web' command
```

### Adding Features
1. Update `InteractiveSessionManager` for backend logic
2. Add API endpoint in `create_app()`
3. Update HTML/JavaScript in `TEMPLATE`
4. Add tests in `tests/test_web_app.py`
5. Run all tests: `python -m pytest tests/ -v`

## See Also

- [SPEC.md](../SPEC.md) - Core specification
- [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) - System architecture
- [docs/WEB_APP.md](../docs/WEB_APP.md) - Original web app specification
- [README.md](../README.md) - Main project documentation
