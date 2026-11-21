import unittest

from beatbee.models import AlbumCandidate, ResultStatus, SearchParams
from beatbee.search import (
    AlbumSearchOutcome,
    FakeSearchAdapter,
    SearchOutcome,
)
from beatbee.service import search_all
from beatbee.validation import validate_document


class ServiceTests(unittest.TestCase):
    def test_album_fallback_runs_only_after_complete_zero_master_search(self) -> None:
        class Adapter:
            def __init__(self) -> None:
                self.master_outcomes = iter(
                    (
                        SearchOutcome(),
                        SearchOutcome(master_ids=(10,)),
                        SearchOutcome(error="timeout"),
                        SearchOutcome(master_ids=(20, 21)),
                    )
                )
                self.album_calls: list[SearchParams] = []

            def search(self, params: SearchParams) -> SearchOutcome:
                return next(self.master_outcomes)

            def search_albums(
                self,
                params: SearchParams,
            ) -> AlbumSearchOutcome:
                self.album_calls.append(params)
                return AlbumSearchOutcome(
                    release_ids=(23,),
                    candidates=(AlbumCandidate(23, title="Omega - Album"),),
                )

        validated = validate_document(
            {
                "list_name": "Test",
                "records": [
                    {"artist": "Omega", "release_title": "Album"},
                    {"title": "Already a Master"},
                    {"title": "Master search error"},
                    {"title": "Multiple Masters"},
                ],
            }
        )
        adapter = Adapter()

        summary = search_all(validated, adapter)

        self.assertEqual(len(adapter.album_calls), 1)
        self.assertEqual(adapter.album_calls[0]["artist"], "Omega")
        self.assertEqual(
            [result.status for result in summary.results],
            [
                ResultStatus.NOT_FOUND,
                ResultStatus.OK,
                ResultStatus.ERROR,
                ResultStatus.MULTIPLE,
            ],
        )
        self.assertEqual(summary.results[0].album_ids, (23,))
        self.assertTrue(summary.results[0].album_search_performed)
        self.assertEqual(summary.results[2].error, "timeout")
        self.assertFalse(summary.results[3].album_search_performed)

    def test_album_fallback_error_is_an_error_not_not_found(self) -> None:
        adapter = FakeSearchAdapter(
            (SearchOutcome(),),
            album_outcomes=(AlbumSearchOutcome(error="release search failed"),),
        )
        validated = validate_document(
            {"list_name": "Test", "records": [{"title": "Album"}]}
        )

        result = search_all(validated, adapter).results[0]

        self.assertEqual(result.status, ResultStatus.ERROR)
        self.assertEqual(result.error, "release search failed")
        self.assertEqual(result.album_ids, ())

    def test_classifies_zero_one_and_multiple_unique_ids(self) -> None:
        document = {
            "list_name": "Test",
            "records": [{"title": "A"}, {"title": "B"}, {"title": "C"}],
        }
        validated = validate_document(document)
        adapter = FakeSearchAdapter(
            (
                SearchOutcome(),
                SearchOutcome(master_ids=(10,)),
                SearchOutcome(master_ids=(30, 20, 30)),
            )
        )

        summary = search_all(validated, adapter)

        self.assertEqual(
            [result.status for result in summary.results],
            [
                ResultStatus.NOT_FOUND,
                ResultStatus.OK,
                ResultStatus.MULTIPLE,
            ],
        )
        self.assertEqual(summary.results[2].master_ids, (20, 30))
        self.assertFalse(summary.all_ok)

    def test_errors_do_not_become_not_found_or_ok(self) -> None:
        validated = validate_document(
            {"list_name": "Test", "records": [{"title": "A"}, {"title": "B"}]}
        )
        adapter = FakeSearchAdapter(
            (
                SearchOutcome(error="timeout"),
                SearchOutcome(master_ids=(10,)),
            )
        )

        summary = search_all(validated, adapter)

        self.assertEqual(summary.results[0].status, ResultStatus.ERROR)
        self.assertEqual(summary.results[0].master_ids, ())
        self.assertTrue(summary.results[1].status is ResultStatus.OK)

    def test_all_entries_are_searched_after_errors(self) -> None:
        validated = validate_document(
            {
                "list_name": "Test",
                "records": [{"title": "A"}, {"title": "B"}, {"title": "C"}],
            }
        )
        adapter = FakeSearchAdapter(
            (
                SearchOutcome(error="timeout"),
                SearchOutcome(),
                SearchOutcome(master_ids=(7,)),
            )
        )

        summary = search_all(validated, adapter)

        self.assertEqual(len(summary.results), 3)


if __name__ == "__main__":
    unittest.main()
