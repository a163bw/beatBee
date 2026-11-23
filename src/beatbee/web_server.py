"""Local web server for interactive BeatBee validation and resolution."""

import json
from copy import deepcopy
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any

from .models import (
    DISCOGS_RESOURCE_TYPES,
    ResultStatus,
    SearchSummary,
)
from .search import SearchAdapter, FakeSearchAdapter
from .service import search_all
from .validation import validate_document, InputValidationError
from .html_report import render_html_report


_SEARCH_TYPE_ORDER = DISCOGS_RESOURCE_TYPES
_RESULTS_PER_PAGE = 50


@dataclass(slots=True)
class WebRecordState:
    """Web-only draft, interactive results, and explicit confirmation."""

    draft: dict[str, Any]
    search_types: tuple[str, ...]
    technical_status: str
    technical_error: str | None = None
    type_searches: dict[str, dict[str, Any]] = field(default_factory=dict)
    selected_candidate: tuple[str, int] | None = None
    confirmed: dict[str, Any] | None = None
    confirmed_params: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class InteractiveSession:
    """State of an interactive validation session."""
    original_input: dict[str, Any]
    current_input: dict[str, Any]
    adapter: SearchAdapter
    summary: SearchSummary | None = None
    resolved_count: int = 0
    is_valid: bool = False


