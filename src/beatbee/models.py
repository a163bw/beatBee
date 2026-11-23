from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping


SearchParams = Mapping[str, str | int]
SearchQuery = Mapping[str, str | int | tuple[str, ...]]
DISCOGS_RESOURCE_TYPES = ("master", "release", "artist", "label")


@dataclass(frozen=True, slots=True)
class SearchRecord:
    position: int
    params: SearchParams
    search_types: tuple[str, ...] = ("master",)


@dataclass(frozen=True, slots=True)
class ValidatedList:
    list_name: str
    records: tuple[SearchRecord, ...]


class ResultStatus(str, Enum):
    OK = "OK"
    NOT_FOUND = "NOT_FOUND"
    MULTIPLE = "MULTIPLE"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class SearchResult:
    position: int
    query: SearchQuery
    status: ResultStatus
    master_ids: tuple[int, ...] = ()
    error: str | None = None
    candidates: tuple["MasterCandidate", ...] = ()
    album_search_performed: bool = False
    album_ids: tuple[int, ...] = ()
    album_candidates: tuple["AlbumCandidate", ...] = ()
    type_results: tuple["TypeSearchResult", ...] = ()


@dataclass(frozen=True, slots=True)
class MasterCandidate:
    master_id: int
    title: str | None = None
    artist: str | None = None
    release_title: str | None = None
    year: str | None = None


@dataclass(frozen=True, slots=True)
class AlbumCandidate:
    release_id: int
    title: str | None = None
    artist: str | None = None
    release_title: str | None = None
    year: str | None = None
    master_id: int | None = None


@dataclass(frozen=True, slots=True)
class TypeSearchResult:
    resource_type: str
    resource_ids: tuple[int, ...] = ()
    status: ResultStatus = ResultStatus.NOT_FOUND
    error: str | None = None
    candidates: tuple["ResourceCandidate", ...] = ()


@dataclass(frozen=True, slots=True)
class ResourceCandidate:
    resource_id: int
    title: str | None = None
    artist: str | None = None
    release_title: str | None = None
    year: str | None = None
    master_id: int | None = None


@dataclass(frozen=True, slots=True)
class SearchSummary:
    list_name: str
    results: tuple[SearchResult, ...]

    def grouped(self) -> dict[ResultStatus, tuple[SearchResult, ...]]:
        return {
            status: tuple(
                result
                for result in self.results
                if result.status is status
            )
            for status in (
                ResultStatus.OK,
                ResultStatus.NOT_FOUND,
                ResultStatus.MULTIPLE,
                ResultStatus.ERROR,
            )
            if status is not ResultStatus.ERROR
            or any(result.status is status for result in self.results)
        }

    @property
    def all_ok(self) -> bool:
        return bool(self.results) and all(
            result.status is ResultStatus.OK for result in self.results
        )


def immutable_params(params: Mapping[str, str | int]) -> SearchParams:
    return MappingProxyType(dict(params))
