from dataclasses import dataclass
from typing import Protocol

from .models import AlbumCandidate, MasterCandidate, SearchParams


@dataclass(frozen=True, slots=True)
class SearchOutcome:
    master_ids: tuple[int, ...] = ()
    error: str | None = None
    candidates: tuple[MasterCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class AlbumSearchOutcome:
    release_ids: tuple[int, ...] = ()
    error: str | None = None
    candidates: tuple[AlbumCandidate, ...] = ()


class SearchAdapter(Protocol):
    def search(self, params: SearchParams) -> SearchOutcome:
        ...

    def search_albums(self, params: SearchParams) -> AlbumSearchOutcome:
        ...


class FakeSearchAdapter:
    """Deterministic in-process adapter for tests and Phase 1 CLI plumbing."""

    def __init__(
        self,
        outcomes: dict[int, SearchOutcome] | tuple[SearchOutcome, ...] | None = None,
        default: SearchOutcome | None = None,
        album_outcomes: (
            dict[int, AlbumSearchOutcome]
            | tuple[AlbumSearchOutcome, ...]
            | None
        ) = None,
        default_album: AlbumSearchOutcome | None = None,
    ) -> None:
        self._outcomes = outcomes
        self._default = default or SearchOutcome(error="Search adapter unavailable")
        self._position = 0
        self._album_outcomes = album_outcomes
        self._default_album = default_album or AlbumSearchOutcome()
        self._album_position = 0

    def search(self, params: SearchParams) -> SearchOutcome:
        self._position += 1
        if isinstance(self._outcomes, dict):
            return self._outcomes.get(self._position, self._default)
        if isinstance(self._outcomes, tuple):
            if self._position <= len(self._outcomes):
                return self._outcomes[self._position - 1]
        return self._default

    def search_albums(self, params: SearchParams) -> AlbumSearchOutcome:
        self._album_position += 1
        if isinstance(self._album_outcomes, dict):
            return self._album_outcomes.get(
                self._album_position,
                self._default_album,
            )
        if isinstance(self._album_outcomes, tuple):
            if self._album_position <= len(self._album_outcomes):
                return self._album_outcomes[self._album_position - 1]
        return self._default_album
