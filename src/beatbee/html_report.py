import html
import json

from .models import ResultStatus, SearchResult, SearchSummary
from .ranking import rank_candidates
from .summary import (
    build_master_manifest,
    master_url,
    release_url,
    summary_to_dict,
)


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _master_link(master_id: int) -> str:
    url = _escape(master_url(master_id))
    return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>'


def _release_link(release_id: int) -> str:
    url = _escape(release_url(release_id))
    return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>'


def _result_card(result: SearchResult) -> str:
    query = _escape(json.dumps(dict(result.query), ensure_ascii=False, sort_keys=True))
    details = ""
    if result.status is ResultStatus.OK:
        details = f"<p>Master ID: {result.master_ids[0]} · {_master_link(result.master_ids[0])}</p>"
    elif result.status is ResultStatus.MULTIPLE:
        candidates = []
        for candidate in rank_candidates(result.candidates, result.query)[:3]:
            title = _escape(candidate.title or f"Master {candidate.master_id}")
            year = f" ({_escape(candidate.year)})" if candidate.year else ""
            candidates.append(
                f"<li>{title}{year} · Master ID: {candidate.master_id}<br>"
                f"{_master_link(candidate.master_id)}</li>"
            )
        details = (
            f"<p>{len(result.master_ids)} unique Masters; suggestions only:</p>"
            f"<ul>{''.join(candidates)}</ul>"
        )
    elif result.status is ResultStatus.NOT_FOUND and result.album_search_performed:
        releases = []
        for candidate in result.album_candidates[:3]:
            title = _escape(candidate.title or f"Release {candidate.release_id}")
            year = f" ({_escape(candidate.year)})" if candidate.year else ""
            releases.append(
                f"<li>{title}{year} · Release ID: {candidate.release_id}<br>"
                f"{_release_link(candidate.release_id)}</li>"
            )
        details = (
            f"<p>No Masters found. Album/release fallback: "
            f"{len(result.album_ids)} releases; fallback results are not "
            f"Master matches.</p>"
            f"{'<ul>' + ''.join(releases) + '</ul>' if releases else ''}"
        )
    elif result.error:
        details = f'<p class="error">{_escape(result.error)}</p>'
    return (
        f'<article class="result"><h3>#{result.position}</h3>'
        f'<pre>{query}</pre>{details}</article>'
    )


def _resolved_row(result: SearchResult) -> str:
    master_id = result.master_ids[0]
    candidate = next(
        (item for item in result.candidates if item.master_id == master_id), None
    )

    def field(name: str, query_key: str) -> str:
        value = getattr(candidate, name) if candidate is not None else None
        if value:
            return f"{_escape(value)} <small>(parsed from Discogs title)</small>"
        if query_key in result.query:
            return f"{_escape(result.query[query_key])} <small>(search query)</small>"
        return "Unavailable"

    return (
        f"<tr><td>{result.position}</td><td>{field('artist', 'artist')}</td>"
        f"<td>{field('release_title', 'release_title')}</td>"
        f"<td>{master_id}</td><td>{_master_link(master_id)}</td></tr>"
    )


def render_html_report(summary: SearchSummary) -> str:
    grouped = summary.grouped()
    counts = "".join(
        f'<div class="metric"><span>{_escape(label)}</span><strong>{count}</strong></div>'
        for label, count in (
            ("Total", len(summary.results)),
            *((status.value, sum(r.status is status for r in summary.results))
              for status in ResultStatus),
        )
    )
    groups = []
    for status, results in grouped.items():
        cards = "".join(_result_card(result) for result in results)
        if not cards:
            cards = '<p class="empty">No entries.</p>'
        groups.append(
            f'<section class="group" id="{status.value.lower()}">'
            f"<h2>{status.value} <span>{len(results)}</span></h2>{cards}</section>"
        )

    resolved = "".join(
        _resolved_row(result)
        for result in summary.results
        if result.status is ResultStatus.OK
    )
    if not resolved:
        resolved = '<tr><td colspan="5">No resolved Masters.</td></tr>'

    data = summary_to_dict(summary)
    if summary.all_ok:
        data["manifest"] = build_master_manifest(summary).to_dict()
    json_data = json.dumps(data, ensure_ascii=False, sort_keys=True).replace("<", "\\u003c")
    title = _escape(summary.list_name)
    status_text = "All searches resolved" if summary.all_ok else "Blocked: unresolved searches"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BeatBee — {title}</title>
<style>
  :root {{ color-scheme: light; font-family: system-ui, sans-serif; color: #172033; background: #f3f5f9; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; }}
  main {{ max-width: 1100px; margin: auto; padding: 2rem 1rem 4rem; }}
  .eyebrow {{ color: #6355c7; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }}
  h1 {{ margin: .25rem 0; overflow-wrap: anywhere; }}
  .status {{ color: #475569; margin-bottom: 1.5rem; }}
  .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(125px, 1fr)); gap: .75rem; }}
  .metric, .group, .resolved {{ background: white; border: 1px solid #dfe4ee; border-radius: 12px; }}
  .metric {{ padding: 1rem; }}
  .metric span, small {{ display: block; color: #64748b; }}
  .metric strong {{ font-size: 1.7rem; }}
  .group, .resolved {{ margin-top: 1rem; padding: 1.25rem; }}
  h2 {{ margin: 0 0 1rem; }}
  h2 span {{ color: #64748b; font-size: .8em; }}
  h3 {{ margin: 0 0 .5rem; }}
  .result {{ border-top: 1px solid #e6eaf1; padding: 1rem 0; }}
  .result:last-child {{ padding-bottom: 0; }}
  pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #f6f7fb; padding: .75rem; border-radius: 6px; }}
  a {{ color: #4338a3; overflow-wrap: anywhere; }}
  li {{ margin: .5rem 0; }}
  .error {{ color: #a32132; }}
  .empty {{ color: #64748b; }}
  .table-wrap {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; text-align: left; }}
  th, td {{ border-bottom: 1px solid #e6eaf1; padding: .75rem; vertical-align: top; }}
  th {{ color: #475569; }}
</style>
</head>
<body><main>
<div class="eyebrow">BeatBee · Search report</div>
<h1>{title}</h1>
<p class="status">{status_text} · No list was published by this report.</p>
<div class="metrics">{counts}</div>
{''.join(groups)}
<section class="resolved"><h2>Resolved Masters</h2>
<p>Successful searches in original input order; not a publication confirmation.</p>
<div class="table-wrap"><table><thead><tr><th>Position</th><th>Artist</th>
<th>Album</th><th>Master ID</th><th>Discogs URL</th></tr></thead>
<tbody>{resolved}</tbody></table></div></section>
<script type="application/json" id="beatbee-summary">{json_data}</script>
</main></body></html>
"""
