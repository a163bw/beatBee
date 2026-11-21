from collections.abc import Callable

from .models import (
    AlbumCandidate,
    MasterCandidate,
    ResultStatus,
    SearchResult,
    SearchSummary,
    ValidatedList,
)
from .search import SearchAdapter


def search_all(
    validated: ValidatedList,
    adapter: SearchAdapter,
    *,
    on_progress: Callable[[int, int], None] | None = None,
) -> SearchSummary:
    results: list[SearchResult] = []
    for record in validated.records:
        outcome = adapter.search(record.params)
        outcome_error = outcome.error
        album_search_performed = False
        album_ids: tuple[int, ...] = ()
        album_candidates: tuple[AlbumCandidate, ...] = ()
        if outcome.error is not None:
            status = ResultStatus.ERROR
            master_ids: tuple[int, ...] = ()
        else:
            master_ids = tuple(sorted(set(outcome.master_ids)))
            if not master_ids:
                album_search_performed = True
                album_outcome = adapter.search_albums(record.params)
                if album_outcome.error is not None:
                    status = ResultStatus.ERROR
                    outcome_error = album_outcome.error
                else:
                    status = ResultStatus.NOT_FOUND
                    outcome_error = None
                    album_ids = tuple(sorted(set(album_outcome.release_ids)))
                    album_candidate_by_id = {
                        candidate.release_id: candidate
                        for candidate in album_outcome.candidates
                        if candidate.release_id in album_ids
                    }
                    album_candidates = tuple(
                        album_candidate_by_id.get(
                            release_id,
                            AlbumCandidate(release_id=release_id),
                        )
                        for release_id in album_ids
                    )
            elif len(master_ids) == 1:
                status = ResultStatus.OK
            else:
                status = ResultStatus.MULTIPLE

        candidate_by_id = {
            candidate.master_id: candidate
            for candidate in outcome.candidates
            if candidate.master_id in master_ids
        }
        candidates = tuple(
            candidate_by_id.get(
                master_id,
                MasterCandidate(master_id=master_id),
            )
            for master_id in master_ids
        )

        results.append(
            SearchResult(
                position=record.position,
                query=record.params,
                status=status,
                master_ids=master_ids,
                error=outcome_error,
                candidates=candidates,
                album_search_performed=album_search_performed,
                album_ids=album_ids,
                album_candidates=album_candidates,
            )
        )
        if on_progress is not None:
            on_progress(len(results), len(validated.records))

    return SearchSummary(list_name=validated.list_name, results=tuple(results))

