import unicodedata
from typing import Mapping

from .models import MasterCandidate


def normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def rank_candidates(
    candidates: tuple[MasterCandidate, ...] | list[MasterCandidate],
    query: Mapping[str, str | int | tuple[str, ...]],
) -> tuple[MasterCandidate, ...]:
    def text_match(field: str, candidate_value: str | None) -> bool:
        query_value = query.get(field)
        if candidate_value is None or not isinstance(query_value, (str, int)):
            return False
        return normalize(str(query_value)) == normalize(candidate_value)

    def match_count(candidate: MasterCandidate) -> int:
        fields = (
            ("artist", candidate.artist),
            ("release_title", candidate.release_title),
            ("title", candidate.release_title),
            ("year", candidate.year),
        )
        count = sum(text_match(field, value) for field, value in fields)
        return count

    def sort_key(candidate: MasterCandidate) -> tuple[object, ...]:
        release_match = text_match("release_title", candidate.release_title)
        artist_match = text_match("artist", candidate.artist)
        year_match = text_match("year", candidate.year)
        return (
            -match_count(candidate),
            -int(release_match),
            -int(artist_match),
            -int(year_match),
            candidate.master_id,
        )

    return tuple(sorted(candidates, key=sort_key))
