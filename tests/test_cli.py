import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from beatbee.cli import (
    EXIT_INVALID_INPUT,
    EXIT_PUBLISHING_FAILED,
    EXIT_UNRESOLVED,
    main,
)
from beatbee.models import MasterCandidate, SearchParams
from beatbee.search import FakeSearchAdapter, SearchOutcome
from beatbee.publisher import PublicationOutcome


class CliTests(unittest.TestCase):
    def write_input(self, content: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "input.json"
        path.write_text(content, encoding="utf-8")
        return path

    def test_invalid_input_has_exit_two_and_no_search(self) -> None:
        path = self.write_input('{"list_name":"Test","records":[{"type":"cassette"}]}')
        adapter = FakeSearchAdapter()
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = main(["validate", str(path)], adapter=adapter)

        self.assertEqual(code, EXIT_INVALID_INPUT)
        self.assertEqual(output.getvalue(), "")

    def test_validate_unresolved_returns_one(self) -> None:
        path = self.write_input(
            '{"list_name":"Test","records":[{"title":"Album"},{"title":"Other"}]}'
        )
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = main(
                ["validate", str(path)],
                adapter=FakeSearchAdapter(
                    (SearchOutcome(master_ids=(1,)), SearchOutcome())
                ),
            )

        self.assertEqual(code, EXIT_UNRESOLVED)
        report = path.with_name("input.summary.html").read_text(encoding="utf-8")
        self.assertIn('<section class="group" id="not_found">', report)
        self.assertIn("HTML report:", output.getvalue())

    def test_progress_updates_during_search_even_when_a_record_errors(self) -> None:
        path = self.write_input(
            '{"list_name":"Test","records":'
            '[{"title":"A"},{"title":"B"},{"title":"C"}]}'
        )
        progress = io.StringIO()
        observed: list[str] = []

        class ObservedAdapter(FakeSearchAdapter):
            def search(self, params: SearchParams) -> SearchOutcome:
                observed.append(progress.getvalue())
                return super().search(params)

        adapter = ObservedAdapter((
            SearchOutcome(master_ids=(1,)),
            SearchOutcome(error="timeout"),
            SearchOutcome(),
        ))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(progress):
            code = main(["validate", str(path)], adapter=adapter)

        self.assertEqual(code, 3)
        self.assertIn("0% (0/3 processed)", observed[0])
        self.assertIn("33% (1/3 processed)", observed[1])
        self.assertIn("66% (2/3 processed)", observed[2])
        self.assertIn("100% (3/3 processed)", progress.getvalue())

    def test_progress_overwrites_terminal_line(self) -> None:
        path = self.write_input('{"list_name":"Test","records":[{"title":"A"}]}')

        class Terminal(io.StringIO):
            def isatty(self) -> bool:
                return True

        progress = Terminal()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(progress):
            main(
                ["validate", str(path)],
                adapter=FakeSearchAdapter((SearchOutcome(master_ids=(1,)),)),
            )

        self.assertIn("0% (0/1 processed)\r", progress.getvalue())
        self.assertTrue(progress.getvalue().endswith("100% (1/1 processed)\n"))

    def test_summary_finishes_with_successful_masters_even_when_blocked(self) -> None:
        path = self.write_input(
            '{"list_name":"Test","records":['
            '{"artist":"Omega","release_title":"Album"},'
            '{"title":"Missing"},{"q":"Other"},'
            '{"title":"Many"},{"title":"Failure"}]}'
        )
        output = io.StringIO()
        adapter = FakeSearchAdapter((
            SearchOutcome(master_ids=(42,), candidates=(
                MasterCandidate(42, title="Omega - Album",
                                artist="Omega", release_title="Album"),
            )),
            SearchOutcome(),
            SearchOutcome(master_ids=(7,), candidates=(
                MasterCandidate(7, title="Other Artist - Other Album",
                                artist="Other Artist", release_title="Other Album"),
            )),
            SearchOutcome(master_ids=(8, 9)),
            SearchOutcome(error="timeout"),
        ))
        with contextlib.redirect_stdout(output):
            code = main(["validate", str(path)], adapter=adapter)

        text = path.with_name("input.summary.html").read_text(encoding="utf-8")
        self.assertEqual(code, 3)
        self.assertLess(text.index('id="not_found"'), text.index('id="multiple"'))
        self.assertLess(text.index('id="multiple"'), text.index('id="error"'))
        final = text.split("<h2>Resolved Masters</h2>")[-1].split("</tbody>")[0]
        self.assertIn("Omega", final)
        self.assertIn("Album", final)
        self.assertIn("<td>42</td>", final)
        self.assertIn("https://www.discogs.com/master/42", final)
        self.assertIn("Other Artist", final)
        self.assertIn("Other Album", final)
        self.assertIn("https://www.discogs.com/master/7", final)
        self.assertLess(final.index("<td>1</td>"), final.index("<td>3</td>"))
        self.assertNotIn("/master/8", final)
        self.assertNotIn("/master/9", final)

    def test_export_cannot_overwrite_input_or_html_report(self) -> None:
        path = self.write_input('{"list_name":"Test","records":[{"title":"A"}]}')
        original = path.read_bytes()
        for target in (path, path.with_name("input.summary.html")):
            with self.subTest(target=target), contextlib.redirect_stderr(io.StringIO()):
                code = main(
                    ["export", str(path), "--output", str(target)],
                    adapter=FakeSearchAdapter((SearchOutcome(master_ids=(1,)),)),
                )
            self.assertEqual(code, 3)
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(path.with_name("input.summary.html").exists())

    def test_report_write_error_blocks_publisher(self) -> None:
        path = self.write_input('{"list_name":"Test","records":[{"title":"A"}]}')

        class SpyPublisher:
            calls = 0

            def publish(self, summary: object) -> PublicationOutcome:
                self.calls += 1
                return PublicationOutcome(confirmed=True, message="published")

        publisher = SpyPublisher()
        errors = io.StringIO()
        with (
            patch("beatbee.cli.Path.write_text", side_effect=PermissionError("denied")),
            contextlib.redirect_stderr(errors),
        ):
            code = main(
                ["run", str(path)],
                adapter=FakeSearchAdapter((SearchOutcome(master_ids=(1,)),)),
                publisher=publisher,
            )
        self.assertEqual(code, 3)
        self.assertIn("Could not write HTML report", errors.getvalue())
        self.assertEqual(publisher.calls, 0)

    def test_run_all_ok_is_blocked_by_unavailable_publisher(self) -> None:
        path = self.write_input(
            '{"list_name":"Test","records":[{"title":"Album"}]}'
        )
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = main(
                ["run", str(path)],
                adapter=FakeSearchAdapter((SearchOutcome(master_ids=(42,)),)),
            )

        self.assertEqual(code, EXIT_PUBLISHING_FAILED)
        self.assertIn("Publishing unavailable", output.getvalue())
        self.assertIn("42", output.getvalue())

    def test_run_can_export_manifest_without_publishing(self) -> None:
        path = self.write_input(
            '{"list_name":"Test","records":[{"title":"Album"}]}'
        )
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "manifest.json"
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(
                    ["run", str(path), "--manifest", str(manifest_path)],
                    adapter=FakeSearchAdapter((SearchOutcome(master_ids=(42,)),)),
                )

            self.assertEqual(code, EXIT_PUBLISHING_FAILED)
            self.assertTrue(manifest_path.exists())
            self.assertIn("Manifest written", output.getvalue())

    def test_run_non_ok_never_calls_publisher(self) -> None:
        path = self.write_input(
            '{"list_name":"Test","records":[{"title":"Album"}]}'
        )

        class SpyPublisher:
            available = True
            calls = 0

            def publish(self, summary: object) -> PublicationOutcome:
                self.calls += 1
                return PublicationOutcome(
                    confirmed=True,
                    message="unexpected",
                )

        publisher = SpyPublisher()
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(
                ["run", str(path)],
                adapter=FakeSearchAdapter((SearchOutcome(),)),
                publisher=publisher,
            )

        self.assertEqual(code, EXIT_UNRESOLVED)
        self.assertEqual(publisher.calls, 0)


if __name__ == "__main__":
    unittest.main()
