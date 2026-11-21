import subprocess
import sys
import json
import contextlib
import io
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from beatbee.token import load_discogs_token
from beatbee.search import FakeSearchAdapter, SearchOutcome
from beatbee.validation import validate_document


ROOT = Path(__file__).resolve().parents[1]


class MainEntryTests(unittest.TestCase):
    def test_main_prints_help_without_a_web_dependency(self) -> None:
        result = subprocess.run(
            [sys.executable, "main.py", "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("validate", result.stdout)
        self.assertIn("export", result.stdout)
        self.assertNotIn("streamlit", result.stdout.lower())

    def test_main_without_arguments_validates_and_prints_summary(self) -> None:
        document = validate_document({
            "list_name": "Test",
            "records": [
                {"artist": "Omega", "release_title": "Album"},
                {"title": "Missing"},
            ],
        })
        adapter = FakeSearchAdapter((
            SearchOutcome(master_ids=(42,)),
            SearchOutcome(),
        ))
        output = io.StringIO()
        with (
            patch.object(sys, "argv", [str(ROOT / "main.py")]),
            patch("beatbee.token.load_discogs_token", return_value="test-token"),
            patch("beatbee.cli.load_input", return_value=document) as load_input,
            patch("beatbee.cli.DiscogsSearchClient", return_value=adapter),
            patch("beatbee.cli.Path.write_text") as write_report,
            contextlib.redirect_stdout(output),
            self.assertRaises(SystemExit) as exit_error,
        ):
            runpy.run_path(str(ROOT / "main.py"), run_name="__main__")

        self.assertEqual(exit_error.exception.code, 1)
        load_input.assert_called_once_with(str(ROOT / "discogsList.json"))
        self.assertIn("HTML report:", output.getvalue())
        report = write_report.call_args.args[0]
        self.assertIn('id="not_found"', report)
        self.assertIn("Resolved Masters", report)
        self.assertIn("https://www.discogs.com/master/42", report)

    def test_token_file_loader_reads_the_supported_field(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "discogsToken.json"
            path.write_text(
                json.dumps({"discogs_token": "test-only-token"}),
                encoding="utf-8",
            )

            token = load_discogs_token(
                environment_name="BEATBEE_TEST_TOKEN",
                file_path=path,
            )

        self.assertEqual(token, "test-only-token")


if __name__ == "__main__":
    unittest.main()
