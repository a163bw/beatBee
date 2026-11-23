from collections.abc import Callable

from .models import (
    AlbumCandidate,
    MasterCandidate,
    ResourceCandidate,
    ResultStatus,
    SearchResult,
    SearchSummary,
    TypeSearchResult,
    ValidatedList,
)
from .search import ResourceSearchOutcome, SearchAdapter


def _status_for_ids(ids: tuple[int, ...], error: str | None) -> ResultStatus:
    if error is not None:
        return ResultStatus.ERROR
    if not ids:
        return ResultStatus.NOT_FOUND
    if len(ids) == 1:
        return ResultStatus.OK
    return ResultStatus.MULTIPLE


def search_all(
    validated: ValidatedList,
    adapter: SearchAdapter,
    *,
    on_progress: Callable[[int, int], None] | None = None,
) -> SearchSummary:
    results: list[SearchResult] = []
    for record in validated.records:
        selected_types = record.search_types
        master_outcome = (
            adapter.search(record.params)
            if "master" in selected_types
            else None
        )
        master_ids = (
            tuple(sorted(set(master_outcome.master_ids)))
            if master_outcome and master_outcome.error is None
            else ()
        )
        master_error = master_outcome.error if master_outcome else None

        album_search_performed = False
        album_outcome = None
        if "release" in selected_types:
            if (
                "master" in selected_types
                and master_outcome is not None
                and master_outcome.error is None
                and not master_ids
            ):
                album_search_performed = True
            album_outcome = adapter.search_albums(record.params)
        elif (
            "master" in selected_types
            and master_outcome is not None
            and master_outcome.error is None
            and not master_ids
        ):
            album_search_performed = True
            album_outcome = adapter.search_albums(record.params)
        fallback_error = (
            album_outcome.error
            if album_search_performed and album_outcome
            else None
        )

        type_results: list[TypeSearchResult] = []
        type_errors: list[str] = []
        release_master_ids: set[int] = set()
        release_master_candidates: dict[int, MasterCandidate] = {}

        for resource_type in selected_types:
            if resource_type == "master":
                resource_ids = master_ids
                error = master_error
                candidates = tuple(
                    ResourceCandidate(
                        resource_id=candidate.master_id,
                        title=candidate.title,
                        artist=candidate.artist,
                        release_title=candidate.release_title,
                        year=candidate.year,
                        master_id=candidate.master_id,
                    )
                    for candidate in (master_outcome.candidates if master_outcome else ())
                )
            elif resource_type == "release":
                resource_ids = (
                    tuple(sorted(set(album_outcome.release_ids)))
                    if album_outcome and album_outcome.error is None
                    else ()
                )
                error = album_outcome.error if album_outcome else None
                candidates = tuple(
                    ResourceCandidate(
                        resource_id=candidate.release_id,
                        title=candidate.title,
                        artist=candidate.artist,
                        release_title=candidate.release_title,
                        year=candidate.year,
                        master_id=candidate.master_id,
                    )
                    for candidate in (album_outcome.candidates if album_outcome else ())
                )
                for candidate in candidates:
                    if candidate.master_id is not None:
                        release_master_ids.add(candidate.master_id)
                        release_master_candidates[candidate.master_id] = MasterCandidate(
                            master_id=candidate.master_id,
                            title=candidate.title,
                            artist=candidate.artist,
                            release_title=candidate.release_title,
                            year=candidate.year,
                        )
            else:
                search_resource_type = getattr(adapter, "search_resource_type", None)
                resource_outcome = (
                    search_resource_type(record.params, resource_type)
                    if search_resource_type
                    else ResourceSearchOutcome(
                        error=(
                            "Search adapter does not support "
                            f"{resource_type} searches."
                        )
                    )
                )
                resource_ids = (
                    tuple(sorted(set(resource_outcome.resource_ids)))
                    if resource_outcome.error is None
                    else ()
                )
                error = resource_outcome.error
                candidates = resource_outcome.candidates

            if error is not None:
                type_errors.append(f"{resource_type}: {error}")
            type_results.append(
                TypeSearchResult(
                    resource_type=resource_type,
                    resource_ids=resource_ids,
                    status=_status_for_ids(resource_ids, error),
                    error=error,
                    candidates=candidates,
                )
            )

        all_master_ids = set(master_ids)
        if "release" in selected_types:
            all_master_ids.update(release_master_ids)
        resolved_master_ids = tuple(sorted(all_master_ids))

        if master_error is not None or fallback_error is not None:
            status = ResultStatus.ERROR
        elif type_errors:
            status = ResultStatus.ERROR
        elif not resolved_master_ids:
            status = ResultStatus.NOT_FOUND
        elif len(resolved_master_ids) == 1:
            status = ResultStatus.OK
        else:
            status = ResultStatus.MULTIPLE

        outcome_error = (
            master_error
            or fallback_error
            or "; ".join(type_errors)
            or (
                "No Master ID was found; selected resource types do not "
                "provide a Master ID."
                if not resolved_master_ids
                else None
            )
        )
        master_candidates: dict[int, MasterCandidate] = {}
        if master_outcome:
            master_candidates.update(
                {
                    candidate.master_id: candidate
                    for candidate in master_outcome.candidates
                }
            )
        master_candidates.update(release_master_candidates)
        candidates = tuple(
            master_candidates.get(master_id, MasterCandidate(master_id=master_id))
            for master_id in resolved_master_ids
        )

        album_ids = (
            tuple(sorted(set(album_outcome.release_ids)))
            if album_search_performed
            and album_outcome
            and album_outcome.error is None
            else ()
        )
        album_candidate_by_id = {
            candidate.release_id: candidate
            for candidate in (album_outcome.candidates if album_outcome else ())
            if candidate.release_id in album_ids
        }
        album_candidates = tuple(
            album_candidate_by_id.get(
                release_id,
                AlbumCandidate(release_id=release_id),
            )
            for release_id in album_ids
        )

        results.append(
            SearchResult(
                position=record.position,
                query={
                    **record.params,
                    "type": record.search_types,
                },
                status=status,
                master_ids=resolved_master_ids,
                error=outcome_error,
                candidates=candidates,
                album_search_performed=album_search_performed,
                album_ids=album_ids,
                album_candidates=album_candidates,
                type_results=tuple(type_results),
            )
        )
        if on_progress is not None:
            on_progress(len(results), len(validated.records))

    return SearchSummary(list_name=validated.list_name, results=tuple(results))
