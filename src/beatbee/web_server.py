"""Local web server for interactive BeatBee validation and resolution."""

import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .models import SearchSummary, ResultStatus, SearchParams
from .search import SearchAdapter, FakeSearchAdapter, SearchOutcome
from .service import search_all
from .validation import validate_document, InputValidationError
from .html_report import render_html_report


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class InteractiveSession:
    """State of an interactive validation session."""
    original_input: dict[str, Any]
    current_input: dict[str, Any]
    summary: SearchSummary | None = None
    adapter: SearchAdapter | None = None
    resolved_count: int = 0
    is_valid: bool = False


class InteractiveSessionManager:
    """Manages interactive validation sessions."""

    def __init__(self, adapter: SearchAdapter | None = None):
        self.adapter = adapter or FakeSearchAdapter()
        self.session: InteractiveSession | None = None
        self.search_history: list[tuple[int, dict[str, Any]]] = []

    def load_input(self, document: dict[str, Any]) -> dict[str, str]:
        """Load and validate input document."""
        try:
            validated = validate_document(document)
            self.session = InteractiveSession(
                original_input=document,
                current_input=document,
                adapter=self.adapter,
                is_valid=True,
            )
            return {"status": "ok", "list_name": validated.list_name}
        except InputValidationError as exc:
            return {"status": "error", "message": str(exc)}

    def run_validation(self) -> dict[str, Any] | None:
        """Run validation on current input."""
        if not self.session or not self.session.is_valid:
            return None

        try:
            validated = validate_document(self.session.current_input)
            summary = search_all(validated, self.session.adapter)
            self.session = InteractiveSession(
                original_input=self.session.original_input,
                current_input=self.session.current_input,
                summary=summary,
                adapter=self.session.adapter,
                resolved_count=sum(
                    1 for r in summary.results
                    if r.status == ResultStatus.OK
                ),
                is_valid=True,
            )
            return self._summary_to_dict(summary)
        except InputValidationError as exc:
            return {"status": "error", "message": str(exc)}

    def update_record_params(
        self,
        record_index: int,
        new_params: dict[str, str | int],
    ) -> dict[str, str]:
        """Update parameters for a specific record."""
        if not self.session:
            return {"status": "error", "message": "No session loaded"}

        try:
            updated_input = json.loads(json.dumps(self.session.current_input))
            if record_index < len(updated_input.get("records", [])):
                updated_input["records"][record_index] = new_params
                # Preserve list_name
                self.session = InteractiveSession(
                    original_input=self.session.original_input,
                    current_input=updated_input,
                    adapter=self.session.adapter,
                    is_valid=True,
                )
                # Clear summary as input has changed
                return {"status": "ok", "message": "Record updated"}
            else:
                return {"status": "error", "message": "Invalid record index"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def get_current_input(self) -> dict[str, Any] | None:
        """Get the current input state."""
        return self.session.current_input if self.session else None

    def get_summary(self) -> dict[str, Any] | None:
        """Get the current validation summary as a dictionary."""
        if not self.session or not self.session.summary:
            return None
        return self._summary_to_dict(self.session.summary)

    def get_resolved_results(self) -> list[dict[str, Any]]:
        """Get resolved (OK status) results as a sortable table."""
        if not self.session or not self.session.summary:
            return []

        results = []
        for result in self.session.summary.results:
            if result.status == ResultStatus.OK:
                master_id = result.master_ids[0]
                candidate = next(
                    (c for c in result.candidates if c.master_id == master_id),
                    None,
                )
                results.append({
                    "position": result.position,
                    "master_id": master_id,
                    "title": candidate.title if candidate else None,
                    "artist": candidate.artist if candidate else None,
                    "year": candidate.year if candidate else None,
                    "query": dict(result.query),
                })
        return results

    def save_to_file(
        self,
        json_path: Path | str,
        html_path: Path | str | None = None,
    ) -> dict[str, str]:
        """Save current input JSON and optionally HTML report."""
        if not self.session:
            return {"status": "error", "message": "No session loaded"}

        try:
            json_path = Path(json_path)
            json_path.write_text(
                json.dumps(
                    self.session.current_input,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            result = {"status": "ok", "saved_json": str(json_path)}

            if html_path and self.session.summary:
                html_path = Path(html_path)
                html_content = render_html_report(self.session.summary)
                html_path.write_text(html_content, encoding="utf-8")
                result["saved_html"] = str(html_path)

            return result
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def reset_to_original(self) -> dict[str, str]:
        """Reset current input to original."""
        if not self.session:
            return {"status": "error", "message": "No session loaded"}

        self.session = InteractiveSession(
            original_input=self.session.original_input,
            current_input=json.loads(json.dumps(self.session.original_input)),
            adapter=self.session.adapter,
            is_valid=True,
        )
        return {"status": "ok", "message": "Reset to original input"}

    def research_record(self, record_index: int, new_params: dict[str, str | int]) -> dict[str, Any]:
        """Re-search a single record with new parameters and preserve resolved results."""
        if not self.session or not self.session.summary:
            return {"status": "error", "message": "No session with results loaded"}

        try:
            # Update the record with new parameters
            updated_input = json.loads(json.dumps(self.session.current_input))
            if record_index >= len(updated_input.get("records", [])):
                return {"status": "error", "message": "Invalid record index"}
            
            updated_input["records"][record_index] = new_params
            
            # Run validation on the updated input
            validated = validate_document(updated_input)
            summary = search_all(validated, self.session.adapter)
            
            # Update session with new results
            self.session = InteractiveSession(
                original_input=self.session.original_input,
                current_input=updated_input,
                summary=summary,
                adapter=self.session.adapter,
                resolved_count=sum(
                    1 for r in summary.results
                    if r.status == ResultStatus.OK
                ),
                is_valid=True,
            )
            
            # Return the new result for this specific record
            if record_index < len(summary.results):
                result = summary.results[record_index]
                return {
                    "status": "ok",
                    "result": {
                        "position": result.position,
                        "query": dict(result.query),
                        "status": str(result.status),
                        "master_ids": result.master_ids,
                        "candidates": [
                            {
                                "master_id": c.master_id,
                                "title": c.title,
                                "artist": c.artist,
                                "year": c.year,
                                "url": c.url,
                            }
                            for c in result.candidates[:3]
                        ],
                        "error": result.error,
                    }
                }
            return {"status": "error", "message": "Record not found in results"}
        except InputValidationError as exc:
            return {"status": "error", "message": str(exc)}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    @staticmethod
    def _summary_to_dict(summary: SearchSummary) -> dict[str, Any]:
        """Convert SearchSummary to dictionary for JSON response."""
        grouped = summary.grouped()
        return {
            "list_name": summary.list_name,
            "total": len(summary.results),
            "all_ok": summary.all_ok,
            "counts": {
                status.value: len(results)
                for status, results in grouped.items()
            },
            "results": [
                {
                    "position": result.position,
                    "query": dict(result.query),
                    "status": result.status.value,
                    "master_ids": list(result.master_ids),
                    "error": result.error,
                    "candidates": [
                        asdict(c) for c in result.candidates
                    ] if result.candidates else [],
                    "album_search_performed": result.album_search_performed,
                    "album_ids": list(result.album_ids),
                    "album_candidates": [
                        asdict(c) for c in result.album_candidates
                    ] if result.album_candidates else [],
                }
                for result in summary.results
            ],
        }
