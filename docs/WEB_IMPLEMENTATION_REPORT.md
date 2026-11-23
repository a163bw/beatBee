# BeatBee Interactive Web Application - Implementation Report

## Implementation Summary

The Flask web application now adds a Web-specific interactive resolution workflow while leaving the Python Core and CLI behavior unchanged. The initial search uses the Core; unresolved positions can then be searched independently, explicitly confirmed, sorted in a combined iO table, and exported without changing original record order.

## Implemented Files

### New Modules
1. **`src/beatbee/web_server.py`** (8305 characters)
   - `InteractiveSessionManager`: Manages per-browser workflow state
   - Keeps original records, drafts, selected types, full results, radio selection, and confirmed results separate per position
   - Performs single-position searches through the existing resource search adapter
   - Converts `SearchSummary` to JSON format for API responses

2. **`src/beatbee/web_app.py`** (20189 characters)
   - Flask application with HTML/CSS/JavaScript template
   - REST API endpoints for initial search, independent item searches, selection, confirmation, state, and download
   - ZIP export functionality
   - Responsive design with gradient styling

3. **`web.py`** (581 characters)
   - Standalone entry point for web server
   - Loads token from environment or file
   - Calls CLI with `web` command

4. **`tests/test_web_app.py`** (10219 characters)
   - Tests for item independence, multi-type searches, pagination, all manual resource types, sorting, export, metadata filtering, token redaction, and browser-session isolation

5. **`docs/WEB_INTERACTIVE.md`** (7169 characters)
   - Complete web app documentation
   - User workflow and instructions
   - REST API documentation
   - Architecture and design decisions
   - Troubleshooting guide

### Updated Files
1. **`src/beatbee/cli.py`**
   - New `web` subcommand added
   - `--host`, `--port`, `--debug` options
   - Routing for `web` command before input validation

2. **`pyproject.toml`**
   - Flask added as optional dependency
   - `[project.optional-dependencies]` section

3. **`docs/ROADMAP.md`**
   - Phase 7 (Interactive Web Application) documented
   - Implemented features listed
   - Known limitations noted

4. **`README.md`**
   - New "Interactive Web Application" section
   - Commands and options documented
   - Link to web app documentation

## Implemented Features

### Backend (Python)
- ✓ Session management for validation state
- ✓ JSON loading and validation
- ✓ Search execution via existing `SearchAdapter`
- ✓ Update search parameters per record
- ✓ Preserves original and edited state
- ✓ Reset to original
- ✓ Save results to file (JSON + HTML)
- ✓ Resolved results in "Resolved Results" table

### Frontend (Browser)
- ✓ Responsive HTML interface
- ✓ JSON editor with text area
- ✓ Load/Validate/Reset buttons
- ✓ Validation status display
- ✓ Summary statistics cards
- ✓ Live automatic/manual iO and open nIO counts after confirmation, separate from unchanged Core counts
- ✓ One combined nIO section, regardless of Core status
- ✓ Combined sortable iO table for automatic and manually confirmed results
- ✓ Independent per-record search and explicit radio-button confirmation
- ✓ Paginated access to complete interactive search results
- ✓ Download JSON
- ✓ Download ZIP archive

### REST API
- ✓ POST `/api/load` - Load JSON
- ✓ POST `/api/validate` - Validate & search
- ✓ POST `/api/reset` - Reset to original
- ✓ GET `/api/state` - Combined nIO/iO state with sorting
- ✓ POST `/api/record/search` - Search one position by selected resource types
- ✓ GET `/api/record/results` - Paginate that position's full results
- ✓ POST `/api/record/select` - Save one radio selection
- ✓ POST `/api/record/confirm` - Explicitly confirm and move to iO
- ✓ GET `/api/download/json` - Download JSON
- ✓ GET `/api/download/zip` - Download JSON + summary as ZIP

### Integration
- ✓ Uses existing `DiscogsSearchClient`
- ✓ Uses existing `ValidationError` handling
- ✓ Uses existing `SearchAdapter` protocol
- ✓ Uses existing `html_report.render_html_report()`
- ✓ Token management via environment/file

## Boundaries

1. **Server-based persistent storage**
   - State is held in memory and expires when the server process exits

2. **Publishing integration**
   - Already documented as future work
   - The Web UI does not publish to Discogs

3. **Remote multi-worker deployment**
   - The per-browser manager registry is process-local
   - Production deployment requires shared server-side session storage and authentication

