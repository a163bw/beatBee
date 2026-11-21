import json
import tempfile
import unittest
import urllib.error
import urllib.request
from email.message import Message
from email.utils import formatdate
from pathlib import Path
from typing import Any

from beatbee.discogs_client import DiscogsSearchClient


class MockResponse:
    def __init__(self, payload: Any, headers: dict[str, str] | None = None) -> None:
        self.payload = payload
        self.headers = headers or {}

    def __enter__(self) -> "MockResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def response_headers(values: dict[str, str] | None = None) -> Message:
    headers = Message()
    for key, value in (values or {}).items():
        headers[key] = value
    return headers


class DiscogsClientTests(unittest.TestCase):
    def test_paces_requests_across_pages_and_searches(self) -> None:
        clock = FakeClock()
        starts: list[float] = []
        responses = iter((
            {"pagination": {"page": 1, "pages": 2}, "results": []},
            {"pagination": {"page": 2, "pages": 2}, "results": []},
            {"pagination": {"page": 1, "pages": 1}, "results": []},
        ))

        def opener(request: urllib.request.Request, timeout: float) -> MockResponse:
            starts.append(clock.now)
            return MockResponse(next(responses))

        client = DiscogsSearchClient(
            "test-token", opener=opener, sleeper=clock.sleep, monotonic=clock.monotonic
        )
        self.assertIsNone(client.search({"title": "Album"}).error)
        self.assertIsNone(client.search_albums({"title": "Album"}).error)
        self.assertEqual(starts, [0.0, 1.25, 2.5])

    def test_rate_limit_headers_slow_next_request(self) -> None:
        for remaining, expected_delay in (("4", 12.0), ("0", 60.0)):
            with self.subTest(remaining=remaining):
                clock = FakeClock()
                calls = 0

                def opener(request: urllib.request.Request, timeout: float) -> MockResponse:
                    nonlocal calls
                    calls += 1
                    headers = {"X-Discogs-Ratelimit-Remaining": remaining} if calls == 1 else {}
                    return MockResponse(
                        {"pagination": {"page": 1, "pages": 1}, "results": []},
                        headers,
                    )

                client = DiscogsSearchClient(
                    "test-token", opener=opener, sleeper=clock.sleep,
                    monotonic=clock.monotonic,
                )
                client.search({"title": "A"})
                client.search({"title": "B"})
                self.assertEqual(clock.sleeps, [expected_delay])

    def test_429_waits_for_retry_after_or_full_window(self) -> None:
        for headers, expected_delay in (
            ({}, 60.0),
            ({"Retry-After": "75"}, 75.0),
            ({"Retry-After": formatdate(75, usegmt=True)}, 75.0),
            ({"Retry-After": "NaN"}, 60.0),
            ({"Retry-After": "-1"}, 60.0),
        ):
            with self.subTest(headers=headers):
                clock = FakeClock()
                starts: list[float] = []

                def opener(request: urllib.request.Request, timeout: float) -> MockResponse:
                    starts.append(clock.now)
                    if len(starts) == 1:
                        raise urllib.error.HTTPError(
                            request.full_url, 429, "Too Many Requests",
                            response_headers(headers), None,
                        )
                    return MockResponse(
                        {"pagination": {"page": 1, "pages": 1}, "results": []}
                    )

                client = DiscogsSearchClient(
                    "test-token", opener=opener, sleeper=clock.sleep,
                    monotonic=clock.monotonic, wall_clock=lambda: 0.0,
                )
                self.assertIsNone(client.search({"title": "Album"}).error)
                self.assertEqual(starts, [0.0, expected_delay])

    def test_long_retry_after_fails_without_retrying_early(self) -> None:
        clock = FakeClock()
        calls = 0

        def opener(request: urllib.request.Request, timeout: float) -> MockResponse:
            nonlocal calls
            calls += 1
            raise urllib.error.HTTPError(
                request.full_url, 429, "Too Many Requests",
                response_headers({"Retry-After": "301"}), None,
            )

        client = DiscogsSearchClient(
            "test-token", opener=opener, sleeper=clock.sleep, monotonic=clock.monotonic
        )
        self.assertIn("longer than 300 seconds", client.search({"title": "A"}).error or "")
        self.assertIn("longer than 300 seconds", client.search({"title": "B"}).error or "")
        self.assertEqual(calls, 1)
        self.assertEqual(clock.sleeps, [])

    def test_lower_server_limit_increases_request_interval(self) -> None:
        clock = FakeClock()
        calls = 0

        def opener(request: urllib.request.Request, timeout: float) -> MockResponse:
            nonlocal calls
            calls += 1
            return MockResponse(
                {"pagination": {"page": 1, "pages": 1}, "results": []},
                {"X-Discogs-Ratelimit": "25"} if calls == 1 else {},
            )

        client = DiscogsSearchClient(
            "test-token", opener=opener, sleeper=clock.sleep, monotonic=clock.monotonic
        )
        client.search({"title": "A"})
        client.search({"title": "B"})
        self.assertEqual(clock.sleeps, [3.0])

    def test_429_exhaustion_delays_next_search(self) -> None:
        clock = FakeClock()
        starts: list[float] = []

        def opener(request: urllib.request.Request, timeout: float) -> MockResponse:
            starts.append(clock.now)
            if len(starts) == 1:
                raise urllib.error.HTTPError(
                    request.full_url, 429, "Too Many Requests", response_headers(), None
                )
            return MockResponse(
                {"pagination": {"page": 1, "pages": 1}, "results": []}
            )

        client = DiscogsSearchClient(
            "test-token", opener=opener, sleeper=clock.sleep,
            monotonic=clock.monotonic, max_retries=0,
        )
        self.assertIn("429", client.search({"title": "A"}).error or "")
        self.assertIsNone(client.search({"title": "B"}).error)
        self.assertEqual(starts, [0.0, 60.0])

    def test_paginates_deduplicates_and_forces_master(self) -> None:
        responses = iter(
            (
                {
                    "pagination": {"page": 1, "pages": 2},
                    "results": [{"id": 20, "type": "master"}, {"id": 10, "type": "master"}],
                },
                {
                    "pagination": {"page": 2, "pages": 2},
                    "results": [{"id": 20, "type": "master"}, {"id": 30, "type": "master"}],
                },
            )
        )
        requests: list[urllib.request.Request] = []

        def opener(request: urllib.request.Request, timeout: float) -> MockResponse:
            requests.append(request)
            return MockResponse(next(responses))

        client = DiscogsSearchClient("test-token", opener=opener)
        outcome = client.search({"artist": "Omega"})

        self.assertEqual(outcome.error, None)
        self.assertEqual(outcome.master_ids, (10, 20, 30))
        self.assertEqual(len(requests), 2)
        self.assertIn("type=master", requests[0].full_url)
        self.assertIn("page=1", requests[0].full_url)
        self.assertTrue(
            requests[0].get_header("Authorization").startswith("Discogs token=")
        )

    def test_album_fallback_searches_release_resources(self) -> None:
        requests: list[urllib.request.Request] = []

        def opener(request: urllib.request.Request, timeout: float) -> MockResponse:
            requests.append(request)
            return MockResponse(
                {
                    "pagination": {"page": 1, "pages": 1},
                    "results": [
                        {
                            "id": 123,
                            "type": "release",
                            "title": "Omega - Album",
                            "year": "1970",
                        }
                    ],
                }
            )

        outcome = DiscogsSearchClient("test-token", opener=opener).search_albums(
            {"artist": "Omega", "type": "master"}
        )

        self.assertIsNone(outcome.error)
        self.assertEqual(outcome.release_ids, (123,))
        self.assertEqual(outcome.candidates[0].title, "Omega - Album")
        self.assertIn("type=release", requests[0].full_url)

    def test_unexpected_resource_is_error(self) -> None:
        client = DiscogsSearchClient(
            "test-token",
            opener=lambda request, timeout: MockResponse(
                {
                    "pagination": {"page": 1, "pages": 1},
                    "results": [{"id": 1, "type": "release"}],
                }
            ),
        )

        outcome = client.search({"title": "Album"})

        self.assertIn("not a Master", outcome.error or "")

    def test_malformed_master_id_is_error(self) -> None:
        client = DiscogsSearchClient(
            "test-token",
            opener=lambda request, timeout: MockResponse(
                {
                    "pagination": {"page": 1, "pages": 1},
                    "results": [{"id": "bad", "type": "master"}],
                }
            ),
        )

        outcome = client.search({"title": "Album"})

        self.assertIn("malformed Master ID", outcome.error or "")

    def test_inconsistent_pagination_is_error(self) -> None:
        client = DiscogsSearchClient(
            "test-token",
            opener=lambda request, timeout: MockResponse(
                {
                    "pagination": {"page": 2, "pages": 3},
                    "results": [],
                }
            ),
        )

        outcome = client.search({"title": "Album"})

        self.assertIn("pagination", outcome.error or "")

    def test_retries_rate_limit_then_succeeds(self) -> None:
        attempts = 0

        def opener(request: urllib.request.Request, timeout: float) -> MockResponse:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise urllib.error.HTTPError(
                    request.full_url,
                    429,
                    "Too Many Requests",
                    response_headers({"Retry-After": "0"}),
                    None,
                )
            return MockResponse(
                {
                    "pagination": {"page": 1, "pages": 1},
                    "results": [],
                }
            )

        client = DiscogsSearchClient(
            "test-token",
            opener=opener,
            sleeper=lambda delay: None,
        )
        outcome = client.search({"title": "Album"})

        self.assertIsNone(outcome.error)
        self.assertEqual(attempts, 2)

    def test_snapshot_only_uses_saved_response_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            query_url = (
                "https://api.discogs.com/database/search?"
                "artist=Omega&type=master&page=1&per_page=100"
            )
            snapshot = Path(directory) / "unused"
            client = DiscogsSearchClient(
                "test-token",
                snapshot_dir=snapshot,
                snapshot_only=True,
            )
            url_hash = __import__("hashlib").sha256(
                query_url.encode("utf-8")
            ).hexdigest()
            snapshot.mkdir()
            (snapshot / f"{url_hash}.json").write_text(
                json.dumps(
                    {
                        "pagination": {"page": 1, "pages": 1},
                        "results": [{"id": 42, "type": "master"}],
                    }
                ),
                encoding="utf-8",
            )

            def unexpected_opener(
                request: urllib.request.Request,
                timeout: float,
            ) -> MockResponse:
                raise AssertionError("Network opener must not be called")

            client.opener = unexpected_opener
            outcome = client.search({"artist": "Omega"})

            self.assertEqual(outcome.master_ids, (42,))


if __name__ == "__main__":
    unittest.main()