class InteractiveSessionManager:
    """Manages interactive validation sessions."""

    def __init__(self, adapter: SearchAdapter | None = None):
        self.adapter = adapter or FakeSearchAdapter()
        self.session: InteractiveSession | None = None
        self.search_history: list[tuple[int, dict[str, Any]]] = []
        self.record_states: list[WebRecordState] = []

    def load_input(self, document: dict[str, Any]) -> dict[str, str]:
        """Load and validate input document."""
        try:
            self._validate_web_metadata(document)
            validated = validate_document(self._search_document(document))
            self.session = InteractiveSession(
                original_input=deepcopy(document),
                current_input=deepcopy(document),
                adapter=self.adapter,
                is_valid=True,
            )
            self.record_states = []
            return {"status": "ok", "list_name": validated.list_name}
        except InputValidationError as exc:
            return {"status": "error", "message": str(exc)}

    def run_validation(self) -> dict[str, Any] | None:
        """Run validation on current input."""
        if not self.session or not self.session.is_valid:
            return None

        try:
            self._validate_web_metadata(self.session.current_input)
            validated = validate_document(
                self._search_document(self.session.current_input)
            )
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
            self.record_states = [
                self._state_from_initial_result(
                    self.session.original_input["records"][index],
                    result,
                )
                for index, result in enumerate(summary.results)
            ]
            return self._summary_to_dict(summary)
        except InputValidationError as exc:
            return {"status": "error", "message": str(exc)}

    @staticmethod
    def _search_document(document: dict[str, Any]) -> dict[str, Any]:
        """Remove Web-only metadata before validation or core searches."""
        sanitized = deepcopy(document)
        if not isinstance(sanitized, dict):
            return sanitized
        records = sanitized.get("records")
        if isinstance(records, list):
            for record in records:
                if isinstance(record, dict):
                    record.pop("selected_result", None)
        return sanitized

    @staticmethod
    def _validate_web_metadata(document: Any) -> None:
        if not isinstance(document, dict):
            return
        records = document.get("records")
        if not isinstance(records, list):
            return
        for position, record in enumerate(records, start=1):
            if not isinstance(record, dict) or "selected_result" not in record:
                continue
            selected = record["selected_result"]
            if not isinstance(selected, dict) or set(selected) != {
                "type", "id", "url"
            }:
                raise InputValidationError(
                    f"Record {position} selected_result must contain type, id, and url."
                )
            resource_type = selected["type"]
            resource_id = selected["id"]
            declared_type = record.get("type", "master")
            type_matches = (
                declared_type == resource_type
                if isinstance(declared_type, str)
                else (
                    isinstance(declared_type, list)
                    and resource_type in declared_type
                )
            )
            if (
                resource_type not in DISCOGS_RESOURCE_TYPES
                or not type_matches
                or isinstance(resource_id, bool)
                or not isinstance(resource_id, int)
                or resource_id <= 0
                or selected["url"]
                != f"https://www.discogs.com/{resource_type}/{resource_id}"
            ):
                raise InputValidationError(
                    f"Record {position} selected_result is invalid."
                )

    def _state_from_initial_result(
        self,
        original_record: dict[str, Any],
        result: Any,
    ) -> WebRecordState:
        raw_types = original_record.get("type", "master")
        if isinstance(raw_types, str):
            selected_types = (raw_types,)
        elif isinstance(raw_types, list):
            selected_types = tuple(raw_types)
        else:
            selected_types = ("master",)
        selected_types = tuple(
            resource_type
            for resource_type in _SEARCH_TYPE_ORDER
            if resource_type in selected_types
        )
        draft = {
            key: deepcopy(value)
            for key, value in original_record.items()
            if key not in {"type", "master_id", "selected_result"}
        }
        state = WebRecordState(
            draft=draft,
            search_types=selected_types or ("master",),
            technical_status=result.status.value,
            technical_error=self._safe_error_message(result.error),
        )
        for type_result in result.type_results:
            candidates = [
                InteractiveSessionManager._candidate_to_dict(
                    type_result.resource_type,
                    candidate,
                )
                for candidate in type_result.candidates
            ]
            state.type_searches[type_result.resource_type] = {
                "status": type_result.status.value,
                "error": self._safe_error_message(type_result.error),
                "candidates": candidates,
            }
        if result.album_search_performed:
            state.type_searches.setdefault(
                "release",
                {
                    "status": (
                        "ERROR"
                        if result.status is ResultStatus.ERROR
                        else "OK"
                        if result.album_candidates
                        else "NOT_FOUND"
                    ),
                    "error": (
                        self._safe_error_message(result.error)
                        if result.status is ResultStatus.ERROR
                        else None
                    ),
                    "candidates": [
                        InteractiveSessionManager._candidate_to_dict(
                            "release", candidate
                        )
                        for candidate in result.album_candidates
                    ],
                },
            )
        return state

    @staticmethod
    def _candidate_to_dict(resource_type: str, candidate: Any) -> dict[str, Any]:
        candidate_data = asdict(candidate)
        resource_id = candidate_data.get(
            "resource_id",
            candidate_data.get(
                "master_id",
                candidate_data.get("release_id"),
            ),
        )
        raw_title = candidate_data.get("title")
        if resource_type in {"artist", "label"}:
            artist_or_name = raw_title or candidate_data.get("artist")
            title = None
        else:
            artist_or_name = candidate_data.get("artist")
            title = candidate_data.get("release_title") or raw_title
        return {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "artist": artist_or_name,
            "title": title,
            "year": candidate_data.get("year"),
            "url": f"https://www.discogs.com/{resource_type}/{resource_id}",
        }

    def search_record(
        self,
        record_index: int,
        params: dict[str, Any],
        search_types: list[str] | tuple[str, ...],
        *,
        page: int = 1,
        per_page: int = _RESULTS_PER_PAGE,
    ) -> dict[str, Any]:
        """Search one position independently, retaining every paginated hit."""
        state = self._record_state(record_index)
        if not isinstance(params, dict):
            return {"status": "error", "message": "params must be an object"}
        if not isinstance(search_types, (list, tuple)) or not search_types:
            return {
                "status": "error",
                "message": "Select at least one resource type.",
            }
        if any(
            not isinstance(resource_type, str)
            or resource_type not in _SEARCH_TYPE_ORDER
            for resource_type in search_types
        ):
            return {"status": "error", "message": "Invalid resource type."}
        if len(set(search_types)) != len(search_types):
            return {"status": "error", "message": "Resource types must be unique."}
        if (
            isinstance(page, bool)
            or not isinstance(page, int)
            or page < 1
            or isinstance(per_page, bool)
            or not isinstance(per_page, int)
            or not 1 <= per_page <= 100
        ):
            return {"status": "error", "message": "Invalid results page."}
        if set(params) & {"type", "master_id", "selected_result", "page", "per_page"}:
            return {
                "status": "error",
                "message": "Search parameters must not contain Web metadata or reserved keys.",
            }
        document = {
            "list_name": self.session.original_input["list_name"],
            "records": [{**params, "type": list(search_types)}],
        }
        try:
            validated = validate_document(document)
        except InputValidationError as exc:
            return {"status": "error", "message": str(exc)}

        updated_types = tuple(
            resource_type
            for resource_type in _SEARCH_TYPE_ORDER
            if resource_type in search_types
        )
        state.draft = deepcopy(params)
        state.search_types = updated_types
        state.type_searches = {}
        state.selected_candidate = None
        search_params = dict(validated.records[0].params)
        search_params.pop("type", None)
        for resource_type in updated_types:
            try:
                outcome = self.adapter.search_resource_type(
                    search_params,
                    resource_type,
                )
            except Exception as exc:
                state.type_searches[resource_type] = {
                    "status": "ERROR",
                    "error": self._safe_error(exc),
                    "candidates": [],
                }
                continue
            candidates = [
                self._candidate_to_dict(resource_type, candidate)
                for candidate in outcome.candidates
            ]
            candidate_ids = {candidate["resource_id"] for candidate in candidates}
            candidates.extend(
                {
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "artist": None,
                    "title": None,
                    "year": None,
                    "url": f"https://www.discogs.com/{resource_type}/{resource_id}",
                }
                for resource_id in outcome.resource_ids
                if resource_id not in candidate_ids
            )
            state.type_searches[resource_type] = {
                "status": (
                    "ERROR"
                    if outcome.error
                    else "OK"
                    if outcome.resource_ids
                    else "NOT_FOUND"
                ),
                "error": self._safe_error_message(outcome.error),
                "candidates": candidates,
            }

        current = deepcopy(self.session.current_input)
        current["records"][record_index] = deepcopy(params)
        self.session = InteractiveSession(
            original_input=self.session.original_input,
            current_input=current,
            adapter=self.session.adapter,
            summary=self.session.summary,
            resolved_count=self.session.resolved_count,
            is_valid=True,
        )
        return {
            "status": "ok",
            "record": self.get_record_results(record_index, page, per_page),
        }

    def get_record_results(
        self,
        record_index: int,
        page: int = 1,
        per_page: int = _RESULTS_PER_PAGE,
    ) -> dict[str, Any]:
        state = self._record_state(record_index)
        if (
            isinstance(page, bool)
            or not isinstance(page, int)
            or page < 1
            or isinstance(per_page, bool)
            or not isinstance(per_page, int)
            or not 1 <= per_page <= 100
        ):
            raise ValueError("Invalid results page.")
        results = []
        for resource_type in state.search_types:
            search = state.type_searches.get(resource_type, {})
            results.extend(search.get("candidates", []))
        total = len(results)
        start = (page - 1) * per_page
        return {
            "position": record_index + 1,
            "technical_status": state.technical_status,
            "technical_error": self._safe_error_message(
                state.technical_error
            ),
            "draft": deepcopy(state.draft),
            "search_types": list(state.search_types),
            "type_searches": deepcopy(state.type_searches),
            "results": results[start:start + per_page],
            "total_results": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, (total + per_page - 1) // per_page),
            "selected_candidate": (
                {
                    "resource_type": state.selected_candidate[0],
                    "resource_id": state.selected_candidate[1],
                }
                if state.selected_candidate
                else None
            ),
        }

    def _safe_error(self, error: Exception) -> str:
        return self._safe_error_message(str(error)) or "Search failed."

    def _safe_error_message(self, message: str | None) -> str | None:
        if message is None:
            return None
        token = getattr(self.adapter, "token", None)
        if isinstance(token, str) and token:
            return message.replace(token, "[redacted]")
        return message

    def select_candidate(
        self,
        record_index: int,
        resource_type: str,
        resource_id: int,
    ) -> dict[str, str]:
        state = self._record_state(record_index)
        if resource_type not in _SEARCH_TYPE_ORDER:
            return {"status": "error", "message": "Invalid resource type."}
        candidates = state.type_searches.get(resource_type, {}).get(
            "candidates", []
        )
        if (
            isinstance(resource_id, bool)
            or not isinstance(resource_id, int)
            or resource_id <= 0
            or not any(
                candidate["resource_id"] == resource_id
                for candidate in candidates
            )
        ):
            return {
                "status": "error",
                "message": "The selected result is not in the latest search.",
            }
        state.selected_candidate = (resource_type, resource_id)
        return {"status": "ok", "message": "Result selected."}

    def confirm_selection(self, record_index: int) -> dict[str, Any]:
        state = self._record_state(record_index)
        if state.selected_candidate is None:
            return {"status": "error", "message": "Select one search result first."}
        resource_type, resource_id = state.selected_candidate
        candidates = state.type_searches[resource_type]["candidates"]
        selected = next(
            candidate
            for candidate in candidates
            if candidate["resource_id"] == resource_id
        )
        state.confirmed = deepcopy(selected)
        state.confirmed_params = deepcopy(state.draft)
        return {
            "status": "ok",
            "message": "Selection confirmed.",
            "record": self._manual_row(record_index + 1, state),
        }

    def get_web_state(
        self,
        *,
        sort_by: str = "position",
        direction: str = "asc",
    ) -> dict[str, Any]:
        if sort_by not in {
            "position", "artist", "title", "year", "resource_type", "resource_id"
        }:
            raise ValueError("Unsupported sort category.")
        if direction not in {"asc", "desc"}:
            raise ValueError("Unsupported sort direction.")
        if not self.session or not self.session.summary:
            raise ValueError("Run the initial search first.")

        results_by_position = {
            result.position: result for result in self.session.summary.results
        }
        unresolved = []
        resolved = []
        for index, state in enumerate(self.record_states):
            position = index + 1
            if state.confirmed:
                resolved.append(self._manual_row(position, state))
                continue
            result = results_by_position[position]
            if result.status is ResultStatus.OK:
                resolved.append(self._automatic_row(result))
            else:
                interactive_results = self.get_record_results(index)
                unresolved.append({
                    "position": position,
                    "original_record": deepcopy(
                        self.session.original_input["records"][index]
                    ),
                    "draft": deepcopy(state.draft),
                    "technical_status": state.technical_status,
                    "technical_error": self._safe_error_message(
                        state.technical_error
                    ),
                    "search_types": list(state.search_types),
                    "type_searches": deepcopy(state.type_searches),
                    "results": interactive_results["results"],
                    "total_results": interactive_results["total_results"],
                    "page": interactive_results["page"],
                    "per_page": interactive_results["per_page"],
                    "total_pages": interactive_results["total_pages"],
                    "selected_candidate": (
                        {
                            "resource_type": state.selected_candidate[0],
                            "resource_id": state.selected_candidate[1],
                        }
                        if state.selected_candidate
                        else None
                    ),
                })
        resolved.sort(key=lambda row: row["position"])
        if sort_by != "position":
            key_name = sort_by
            resolved.sort(
                key=lambda row: (
                    row[key_name] is None,
                    row[key_name] if row[key_name] is not None else "",
                ),
                reverse=direction == "desc",
            )
        elif direction == "desc":
            resolved.sort(key=lambda row: row["position"], reverse=True)

        core_counts = {
            status.value: sum(
                result.status is status
                for result in self.session.summary.results
            )
            for status in ResultStatus
        }
        return {
            "list_name": self.session.original_input["list_name"],
            "total": len(self.record_states),
            "nIO": unresolved,
            "iO": resolved,
            "core_counts": core_counts,
            "automatic_count": sum(
                row["source"] == "automatic" for row in resolved
            ),
            "manual_count": sum(
                row["source"] == "manual" for row in resolved
            ),
            "sort_by": sort_by,
            "direction": direction,
        }

    @staticmethod
    def _manual_row(position: int, state: WebRecordState) -> dict[str, Any]:
        confirmed = state.confirmed or {}
        return {
            "position": position,
            "artist": confirmed.get("artist") or confirmed.get("title"),
            "title": confirmed.get("title"),
            "year": confirmed.get("year"),
            "resource_type": confirmed.get("resource_type"),
            "resource_id": confirmed.get("resource_id"),
            "url": confirmed.get("url"),
            "source": "manual",
        }

    @staticmethod
    def _automatic_row(result: Any) -> dict[str, Any]:
        master_id = result.master_ids[0]
        candidate = next(
            (
                item for item in result.candidates
                if item.master_id == master_id
            ),
            None,
        )
        return {
            "position": result.position,
            "artist": candidate.artist if candidate else None,
            "title": (
                candidate.release_title or candidate.title
                if candidate
                else None
            ),
            "year": candidate.year if candidate else None,
            "resource_type": "master",
            "resource_id": master_id,
            "url": f"https://www.discogs.com/master/{master_id}",
            "source": "automatic",
        }

    def _record_state(self, record_index: int) -> WebRecordState:
        if not self.session or not self.session.summary:
            raise ValueError("Run the initial search first.")
        if (
            isinstance(record_index, bool)
            or not isinstance(record_index, int)
            or record_index < 0
            or record_index >= len(self.record_states)
        ):
            raise ValueError("Invalid record index.")
        return self.record_states[record_index]

    def update_record_params(
        self,
        record_index: int,
        new_params: dict[str, Any],
    ) -> dict[str, str]:
        """Update parameters for a specific record."""
        if not self.session:
            return {"status": "error", "message": "No session loaded"}

        if (
            isinstance(record_index, bool)
            or not isinstance(record_index, int)
            or record_index < 0
            or record_index >= len(self.session.current_input.get("records", []))
        ):
            return {"status": "error", "message": "Invalid record index"}
        updated_input = deepcopy(self.session.current_input)
        updated_input["records"][record_index] = deepcopy(new_params)
        self.session = InteractiveSession(
            original_input=self.session.original_input,
            current_input=updated_input,
            adapter=self.session.adapter,
            summary=self.session.summary,
            resolved_count=self.session.resolved_count,
            is_valid=True,
        )
        return {"status": "ok", "message": "Record updated"}

    def get_current_input(self) -> dict[str, Any] | None:
        """Get the current input state."""
        return self.session.current_input if self.session else None

    def get_export_input(self) -> dict[str, Any] | None:
        """Build the Web export without modifying original records or order."""
        if not self.session:
            return None

        exported = deepcopy(self.session.original_input)
        if not self.session or not self.session.summary:
            return exported
        for result in self.session.summary.results:
            state = self.record_states[result.position - 1]
            if state.confirmed and state.confirmed_params is not None:
                record = deepcopy(state.confirmed_params)
                record["type"] = state.confirmed["resource_type"]
                record["selected_result"] = {
                    "type": state.confirmed["resource_type"],
                    "id": state.confirmed["resource_id"],
                    "url": state.confirmed["url"],
                }
                exported["records"][result.position - 1] = record
            elif result.status is ResultStatus.OK and result.master_ids:
                exported["records"][result.position - 1]["master_id"] = result.master_ids[0]
            else:
                exported["records"][result.position - 1] = deepcopy(
                    self.session.original_input["records"][result.position - 1]
                )
        return exported

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
                    self.get_export_input(),
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
            current_input=deepcopy(self.session.original_input),
            adapter=self.session.adapter,
            is_valid=True,
        )
        self.record_states = []
        return {"status": "ok", "message": "Reset to original input"}

    def research_record(self, record_index: int, new_params: dict[str, Any]) -> dict[str, Any]:
        """Backward-compatible single-item search endpoint."""
        raw_types = new_params.get("type", ["master"])
        search_types = [raw_types] if isinstance(raw_types, str) else raw_types
        params = {
            key: value
            for key, value in new_params.items()
            if key != "type"
        }
        try:
            outcome = self.search_record(record_index, params, search_types)
            if outcome["status"] != "ok":
                return outcome
            summary = self.get_summary()
            record = self.get_record_results(record_index)
            if summary:
                summary["results"][record_index]["query"] = {
                    **params,
                    "type": tuple(search_types),
                }
                summary["results"][record_index]["type_results"] = [
                    {
                        "resource_type": resource_type,
                        "resource_ids": [
                            candidate["resource_id"]
                            for candidate in search["candidates"]
                        ],
                        "status": search["status"],
                        "error": search["error"],
                        "candidates": search["candidates"],
                    }
                    for resource_type, search in record["type_searches"].items()
                ]
            return {
                "status": "ok",
                "summary": summary,
                "result": record,
            }
        except (ValueError, TypeError) as exc:
            return {"status": "error", "message": str(exc)}

    def _summary_to_dict(self, summary: SearchSummary) -> dict[str, Any]:
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
                    "error": self._safe_error_message(result.error),
                    "candidates": [
                        asdict(c) for c in result.candidates
                    ] if result.candidates else [],
                    "album_search_performed": result.album_search_performed,
                    "album_ids": list(result.album_ids),
                    "album_candidates": [
                        asdict(c) for c in result.album_candidates
                    ] if result.album_candidates else [],
                    "type_results": [
                        {
                            "resource_type": type_result.resource_type,
                            "resource_ids": list(type_result.resource_ids),
                            "status": type_result.status.value,
                            "error": self._safe_error_message(type_result.error),
                            "candidates": [
                                asdict(candidate)
                                for candidate in type_result.candidates
                            ],
                        }
                        for type_result in result.type_results
                    ],
                }
                for result in summary.results
            ],
        }