## Tests

`tests/test_web_app.py` covers loading and initial Core search, independent drafts, per-type requests, complete paginated results, manual confirmation for each resource type, state movement, stable sorting, JSON export, metadata filtering, session isolation, and token redaction.

The focused web suite passes **30 tests and 4 subtests**. The complete project suite passes **94 tests and 30 subtests**.

## Test Run Results

```
94 passed, 30 subtests passed
```

## Usage

### Install Flask
```bash
pip install flask
```

### Start Web Server
```bash
python web.py
# or
python main.py web --port 5000
```

### Open in Browser
```
http://localhost:5000/
```

### Advanced Options
```bash
python main.py web --host 0.0.0.0 --port 8080 --debug
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (HTML/CSS/JS)                │
│  - JSON Editor                                          │
│  - Buttons: Load, Validate, Reset, Download             │
│  - Status Display & Results Table                       │
└──────────────────┬──────────────────────────────────────┘
                   │ HTTP/JSON
┌──────────────────▼──────────────────────────────────────┐
│                   Flask Web Server                       │
│  - GET /                      (HTML Interface)          │
│  - POST /api/load             (Load JSON)               │
│  - POST /api/validate         (Execute Search)          │
│  - POST /api/record/search    (Independent searches)    │
│  - POST /api/record/select    (Radio selection)         │
│  - POST /api/record/confirm   (Manual confirmation)     │
│  - GET /api/download/*        (Web JSON/ZIP export)     │
└──────────────────┬──────────────────────────────────────┘
                   │ Python
┌──────────────────▼──────────────────────────────────────┐
│          InteractiveSessionManager                       │
│  - Session State Management                             │
│  - Input Validation                                     │
│  - Search Execution                                     │
│  - File I/O                                             │
└──────────────────┬──────────────────────────────────────┘
                   │ Python
┌──────────────────▼──────────────────────────────────────┐
│          Existing BeatBee Core Modules                  │
│  - DiscogsSearchClient (Real API)                       │
│  - FakeSearchAdapter (Testing)                          │
│  - Validation, Service, Summary, etc.                   │
└──────────────────┬──────────────────────────────────────┘
                   │ HTTP (Discogs)
└──────────────────▼──────────────────────────────────────┘
            Discogs API
```

## Known Limitations

1. **No persistent storage**
   - Session data is held in process memory and is lost when the server restarts
   - Refreshing the page does not itself clear state while the cookie and process remain available

2. **Local server by default**
   - Standard binding to localhost
   - Not intended for untrusted networks
   - Would require authentication for remote deployment

3. **No publishing integration**
   - Manifest export available via CLI
   - Users import manually to Discogs

4. **Single-process session registry**
   - Browser sessions are isolated in one process
   - Multiple worker processes do not share this state

5. **Flask development server**
   - Not intended for production
   - For production: use Gunicorn/WSGI

## Future Enhancements

1. **Production deployment**
   - Gunicorn/WSGI support
   - Authentication for remote access
   - Shared server-side session storage

4. **Publishing integration**
   - After verified Discogs API
   - Account-based authorization

## Developer Notes

### Add Dependencies
Flask is already defined in `pyproject.toml` as an optional dependency:
```toml
[project.optional-dependencies]
web = ["flask>=2.0,<4.0"]
```

### Import Modules
```python
from beatbee.web_server import InteractiveSessionManager
from beatbee.web_app import create_app, run_server
```

### Extend Tests
```bash
# Single test file
python -m pytest tests/test_web_app.py -v

# Single test
python -m pytest tests/test_web_app.py::InteractiveSessionManagerTests::test_load_input_validates_document -v

# With coverage
python -m pytest tests/test_web_app.py --cov=beatbee
```

## Workflow and export guarantees

- The initial search remains the existing Core search.
- The interactive Web search makes one sequential adapter request per selected resource type and retains all returned candidates for pagination.
- A manual confirmation is Web-only and does not rewrite the Core status.
- Automatic records retain their original search parameters and gain `master_id`.
- Manually confirmed records contain confirmed parameters, exactly one string `type`, and a Web-only `selected_result` object with the selected type, ID, and URL.
- Unresolved records are copied from original input; unconfirmed drafts are never exported.
- Sorting affects only the displayed table, not exported record order.
- No automatic publishing is performed.
