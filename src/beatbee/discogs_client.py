import hashlib
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from .models import AlbumCandidate, MasterCandidate, SearchParams
from .search import AlbumSearchOutcome, SearchAdapter, SearchOutcome


RequestOpener = Callable[[urllib.request.Request, float], Any]
MIN_REQUEST_INTERVAL = 1.25
RATE_WINDOW_SECONDS = 60.0
MAX_WAIT_SECONDS = 300.0


@dataclass(frozen=True, slots=True)
class _CandidateData:
    resource_id: int
    title: str | None
    artist: str | None
    release_title: str | None
    year: str | None


@dataclass(frozen=True, slots=True)
class _ResourceSearchOutcome:
    resource_ids: tuple[int, ...] = ()
    candidates: tuple[_CandidateData, ...] = ()
    error: str | None = None


class DiscogsSearchClient(SearchAdapter):
    def __init__(
        self,
        token: str,
        *,
        timeout_seconds: float = 15.0,
        max_retries: int = 3,
        max_pages: int = 100,
        max_results: int = 10_000,
        per_page: int = 100,
        opener: RequestOpener | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
        snapshot_dir: str | Path | None = None,
        snapshot_only: bool = False,
    ) -> None:
        if not token.strip():
            raise ValueError("Discogs token must not be empty.")
        self.token = token
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.max_pages = max_pages
        self.max_results = max_results
        self.per_page = per_page
        self.opener = opener or self._urlopen
        self.sleeper = sleeper
        self.monotonic = monotonic
        self.wall_clock = wall_clock
        self._next_request_at = 0.0
        self._request_interval = MIN_REQUEST_INTERVAL
        self.snapshot_dir = Path(snapshot_dir) if snapshot_dir else None
        self.snapshot_only = snapshot_only

    @staticmethod
    def _urlopen(request: urllib.request.Request, timeout: float) -> Any:
        return urllib.request.urlopen(request, timeout=timeout)

    def _snapshot_path(self, url: str) -> Path | None:
        if self.snapshot_dir is None:
            return None
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.snapshot_dir / f"{digest}.json"

    def _read_snapshot(self, url: str) -> dict[str, Any] | None:
        path = self._snapshot_path(url)
        if path is None or not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _write_snapshot(self, url: str, payload: Mapping[str, Any]) -> None:
        path = self._snapshot_path(url)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

    def _wait_for_request(self) -> None:
        delay = self._next_request_at - self.monotonic()
        if delay > MAX_WAIT_SECONDS:
            raise RuntimeError(
                f"Discogs requested a wait longer than {MAX_WAIT_SECONDS:g} seconds."
            )
        if delay > 0:
            self.sleeper(delay)
        self._next_request_at = self.monotonic() + self._request_interval

    def _defer_requests(self, delay: float) -> None:
        self._next_request_at = max(
            self._next_request_at,
            self.monotonic() + delay,
        )

    def _update_rate_limit(self, headers: Any) -> None:
        try:
            limit = int(headers.get("X-Discogs-Ratelimit", ""))
        except (TypeError, ValueError):
            limit = 0
        if limit > 0:
            self._request_interval = max(MIN_REQUEST_INTERVAL, 75.0 / limit)
            self._defer_requests(self._request_interval)

        try:
            remaining = int(headers.get("X-Discogs-Ratelimit-Remaining", ""))
        except (TypeError, ValueError):
            return
        if 0 <= remaining <= 5:
            self._defer_requests(RATE_WINDOW_SECONDS / (remaining + 1))

    def _retry_after(self, value: str | None) -> float:
        if value is None:
            return RATE_WINDOW_SECONDS
        try:
            delay = float(value)
            if delay < 0:
                return RATE_WINDOW_SECONDS
        except ValueError:
            try:
                date = parsedate_to_datetime(value)
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
                delay = date.timestamp() - self.wall_clock()
            except (TypeError, ValueError, OverflowError):
                return RATE_WINDOW_SECONDS
        if not math.isfinite(delay):
            return RATE_WINDOW_SECONDS
        return max(delay, 0.0)

    def _request(self, url: str) -> dict[str, Any]:
        snapshot = self._read_snapshot(url)
        if snapshot is not None:
            return snapshot
        if self.snapshot_only:
            raise RuntimeError("Required API response is missing from snapshot.")

        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Discogs token={self.token}",
                "User-Agent": "BeatBee/0.1",
            },
            method="GET",
        )

        for attempt in range(self.max_retries + 1):
            try:
                self._wait_for_request()
                with self.opener(request, self.timeout_seconds) as response:
                    self._update_rate_limit(response.headers)
                    raw = response.read()
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise RuntimeError("Discogs returned a non-object JSON response.")
                self._write_snapshot(url, payload)
                return payload
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    retry_after = (
                        exc.headers.get("Retry-After") if exc.headers else None
                    )
                    self._defer_requests(self._retry_after(retry_after))
                    if attempt < self.max_retries:
                        continue
                raise RuntimeError(
                    f"Discogs API HTTP {exc.code}: {exc.reason}"
                ) from exc
            except urllib.error.URLError as exc:
                if attempt < self.max_retries:
                    self._defer_requests(min(2 ** attempt, 60.0))
                    continue
                raise TimeoutError(
                    f"Discogs request failed: {exc.reason}"
                ) from exc
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    "Discogs returned malformed JSON."
                ) from exc

        raise RuntimeError("Discogs request retry limit exhausted.")

    def search(self, params: SearchParams) -> SearchOutcome:
        outcome = self._search_resources(params, "master")
        if outcome.error is not None:
            return SearchOutcome(error=outcome.error)
        return SearchOutcome(
            master_ids=outcome.resource_ids,
            candidates=tuple(
                MasterCandidate(
                    master_id=candidate.resource_id,
                    title=candidate.title,
                    artist=candidate.artist,
                    release_title=candidate.release_title,
                    year=candidate.year,
                )
                for candidate in outcome.candidates
            ),
        )

    def search_albums(self, params: SearchParams) -> AlbumSearchOutcome:
        outcome = self._search_resources(params, "release")
        if outcome.error is not None:
            return AlbumSearchOutcome(error=outcome.error)
        return AlbumSearchOutcome(
            release_ids=outcome.resource_ids,
            candidates=tuple(
                AlbumCandidate(
                    release_id=candidate.resource_id,
                    title=candidate.title,
                    artist=candidate.artist,
                    release_title=candidate.release_title,
                    year=candidate.year,
                )
                for candidate in outcome.candidates
            ),
        )

    def _search_resources(
        self,
        params: SearchParams,
        resource_type: str,
    ) -> _ResourceSearchOutcome:
        resource_ids: set[int] = set()
        candidates: dict[int, _CandidateData] = {}
        page_number = 1

        while True:
            if page_number > self.max_pages:
                return _ResourceSearchOutcome(
                    error=f"Pagination exceeded configured limit of {self.max_pages} pages."
                )

            query = dict(params)
            query["type"] = resource_type
            query["page"] = page_number
            query["per_page"] = self.per_page
            url = (
                "https://api.discogs.com/database/search?"
                + urllib.parse.urlencode(query)
            )

            try:
                payload = self._request(url)
            except (RuntimeError, TimeoutError) as exc:
                return _ResourceSearchOutcome(error=str(exc))

            pagination = payload.get("pagination")
            results = payload.get("results")
            if not isinstance(pagination, dict) or not isinstance(results, list):
                return _ResourceSearchOutcome(
                    error="Malformed Discogs search response: missing pagination or results."
                )

            returned_page = pagination.get("page")
            total_pages = pagination.get("pages")
            if (
                isinstance(returned_page, bool)
                or not isinstance(returned_page, int)
                or isinstance(total_pages, bool)
                or not isinstance(total_pages, int)
                or returned_page != page_number
                or total_pages < 1
                or returned_page > total_pages
            ):
                return _ResourceSearchOutcome(
                    error="Incomplete or inconsistent Discogs pagination."
                )

            for result in results:
                if not isinstance(result, dict):
                    return _ResourceSearchOutcome(
                        error="Malformed Discogs search result."
                    )
                if result.get("type") != resource_type:
                    return _ResourceSearchOutcome(
                        error=(
                            "Discogs search returned a resource that is not a "
                            f"{resource_type.title()}."
                        )
                    )
                resource_id = result.get("id")
                if (
                    isinstance(resource_id, bool)
                    or not isinstance(resource_id, int)
                    or resource_id <= 0
                ):
                    return _ResourceSearchOutcome(
                        error=(
                            "Discogs search returned a malformed "
                            f"{resource_type.title()} ID."
                        )
                    )
                resource_ids.add(resource_id)
                raw_title = result.get("title")
                title = raw_title if isinstance(raw_title, str) and raw_title else None
                artist: str | None = None
                release_title: str | None = None
                if title is not None and " - " in title:
                    artist, release_title = title.split(" - ", 1)
                elif title is not None:
                    release_title = title

                raw_year = result.get("year")
                year = str(raw_year) if isinstance(raw_year, (str, int)) and not isinstance(raw_year, bool) else None
                candidates[resource_id] = _CandidateData(
                    resource_id=resource_id,
                    title=title,
                    artist=artist,
                    release_title=release_title,
                    year=year,
                )
                if len(resource_ids) > self.max_results:
                    return _ResourceSearchOutcome(
                        error=(
                            f"Search exceeded configured result limit "
                            f"of {self.max_results} unique {resource_type.title()}s."
                        )
                    )

            if page_number >= total_pages:
                break
            page_number += 1

        return _ResourceSearchOutcome(
            resource_ids=tuple(sorted(resource_ids)),
            candidates=tuple(
                candidates[resource_id]
                for resource_id in sorted(resource_ids)
            ),
        )
