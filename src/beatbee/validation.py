import json
from pathlib import Path
from typing import Any

from .models import (
    DISCOGS_RESOURCE_TYPES,
    SearchRecord,
    ValidatedList,
    immutable_params,
)


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
RECORD_METADATA_KEYS = frozenset({"master_id"})


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

        unknown = (
            set(record)
            - ALLOWED_SEARCH_PARAMS
            - RESERVED_PARAMS
            - RECORD_METADATA_KEYS
        )
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

        raw_types = record.get("type", "master")
        if isinstance(raw_types, str):
            search_types = (raw_types,)
        elif isinstance(raw_types, list) and raw_types:
            search_types = tuple(raw_types)
        else:
            raise InputValidationError(
                f"Record {position} type must be a resource type or a nonempty array."
            )
        if any(
            not isinstance(resource_type, str)
            or resource_type not in DISCOGS_RESOURCE_TYPES
            for resource_type in search_types
        ):
            raise InputValidationError(
                f"Record {position} type values must be one of: "
                f"{', '.join(DISCOGS_RESOURCE_TYPES)}."
            )
        if len(set(search_types)) != len(search_types):
            raise InputValidationError(
                f"Record {position} type values must not contain duplicates."
            )
        if "master_id" in record:
            master_id = record["master_id"]
            if (
                isinstance(master_id, bool)
                or not isinstance(master_id, int)
                or master_id <= 0
            ):
                raise InputValidationError(
                    f"Record {position} master_id must be a positive integer."
                )
        if not any(key not in {"type", "master_id"} for key in record):
            raise InputValidationError(
                f"Record {position} must include at least one search parameter."
            )

        params: dict[str, str | int] = {}
        for key, value in record.items():
            if key in {"type", "master_id"}:
                continue
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
            SearchRecord(
                position=position,
                params=immutable_params(params),
                search_types=search_types,
            )
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
