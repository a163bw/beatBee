import json
import os
from pathlib import Path


def load_discogs_token(
    *,
    environment_name: str = "DISCOGS_TOKEN",
    file_path: str | Path = "discogsToken.json",
) -> str | None:
    token = os.getenv(environment_name)
    if token:
        return token.strip() or None

    path = Path(file_path)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    token = payload.get("discogs_token")
    return token.strip() if isinstance(token, str) and token.strip() else None
