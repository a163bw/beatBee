import json
from pathlib import Path
from typing import Any

from .models import SearchRecord, ValidatedList, immutable_params


ALLOWED_SEARCH_PARAMS = frozenset(
    {
        "q",
        "artist",
        "release_title",
        "title",
        "year",
        "genre",
        "style",
        "country",
        "format",
        "label",
        "catno",
        "barcode",
        "track",
        "credit",
        "anv",
        "submitter",
        "contributor",
        "type",
    }
)
RESERVED_PARAMS = frozenset({"page", "per_page"})


class InputValidationError(ValueError):
    pass


def validate_document(document: Any) -> ValidatedList:
    if not isinstance(document, dict):
        raise InputValidationError("The input JSON root must be an object.")

    unknown_root = set(document) - {"list_name", "records"}
    if unknown_root:
        raise InputValidationError(
            f"Unknown root keys: {', '.join(sorted(unknown_root))}"
        )

    list_name = document.get("list_name")
    if not isinstance(list_name, str) or not list_name.strip():
        raise InputValidationError("list_name must be a nonempty Unicode string.")

    records = document.get("records")
    if not isinstance(records, list) or not records:
        raise InputValidationError("records must be a nonempty array.")

    validated_records: list[SearchRecord] = []
    for position, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise InputValidationError(
                f"Record {position} must be an object."
            )
        if not record:
            raise InputValidationError(f"Record {position} must not be empty.")

        unknown = set(record) - ALLOWED_SEARCH_PARAMS - RESERVED_PARAMS
        if unknown:
            raise InputValidationError(
                f"Record {position} has unknown or reserved keys: "
                f"{', '.join(sorted(unknown))}"
            )

        reserved = set(record) & RESERVED_PARAMS
        if reserved:
            raise InputValidationError(
                f"Record {position} uses reserved pagination key(s): "
                f"{', '.join(sorted(reserved))}"
            )

        if "type" in record and record["type"] != "master":
            raise InputValidationError(
                f"Record {position} has type={record['type']!r}; only "
                "'master' or no type is allowed."
            )

        params: dict[str, str | int] = {}
        for key, value in record.items():
            if isinstance(value, bool) or not isinstance(value, (str, int)):
                raise InputValidationError(
                    f"Record {position} parameter {key!r} must be a string or integer."
                )
            if isinstance(value, str) and not value.strip():
                raise InputValidationError(
                    f"Record {position} parameter {key!r} must not be empty."
                )
            params[key] = value

        params["type"] = "master"
        validated_records.append(
            SearchRecord(position=position, params=immutable_params(params))
        )

    return ValidatedList(
        list_name=list_name,
        records=tuple(validated_records),
    )


def load_input(path: str | Path) -> ValidatedList:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            document = json.load(handle)
    except json.JSONDecodeError as exc:
        raise InputValidationError(
            f"Malformed JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise InputValidationError(f"Could not read input JSON: {exc}") from exc
    return validate_document(document)
