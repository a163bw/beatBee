"""Standalone BeatBee command-line entry point."""

from pathlib import Path
import sys


SOURCE_ROOT = Path(__file__).resolve().parent / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from beatbee.cli import main
from beatbee.token import load_discogs_token


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent
    token_file = project_root / "discogsToken.json"
    token = load_discogs_token(file_path=token_file)
    args = sys.argv[1:] or ["validate", str(project_root / "discogsList.json")]
    raise SystemExit(main(args, token=token))
