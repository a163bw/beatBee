import unittest

from beatbee.models import ResultStatus, SearchResult, SearchSummary
from beatbee.publisher import UnavailablePublisher


class PublisherTests(unittest.TestCase):
    def test_unavailable_publisher_never_confirms_success(self) -> None:
        summary = SearchSummary(
            list_name="Test",
            results=(SearchResult(
                position=1,
                query={"title": "A"},
                status=ResultStatus.OK,
                master_ids=(42,),
            ),),
        )

        outcome = UnavailablePublisher().publish(summary)

        self.assertFalse(outcome.confirmed)
        self.assertIn("Publishing unavailable", outcome.message)

    def test_unavailable_publisher_does_not_export_blocked_summary(self) -> None:
        summary = SearchSummary(
            list_name="Test",
            results=(SearchResult(
                position=1,
                query={"title": "A"},
                status=ResultStatus.NOT_FOUND,
            ),),
        )

        outcome = UnavailablePublisher().publish(summary)

        self.assertFalse(outcome.confirmed)
        self.assertIn("blocked", outcome.message)


if __name__ == "__main__":
    unittest.main()
