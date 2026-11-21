import unittest

from beatbee.gate import can_publish
from beatbee.models import ResultStatus, SearchResult, SearchSummary


class GateTests(unittest.TestCase):
    def test_all_ok_is_required(self) -> None:
        ok = SearchSummary(
            list_name="Test",
            results=(SearchResult(
                position=1,
                query={"title": "A"},
                status=ResultStatus.OK,
                master_ids=(1,),
            ),),
        )
        blocked = SearchSummary(
            list_name="Test",
            results=ok.results
            + (SearchResult(
                position=2,
                query={"title": "B"},
                status=ResultStatus.ERROR,
                error="timeout",
            ),),
        )

        self.assertTrue(can_publish(ok))
        self.assertFalse(can_publish(blocked))


if __name__ == "__main__":
    unittest.main()
