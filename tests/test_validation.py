import unittest
from pathlib import Path
import tempfile

from beatbee.validation import InputValidationError, load_input, validate_document


class ValidationTests(unittest.TestCase):
    def test_accepts_unicode_and_preserves_query(self) -> None:
        validated = validate_document(
            {
                "list_name": "A 100 legfontosabb magyar lemez",
                "records": [
                    {
                        "artist": "Gábor Szabó",
                        "release_title": "Dreams",
                        "year": "1968",
                    }
                ],
            }
        )

        self.assertEqual(validated.list_name, "A 100 legfontosabb magyar lemez")
        self.assertEqual(validated.records[0].position, 1)
        self.assertEqual(validated.records[0].params["type"], "master")
        self.assertEqual(validated.records[0].params["artist"], "Gábor Szabó")

    def test_accepts_redundant_master_type(self) -> None:
        validated = validate_document(
            {"list_name": "Test", "records": [{"title": "Album", "type": "master"}]}
        )
        self.assertEqual(validated.records[0].params["type"], "master")

    def test_accepts_single_and_multiple_resource_types(self) -> None:
        for raw_type, expected in (
            ("release", ("release",)),
            (["master", "release"], ("master", "release")),
        ):
            with self.subTest(raw_type=raw_type):
                validated = validate_document(
                    {
                        "list_name": "Test",
                        "records": [{"title": "Album", "type": raw_type}],
                    }
                )
                self.assertEqual(validated.records[0].search_types, expected)

    def test_defaults_search_type_to_master(self) -> None:
        validated = validate_document(
            {"list_name": "Test", "records": [{"title": "Album"}]}
        )
        self.assertEqual(validated.records[0].search_types, ("master",))

    def test_exported_master_id_is_metadata_not_a_search_parameter(self) -> None:
        validated = validate_document(
            {
                "list_name": "Test",
                "records": [{"title": "Album", "master_id": 42}],
            }
        )
        self.assertEqual(validated.records[0].params["title"], "Album")
        self.assertNotIn("master_id", validated.records[0].params)

        with self.assertRaises(InputValidationError):
            validate_document(
                {
                    "list_name": "Test",
                    "records": [{"title": "Album", "master_id": "42"}],
                }
            )

    def test_rejects_invalid_or_duplicate_search_types(self) -> None:
        for value in ([], ["master", "master"], "unknown", ["artist", 1]):
            with self.subTest(value=value):
                with self.assertRaises(InputValidationError):
                    validate_document(
                        {
                            "list_name": "Test",
                            "records": [{"title": "Album", "type": value}],
                        }
                    )

    def test_rejects_unknown_and_reserved_keys(self) -> None:
        for record in (
            {"title": "Album", "unknown": "value"},
            {"title": "Album", "page": 2},
            {"title": "Album", "per_page": 100},
        ):
            with self.subTest(record=record):
                with self.assertRaises(InputValidationError):
                    validate_document({"list_name": "Test", "records": [record]})

    def test_rejects_empty_or_malformed_documents(self) -> None:
        invalid = (
            None,
            {},
            {"list_name": "", "records": [{"title": "Album"}]},
            {"list_name": "Test", "records": []},
            {"list_name": "Test", "records": [{}]},
            {"list_name": "Test", "records": [{"type": "master"}]},
            {"list_name": "Test", "records": [{"master_id": 42}]},
            {"list_name": "Test", "records": [{"title": []}]},
        )
        for document in invalid:
            with self.subTest(document=document):
                with self.assertRaises(InputValidationError):
                    validate_document(document)

    def test_duplicate_entries_and_positions_are_preserved(self) -> None:
        records = [{"title": "Album"}, {"title": "Album"}]
        validated = validate_document({"list_name": "Test", "records": records})
        self.assertEqual(
            [record.position for record in validated.records],
            [1, 2],
        )

    def test_load_malformed_json_has_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text('{"list_name":', encoding="utf-8")
            with self.assertRaises(InputValidationError):
                load_input(path)

    def test_validation_does_not_mutate_the_source_document(self) -> None:
        document = {
            "list_name": "Test",
            "records": [{"artist": "Omega"}],
        }
        original = {
            "list_name": "Test",
            "records": [{"artist": "Omega"}],
        }

        validate_document(document)

        self.assertEqual(document, original)


if __name__ == "__main__":
    unittest.main()
