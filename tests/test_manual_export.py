import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from beatbee.cli import EXIT_OK, EXIT_PUBLISHING_FAILED, EXIT_UNRESOLVED, main
from beatbee.search import FakeSearchAdapter, SearchOutcome
from beatbee.summary import ManifestExporter
from beatbee.models import ResultStatus, SearchResult, SearchSummary


class ManualExportTests(unittest.TestCase):
    def write_input(self, content: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "input.json"
        path.write_text(content, encoding="utf-8")
        return path

    def test_json_export_preserves_name_and_order(self) -> None:
        summary = SearchSummary(
            list_name="Unicode Liste",
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
            {"list_name": "Unicode Liste", "master_ids": [42, 7]},
        )

    def test_markdown_export_has_ordered_clickable_links(self) -> None:
        summary = SearchSummary(
            list_name="My List",
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
            path = Path(directory) / "manifest.md"
            ManifestExporter().export_markdown(summary, path)
            text = path.read_text(encoding="utf-8")

        self.assertIn("# My List", text)
        self.assertIn(
            "1. [42](https://www.discogs.com/master/42)",
            text,
        )
        self.assertIn(
            "2. [7](https://www.discogs.com/master/7)",
            text,
        )
        self.assertIn("does not publish", text)

    def test_export_is_blocked_for_not_found(self) -> None:
        path = self.write_input(
            '{"list_name":"Test","records":[{"title":"Album"}]}'
        )
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "manifest.md"
            with contextlib.redirect_stdout(output):
                code = main(
                    ["export", str(path), "--format", "markdown", "--output", str(target)],
                    adapter=FakeSearchAdapter((SearchOutcome(),)),
                )
            self.assertFalse(target.exists())

        self.assertEqual(code, EXIT_UNRESOLVED)

    def test_export_all_ok_never_calls_publisher(self) -> None:
        path = self.write_input(
            '{"list_name":"Test","records":[{"title":"Album"}]}'
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "manifest.json"
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(
                    ["export", str(path), "--output", str(target)],
                    adapter=FakeSearchAdapter((SearchOutcome(master_ids=(42,)),)),
                )
            self.assertTrue(target.exists())

        self.assertEqual(code, EXIT_OK)
        self.assertIn("not proof", output.getvalue())


if __name__ == "__main__":
    unittest.main()
