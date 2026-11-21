import unittest
import json
import tempfile
from pathlib import Path

from beatbee.html_report import render_html_report
from beatbee.models import (
    AlbumCandidate,
    MasterCandidate,
    ResultStatus,
    SearchResult,
    SearchSummary,
)
from beatbee.summary import (
    ManifestExporter,
    build_master_manifest,
    format_human,
    format_resolved_masters,
    summary_to_dict,
)


class SummaryTests(unittest.TestCase):
    def test_html_report_escapes_data_and_links_ranked_candidates(self) -> None:
        summary = SearchSummary(
            list_name='Liste </script><script>alert("x")</script>',
            results=(
                SearchResult(
                    1,
                    {"artist": "Ä & Ω"},
                    ResultStatus.MULTIPLE,
                    (1, 2, 3, 4),
                    candidates=tuple(
                        MasterCandidate(master_id=i, title=f"Title <{i}>", year="1999")
                        for i in (4, 3, 2, 1)
                    ),
                ),
                SearchResult(2, {"q": "missing"}, ResultStatus.ERROR,
                             error="<unsafe>"),
            ),
        )
        report = render_html_report(summary)
        self.assertIn("Liste &lt;/script&gt;&lt;script&gt;", report)
        self.assertIn("&lt;unsafe&gt;", report)
        self.assertNotIn('<script>alert("x")</script>', report)
        self.assertIn('href="https://www.discogs.com/master/1"', report)
        self.assertIn('href="https://www.discogs.com/master/3"', report)
        self.assertNotIn('href="https://www.discogs.com/master/4"', report)
        payload = report.split('id="beatbee-summary">', 1)[1].split("</script>", 1)[0]
        data = json.loads(payload)
        self.assertEqual(data["list_name"], summary.list_name)
        self.assertEqual(data["results"][0]["position"], 1)
        self.assertNotIn("manifest", data)

    def test_html_report_embeds_manifest_only_when_all_ok(self) -> None:
        summary = SearchSummary(
            list_name="Test",
            results=(
                SearchResult(1, {"q": "a"}, ResultStatus.OK, (42,)),
                SearchResult(2, {"q": "b"}, ResultStatus.OK, (7,)),
            ),
        )
        report = render_html_report(summary)
        payload = report.split('id="beatbee-summary">', 1)[1].split("</script>", 1)[0]
        self.assertEqual(json.loads(payload)["manifest"],
                         {"list_name": "Test", "master_ids": [42, 7]})

    def test_resolved_masters_reports_query_fallback_and_missing_metadata(self) -> None:
        summary = SearchSummary(
            list_name="Test",
            results=(
                SearchResult(1, {"artist": "Ωmega", "release_title": "Album"},
                             ResultStatus.OK, (42,)),
                SearchResult(2, {"q": "Other"}, ResultStatus.OK, (7,)),
                SearchResult(3, {"title": "Missing"}, ResultStatus.NOT_FOUND),
            ),
        )

        text = format_resolved_masters(summary)

        self.assertIn("Artist: Ωmega (search query)", text)
        self.assertIn("Album: Album (search query)", text)
        self.assertIn("Artist: unavailable", text)
        self.assertIn("Album: unavailable", text)
        self.assertEqual(text.count("Master ID:"), 2)
        self.assertNotIn("[3]", text)

    def test_resolved_masters_reports_when_none_found(self) -> None:
        summary = SearchSummary(
            list_name="Test",
            results=(SearchResult(1, {"q": "missing"}, ResultStatus.NOT_FOUND),),
        )
        self.assertIn("No resolved Masters.", format_resolved_masters(summary))

    def test_group_counts_include_zero_values_and_multiple_candidates(self) -> None:
        summary = SearchSummary(
            list_name="Test",
            results=(
                SearchResult(
                    position=1,
                    query={"title": "Album"},
                    status=ResultStatus.MULTIPLE,
                    master_ids=(20, 10),
                    candidates=(
                        MasterCandidate(
                            master_id=20,
                            title="A",
                            year="1970",
                        ),
                        MasterCandidate(
                            master_id=10,
                            title="B",
                            year="1969",
                        ),
                    ),
                ),
            ),
        )

        machine = summary_to_dict(summary)

        self.assertEqual(
            machine["counts"],
            {"OK": 0, "NOT_FOUND": 0, "MULTIPLE": 1, "ERROR": 0},
        )
        self.assertEqual(len(machine["results"][0]["candidates"]), 2)
        self.assertIn("https://www.discogs.com/master/", format_human(summary))

    def test_release_fallback_is_displayed_but_not_resolved_as_master(self) -> None:
        summary = SearchSummary(
            list_name="Test",
            results=(
                SearchResult(
                    position=1,
                    query={"title": "Album"},
                    status=ResultStatus.NOT_FOUND,
                    album_search_performed=True,
                    album_ids=(123,),
                    album_candidates=(
                        AlbumCandidate(123, title="Artist - Album", year="1970"),
                    ),
                ),
            ),
        )

        payload = summary_to_dict(summary)
        report = render_html_report(summary)

        self.assertFalse(summary.all_ok)
        self.assertNotIn("manifest", payload)
        self.assertEqual(
            payload["results"][0]["album_fallback"]["release_ids"],
            [123],
        )
        self.assertIn("https://www.discogs.com/release/123", report)
        self.assertNotIn("https://www.discogs.com/master/123", report)

    def test_manifest_is_blocked_for_partial_summary(self) -> None:
        summary = SearchSummary(
            list_name="Test",
            results=(
                SearchResult(
                    position=1,
                    query={"title": "Album"},
                    status=ResultStatus.NOT_FOUND,
                ),
            ),
        )

        with self.assertRaises(ValueError):
            build_master_manifest(summary)

    def test_manifest_preserves_order_for_all_ok(self) -> None:
        summary = SearchSummary(
            list_name="Test",
            results=(
                SearchResult(
                    position=1,
                    query={"title": "A"},
                    status=ResultStatus.OK,
                    master_ids=(42,),
                ),
                SearchResult(
                    position=2,
                    query={"title": "B"},
                    status=ResultStatus.OK,
                    master_ids=(7,),
                ),
            ),
        )

        manifest = build_master_manifest(summary)
        self.assertEqual(manifest.list_name, "Test")
        self.assertEqual(manifest.master_ids, (42, 7))

    def test_manifest_exporter_writes_exact_json(self) -> None:
        summary = SearchSummary(
            list_name="Unicode 漢字",
            results=(
                SearchResult(
                    position=1,
                    query={"title": "A"},
                    status=ResultStatus.OK,
                    master_ids=(42,),
                ),
                SearchResult(
                    position=2,
                    query={"title": "B"},
                    status=ResultStatus.OK,
                    master_ids=(7,),
                ),
            ),
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            ManifestExporter().export_json(summary, path)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(
            payload,
            {"list_name": "Unicode 漢字", "master_ids": [42, 7]},
        )


if __name__ == "__main__":
    unittest.main()
