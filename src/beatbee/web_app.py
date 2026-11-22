"""Flask application for interactive BeatBee web interface."""

import json
import logging
from pathlib import Path
from typing import Any

from flask import Flask, render_template_string, request, jsonify

from .web_server import InteractiveSessionManager
from .search import FakeSearchAdapter, SearchOutcome
from .discogs_client import DiscogsSearchClient


logger = logging.getLogger(__name__)


# HTML template for the interactive interface
TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BeatBee - Interactive Discogs Master List Builder</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }
        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }
        header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        .content {
            padding: 40px;
            display: flex;
            flex-direction: column;
            gap: 40px;
        }
        .panel {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 24px;
        }
        .panel h2 {
            margin-bottom: 20px;
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
        }
        input[type="text"],
        textarea,
        select {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 1em;
            font-family: 'Monaco', 'Courier New', monospace;
        }
        textarea {
            min-height: 300px;
            resize: vertical;
        }
        .button-group {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 1em;
            font-weight: 600;
            transition: transform 0.2s, box-shadow 0.2s;
            flex: 1;
            min-width: 150px;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 16px rgba(102, 126, 234, 0.4);
        }
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        .btn-secondary {
            background: #6c757d;
        }
        .progress-container {
            display: none;
            margin-top: 20px;
        }
        .progress-bar {
            width: 100%;
            height: 25px;
            background: #e0e0e0;
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 10px;
        }
        .progress-bar-fill {
            height: 100%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            width: 0%;
            transition: width 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 0.8em;
            font-weight: 600;
        }
        .progress-text {
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }
        .status-box {
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 16px;
            border-radius: 4px;
            margin-bottom: 20px;
        }
        .status-ok { border-left-color: #28a745; }
        .status-error { border-left-color: #dc3545; }
        .status-warning { border-left-color: #ffc107; }
        .results-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        .results-table th,
        .results-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        .results-table th {
            background: #f8f9fa;
            font-weight: 600;
        }
        .results-table tr:hover {
            background: #f8f9fa;
        }
        .master-link {
            color: #667eea;
            text-decoration: none;
        }
        .master-link:hover {
            text-decoration: underline;
        }
        .summary-section {
            margin-top: 30px;
        }
        .summary-cards {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }
        .summary-card {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            text-align: center;
        }
        .summary-card .value {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }
        .summary-card .label {
            font-size: 0.9em;
            color: #666;
            margin-top: 5px;
        }
        .results-group {
            margin-bottom: 30px;
        }
        .results-group h3 {
            color: #667eea;
            margin-bottom: 15px;
            padding: 10px 0;
            border-bottom: 1px solid #ddd;
        }
        .result-item {
            background: #f8f9fa;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 4px;
            border-left: 4px solid #ddd;
        }
        .result-item.ok { border-left-color: #28a745; }
        .result-item.not-found { border-left-color: #ffc107; }
        .result-item.multiple { border-left-color: #17a2b8; }
        .result-item.error { border-left-color: #dc3545; }
        @media (max-width: 1024px) {
            .summary-cards {
                grid-template-columns: repeat(2, 1fr);
            }
            button {
                flex: none;
                min-width: auto;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🐝 BeatBee</h1>
            <p>Build curated Discogs Master lists interactively</p>
        </header>

        <div class="content">
            <!-- Input & Control Panel - First -->
            <div class="panel">
                <h2>Input & Control</h2>
                
                <div class="form-group">
                    <label for="json-input">JSON List Definition</label>
                    <textarea id="json-input" placeholder="Paste or edit your JSON here..."></textarea>
                </div>

                <div class="button-group">
                    <button onclick="loadJSON()">Load JSON</button>
                    <button onclick="validateAndSearch()" class="btn-secondary">Validate & Search</button>
                    <button onclick="resetInput()" class="btn-secondary">Reset</button>
                    <button onclick="downloadJSON()" class="btn-secondary">Download JSON</button>
                    <button onclick="downloadAll()" class="btn-secondary">Download All (ZIP)</button>
                </div>

                <!-- Progress Bar -->
                <div class="progress-container" id="progress-container">
                    <div class="progress-bar">
                        <div class="progress-bar-fill" id="progress-fill">0%</div>
                    </div>
                    <div class="progress-text" id="progress-text">Searching...</div>
                </div>
            </div>

            <!-- Validation Status Panel -->
            <div class="panel" id="validation-panel" style="display: none;">
                <h2>Validation Status</h2>
                <div id="status-box" class="status-box" style="display: none;"></div>
                
                <div class="summary-section">
                    <div id="summary-cards" class="summary-cards" style="display: none;"></div>
                    <div id="results-container"></div>
                </div>
            </div>

            <!-- Resolved Results Panel -->
            <div class="panel" id="resolved-panel" style="display: none;">
                <h2>Resolved Results</h2>
                <table class="results-table" id="resolved-table">
                    <thead>
                        <tr>
                            <th>Position</th>
                            <th>Master ID</th>
                            <th>Title</th>
                            <th>Artist</th>
                            <th>Year</th>
                            <th>Discogs Link</th>
                        </tr>
                    </thead>
                    <tbody id="resolved-tbody"></tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        // Load example JSON on page load
        window.addEventListener('load', () => {
            const example = {
                "list_name": "Example Collection",
                "records": [
                    {"artist": "Gábor Szabó", "release_title": "Dreams", "year": "1968"},
                    {"artist": "Omega", "release_title": "10000 lépés", "year": "1969"}
                ]
            };
            document.getElementById('json-input').value = JSON.stringify(example, null, 2);
        });

        async function loadJSON() {
            const input = document.getElementById('json-input').value;
            try {
                const doc = JSON.parse(input);
                const response = await fetch('/api/load', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(doc)
                });
                const result = await response.json();
                if (result.status === 'ok') {
                    showStatus('List loaded successfully', 'status-ok');
                } else {
                    showStatus(result.message || 'Error loading list', 'status-error');
                }
            } catch (e) {
                showStatus('Invalid JSON: ' + e.message, 'status-error');
            }
        }

        function showProgress(percentage, text) {
            const container = document.getElementById('progress-container');
            const fill = document.getElementById('progress-fill');
            const progressText = document.getElementById('progress-text');
            
            container.style.display = 'block';
            fill.style.width = percentage + '%';
            fill.textContent = percentage + '%';
            progressText.textContent = text;
        }

        function hideProgress() {
            const container = document.getElementById('progress-container');
            container.style.display = 'none';
        }

        async function validateAndSearch() {
            const buttons = document.querySelectorAll('button');
            buttons.forEach(b => b.disabled = true);
            
            showProgress(0, 'Starting search...');
            
            try {
                const response = await fetch('/api/validate', { method: 'POST' });
                const result = await response.json();
                
                if (result.status === 'error') {
                    showStatus(result.message, 'status-error');
                    hideProgress();
                    buttons.forEach(b => b.disabled = false);
                    return;
                }

                // Simulate progress updates (in a real scenario, this would come from the server)
                for (let i = 0; i < 100; i += 20) {
                    showProgress(i, `Processing ${i}%...`);
                    await new Promise(resolve => setTimeout(resolve, 100));
                }
                
                showProgress(100, 'Complete!');
                await new Promise(resolve => setTimeout(resolve, 300));

                displaySummary(result);
                displayResults(result);
                displayResolvedTable(result.resolved || []);
                hideProgress();
            } catch (e) {
                showStatus('Search failed: ' + e.message, 'status-error');
                hideProgress();
            } finally {
                buttons.forEach(b => b.disabled = false);
            }
        }

        async function resetInput() {
            const response = await fetch('/api/reset', { method: 'POST' });
            const result = await response.json();
            showStatus(result.message, result.status === 'ok' ? 'status-ok' : 'status-error');
            document.getElementById('validation-panel').style.display = 'none';
            document.getElementById('resolved-panel').style.display = 'none';
            document.getElementById('status-box').style.display = 'none';
            document.getElementById('summary-cards').style.display = 'none';
            document.getElementById('results-container').innerHTML = '';
            hideProgress();
        }

        async function downloadJSON() {
            const response = await fetch('/api/download/json');
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'beatbee-list.json';
            a.click();
            URL.revokeObjectURL(url);
        }

        async function downloadAll() {
            const response = await fetch('/api/download/zip');
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'beatbee-results.zip';
            a.click();
            URL.revokeObjectURL(url);
        }

        function showStatus(message, className) {
            const box = document.getElementById('status-box');
            const panel = document.getElementById('validation-panel');
            box.className = 'status-box ' + className;
            box.textContent = message;
            box.style.display = 'block';
            panel.style.display = 'block';
        }

        function displaySummary(summary) {
            const counts = summary.counts || {};
            const cards = document.getElementById('summary-cards');
            cards.innerHTML = `
                <div class="summary-card">
                    <div class="value">${summary.total}</div>
                    <div class="label">Total</div>
                </div>
                <div class="summary-card">
                    <div class="value">${counts.OK || 0}</div>
                    <div class="label">OK</div>
                </div>
                <div class="summary-card">
                    <div class="value">${counts.NOT_FOUND || 0}</div>
                    <div class="label">Not Found</div>
                </div>
                <div class="summary-card">
                    <div class="value">${counts.MULTIPLE || 0}</div>
                    <div class="label">Multiple</div>
                </div>
            `;
            cards.style.display = 'grid';

            if (summary.all_ok) {
                showStatus('All records resolved successfully!', 'status-ok');
            } else {
                showStatus('Some records need attention', 'status-warning');
            }
        }

        function displayResults(summary) {
            const container = document.getElementById('results-container');
            if (!summary.results) {
                container.innerHTML = '';
                return;
            }

            const groups = { NOT_FOUND: [], MULTIPLE: [], ERROR: [] };
            summary.results.forEach(result => {
                // Skip OK results - only show problems
                if (result.status !== 'OK') {
                    groups[result.status] = groups[result.status] || [];
                    groups[result.status].push(result);
                }
            });

            let html = '';
            for (const [status, results] of Object.entries(groups)) {
                if (results.length === 0) continue;
                html += `<div class="results-group"><h3>${status} (${results.length})</h3>`;
                results.forEach(r => {
                    const statusClass = status.toLowerCase().replace('_', '-');
                    html += `<div class="result-item ${statusClass}">
                        <strong>Position #${r.position}</strong>
                        <pre>${JSON.stringify(r.query, null, 2)}</pre>`;
                    if (r.error) {
                        html += `<p><strong>Error:</strong> ${r.error}</p>`;
                    }
                    if (r.status === 'MULTIPLE') {
                        html += `<p>${r.master_ids.length} candidates found</p>`;
                    }
                    html += '</div>';
                });
                html += '</div>';
            }
            container.innerHTML = html;
        }

        function displayResolvedTable(resolved) {
            const tbody = document.getElementById('resolved-tbody');
            const panel = document.getElementById('resolved-panel');
            if (resolved.length === 0) {
                panel.style.display = 'none';
                return;
            }
            panel.style.display = 'block';
            tbody.innerHTML = resolved.map(r => `
                <tr>
                    <td>${r.position}</td>
                    <td>${r.master_id}</td>
                    <td>${r.title || 'N/A'}</td>
                    <td>${r.artist || 'N/A'}</td>
                    <td>${r.year || 'N/A'}</td>
                    <td><a href="https://www.discogs.com/master/${r.master_id}" target="_blank" class="master-link">View</a></td>
                </tr>
            `).join('');
        }
    </script>
</body>
</html>
"""


def create_app(adapter=None, token: str | None = None):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config['JSON_SORT_KEYS'] = False

    # Initialize session manager
    if adapter is None:
        if token:
            try:
                adapter = DiscogsSearchClient(token)
            except ValueError:
                adapter = FakeSearchAdapter()
        else:
            adapter = FakeSearchAdapter()

    manager = InteractiveSessionManager(adapter=adapter)

    @app.route('/')
    def index():
        """Serve the main interface."""
        return render_template_string(TEMPLATE)

    @app.route('/api/load', methods=['POST'])
    def api_load():
        """Load JSON input."""
        try:
            document = request.get_json()
            result = manager.load_input(document)
            return jsonify(result)
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    @app.route('/api/validate', methods=['POST'])
    def api_validate():
        """Validate and search."""
        try:
            summary_dict = manager.run_validation()
            if summary_dict is None:
                return jsonify({"status": "error", "message": "No session loaded"}), 400
            
            # Add resolved results
            summary_dict["resolved"] = manager.get_resolved_results()
            return jsonify(summary_dict)
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    @app.route('/api/reset', methods=['POST'])
    def api_reset():
        """Reset to original input."""
        try:
            result = manager.reset_to_original()
            return jsonify(result)
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    @app.route('/api/download/json')
    def api_download_json():
        """Download current JSON."""
        try:
            current = manager.get_current_input()
            if not current:
                return jsonify({"error": "No session loaded"}), 400
            
            response_data = json.dumps(current, ensure_ascii=False, indent=2).encode('utf-8')
            return response_data, 200, {
                'Content-Type': 'application/json',
                'Content-Disposition': 'attachment; filename=beatbee-list.json'
            }
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route('/api/download/zip')
    def api_download_zip():
        """Download JSON and HTML as ZIP."""
        try:
            import zipfile
            import io

            current = manager.get_current_input()
            if not current:
                return jsonify({"error": "No session loaded"}), 400

            summary = manager.get_summary()
            if not summary:
                return jsonify({"error": "Run validation first"}), 400

            # Create ZIP in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Add JSON
                json_content = json.dumps(current, ensure_ascii=False, indent=2)
                zf.writestr('beatbee-list.json', json_content)

                # Add HTML
                # Note: We need access to the full summary object to render HTML
                # For now, store summary dict as JSON
                summary_json = json.dumps(summary, ensure_ascii=False, indent=2)
                zf.writestr('beatbee-summary.json', summary_json)

            zip_buffer.seek(0)
            return zip_buffer.getvalue(), 200, {
                'Content-Type': 'application/zip',
                'Content-Disposition': 'attachment; filename=beatbee-results.zip'
            }
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    return app


def run_server(
    host: str = "localhost",
    port: int = 5000,
    adapter=None,
    token: str | None = None,
    debug: bool = False,
):
    """Run the Flask development server."""
    app = create_app(adapter=adapter, token=token)
    print(f"\nBeatBee Web Server running at http://{host}:{port}/")
    print(f"   Press Ctrl+C to stop.\n")
    app.run(host=host, port=port, debug=debug)
