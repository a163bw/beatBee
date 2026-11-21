import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import ResultStatus, SearchSummary
from .ranking import rank_candidates


def master_url(master_id: int) -> str:
    return f"https://www.discogs.com/master/{master_id}"


def release_url(release_id: int) -> str:
    return f"https://www.discogs.com/release/{release_id}"


@dataclass(frozen=True, slots=True)
class MasterManifest:
    list_name: str
    master_ids: tuple[int, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "list_name": self.list_name,
            "master_ids": list(self.master_ids),
        }


def build_master_manifest(summary: SearchSummary) -> MasterManifest:
    if not summary.all_ok:
        raise ValueError("A manifest is available only when every result is OK.")
    return MasterManifest(
        list_name=summary.list_name,
        master_ids=tuple(result.master_ids[0] for result in summary.results),
    )


class ManifestExporter:
    def export(self, summary: SearchSummary) -> MasterManifest:
        return build_master_manifest(summary)

    def export_json(
        self,
        summary: SearchSummary,
        path: str | Path,
    ) -> MasterManifest:
        manifest = build_master_manifest(summary)
        Path(path).write_text(
            json.dumps(manifest.to_dict(), ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        return manifest

    def export_markdown(
        self,
        summary: SearchSummary,
        path: str | Path,
    ) -> MasterManifest:
        manifest = build_master_manifest(summary)
        lines = [
            f"# {manifest.list_name}",
            "",
            "Create this as a manual Discogs list in the shown order.",
            "BeatBee does not publish or claim publication.",
            "",
        ]
        for position, master_id in enumerate(manifest.master_ids, start=1):
            lines.append(
                f"{position}. [{master_id}]({master_url(master_id)})"
            )
        Path(path).write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
        )
        return manifest


def summary_to_dict(summary: SearchSummary) -> dict[str, Any]:
    counts = {
        "OK": sum(result.status.value == "OK" for result in summary.results),
        "NOT_FOUND": sum(result.status.value == "NOT_FOUND" for result in summary.results),
        "MULTIPLE": sum(result.status.value == "MULTIPLE" for result in summary.results),
        "ERROR": sum(result.status.value == "ERROR" for result in summary.results),
    }
    return {
        "list_name": summary.list_name,
        "total": len(summary.results),
        "counts": counts,
        "all_ok": summary.all_ok,
        "results": [
            {
                "position": result.position,
                "query": dict(result.query),
                "status": result.status.value,
                "master_ids": list(result.master_ids),
                **({"error": result.error} if result.error is not None else {}),
                **(
                    {
                        "candidates": [
                            {
                                "master_id": candidate.master_id,
                                "title": candidate.title,
                                "year": candidate.year,
                                "url": master_url(candidate.master_id),
                            }
                            for candidate in rank_candidates(
                                result.candidates,
                                result.query,
                            )[:3]
                        ]
                    }
                    if result.status.value == "MULTIPLE"
                    else {}
                ),
                **(
                    {
                        "album_fallback": {
                            "release_ids": list(result.album_ids),
                            "candidates": [
                                {
                                    "release_id": candidate.release_id,
                                    "title": candidate.title,
                                    "year": candidate.year,
                                    "url": release_url(candidate.release_id),
                                }
                                for candidate in result.album_candidates[:3]
                            ],
                        }
                    }
                    if result.album_search_performed
                    else {}
                ),
            }
            for result in summary.results
        ],
    }


def format_human(summary: SearchSummary) -> str:
    lines = [
        f"List: {summary.list_name}",
        f"Total: {len(summary.results)}",
    ]
    grouped = summary.grouped()
    for status, results in grouped.items():
        lines.append(f"{status.value}: {len(results)}")

    lines.append(
        "Status: READY_TO_PUBLISH" if summary.all_ok else "Status: BLOCKED"
    )
    for status, results in grouped.items():
        if not results:
            continue
        lines.append("")
        lines.append(f"{status.value}")
        for result in results:
            detail = f"  [{result.position}] {json.dumps(dict(result.query), ensure_ascii=False)}"
            if result.status.value == "OK":
                detail += f" -> Master {result.master_ids[0]}"
            elif result.status.value == "MULTIPLE":
                detail += f" -> {len(result.master_ids)} Masters"
                ranked = rank_candidates(result.candidates, result.query)
                for candidate in ranked[:3]:
                    title = candidate.title or f"Master {candidate.master_id}"
                    year = f", {candidate.year}" if candidate.year else ""
                    detail += (
                        f"\n    {candidate.master_id}: {title}{year} "
                        f"{master_url(candidate.master_id)}"
                    )
            elif (
                result.status.value == "NOT_FOUND"
                and result.album_search_performed
            ):
                detail += (
                    f" -> No Masters; album/release fallback found "
                    f"{len(result.album_ids)} releases"
                )
                for candidate in result.album_candidates[:3]:
                    title = candidate.title or f"Release {candidate.release_id}"
                    year = f", {candidate.year}" if candidate.year else ""
                    detail += (
                        f"\n    {candidate.release_id}: {title}{year} "
                        f"{release_url(candidate.release_id)}"
                    )
            elif result.error:
                detail += f" -> {result.error}"
            lines.append(detail)
    return "\n".join(lines)


def format_resolved_masters(summary: SearchSummary) -> str:
    lines = ["Resolved Masters"]
    results = [result for result in summary.results if result.status is ResultStatus.OK]
    if not results:
        return "\n".join(lines + ["  No resolved Masters."])

    for result in results:
        master_id = result.master_ids[0]
        candidate = next(
            (item for item in result.candidates if item.master_id == master_id),
            None,
        )
        lines.append(f"  [{result.position}]")
        for label, field, query_field in (
            ("Artist", "artist", "artist"),
            ("Album", "release_title", "release_title"),
        ):
            value = getattr(candidate, field) if candidate is not None else None
            if value:
                description = f"{value} (parsed from Discogs title)"
            elif query_field in result.query:
                description = f"{result.query[query_field]} (search query)"
            else:
                description = "unavailable"
            lines.append(f"    {label}: {description}")
        if candidate is not None and candidate.title:
            lines.append(f"    Discogs title: {candidate.title}")
        lines.append(f"    Master ID: {master_id}")
        lines.append(f"    URL: {master_url(master_id)}")
    return "\n".join(lines)
