"""Tests for interactive web server functionality."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from beatbee.search import (
    FakeSearchAdapter,
    ResourceSearchOutcome,
    SearchOutcome,
    AlbumSearchOutcome,
)
from beatbee.web_server import InteractiveSessionManager
from beatbee.web_app import create_app
from beatbee.models import MasterCandidate, AlbumCandidate, ResourceCandidate


class InteractiveSessionManagerTests(unittest.TestCase):
    """Test the interactive session manager."""

    def test_load_input_validates_document(self):
        """Load input validates JSON structure."""
        manager = InteractiveSessionManager()
        document = {
            "list_name": "Test List",
            "records": [
                {"artist": "Test", "release_title": "Album"}
            ]
        }
        result = manager.load_input(document)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["list_name"], "Test List")

    def test_load_input_rejects_invalid_document(self):
        """Load input rejects invalid JSON."""
        manager = InteractiveSessionManager()
        document = {"records": []}  # Missing list_name
        result = manager.load_input(document)
        self.assertEqual(result["status"], "error")
        self.assertIn("list_name", result["message"])

    def test_run_validation_requires_session(self):
        """Validation requires loaded session."""
        manager = InteractiveSessionManager()
        result = manager.run_validation()
        self.assertIsNone(result)

    def test_run_validation_executes_search(self):
        """Validation executes search and returns summary."""
        adapter = FakeSearchAdapter(
            outcomes=(
                SearchOutcome(master_ids=(1,)),
            ),
        )
        manager = InteractiveSessionManager(adapter=adapter)
        document = {
            "list_name": "Test",
            "records": [{"artist": "Test"}]
        }
        manager.load_input(document)
        result = manager.run_validation()
        self.assertIsNotNone(result)
        self.assertEqual(result["list_name"], "Test")
        self.assertEqual(result["total"], 1)
        self.assertTrue(result["all_ok"])

    def test_update_record_params(self):
        """Update record parameters."""
        manager = InteractiveSessionManager()
        document = {
            "list_name": "Test",
            "records": [
                {"artist": "Old", "release_title": "Album"}
            ]
        }
        manager.load_input(document)
        result = manager.update_record_params(0, {"artist": "New"})
        self.assertEqual(result["status"], "ok")
        
        updated = manager.get_current_input()
        self.assertEqual(updated["records"][0]["artist"], "New")

    def test_research_supports_multiple_types_and_returns_type_results(self):
        manager = InteractiveSessionManager(
            adapter=FakeSearchAdapter(
                outcomes=(SearchOutcome(),),
                resource_outcomes={
                    "artist": ResourceSearchOutcome(resource_ids=(5,)),
                    "label": ResourceSearchOutcome(resource_ids=(8,)),
                },
            )
        )
        manager.load_input(
            {"list_name": "Test", "records": [{"title": "Original"}]}
        )
        manager.run_validation()

        result = manager.research_record(
            0,
            {"title": "Edited", "type": ["artist", "label"]},
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            [
                item["resource_type"]
                for item in result["summary"]["results"][0]["type_results"]
            ],
            ["artist", "label"],
        )

    def test_interactive_searches_are_independent_complete_and_paginated(self):
        class TrackingAdapter(FakeSearchAdapter):
            def __init__(self):
                candidates = tuple(
                    ResourceCandidate(resource_id=item, title=f"Artist {item}")
                    for item in range(1, 54)
                )
                super().__init__(
                    outcomes=(SearchOutcome(), SearchOutcome()),
                    resource_outcomes={
                        "artist": ResourceSearchOutcome(
                            resource_ids=tuple(range(1, 54)),
                            candidates=candidates,
                        ),
                        "label": ResourceSearchOutcome(
                            resource_ids=(900,),
                            candidates=(
                                ResourceCandidate(resource_id=900, title="Label"),
                            ),
                        ),
                    },
                )
                self.interactive_calls = []

            def search_resource_type(self, params, resource_type):
                self.interactive_calls.append((dict(params), resource_type))
                return super().search_resource_type(params, resource_type)

        adapter = TrackingAdapter()
        manager = InteractiveSessionManager(adapter=adapter)
        manager.load_input({
            "list_name": "Test",
            "records": [{"title": "Original"}, {"title": "Other"}],
        })
        manager.run_validation()

        result = manager.search_record(
            0,
            {"title": "Edited"},
            ["label", "artist"],
        )

        self.assertEqual(
            [resource_type for _, resource_type in adapter.interactive_calls],
            ["artist", "label"],
        )
        self.assertEqual(result["record"]["total_results"], 54)
        self.assertEqual(len(result["record"]["results"]), 50)
        last_page = manager.get_record_results(0, page=2)
        self.assertEqual(len(last_page["results"]), 4)
        state = manager.get_web_state()
        self.assertEqual(state["nIO"][0]["draft"], {"title": "Edited"})
        self.assertEqual(state["nIO"][1]["draft"], {"title": "Other"})
        self.assertEqual(state["nIO"][0]["technical_status"], "NOT_FOUND")

    def test_manual_confirmation_supports_every_resource_type_and_exports_one(self):
        for resource_type, resource_id in (
            ("master", 101),
            ("release", 102),
            ("artist", 103),
            ("label", 104),
        ):
            with self.subTest(resource_type=resource_type):
                adapter = FakeSearchAdapter(
                    outcomes=(SearchOutcome(),),
                    resource_outcomes={
                        resource_type: ResourceSearchOutcome(
                            resource_ids=(resource_id,),
                            candidates=(
                                ResourceCandidate(
                                    resource_id=resource_id,
                                    title=f"Candidate {resource_id}",
                                ),
                            ),
                        ),
                    },
                )
                manager = InteractiveSessionManager(adapter=adapter)
                original = {
                    "list_name": "Test",
                    "records": [{"title": "Original"}],
                }
                manager.load_input(original)
                manager.run_validation()
                manager.search_record(
                    0,
                    {"title": "Edited"},
                    [resource_type],
                )
                manager.select_candidate(0, resource_type, resource_id)
                manager.confirm_selection(0)

                state = manager.get_web_state()
                self.assertEqual(state["nIO"], [])
                self.assertEqual(state["iO"][0]["source"], "manual")
                self.assertEqual(state["iO"][0]["resource_type"], resource_type)
                exported = manager.get_export_input()
                self.assertEqual(
                    exported["records"][0]["type"],
                    resource_type,
                )
                self.assertEqual(
                    exported["records"][0]["selected_result"]["id"],
                    resource_id,
                )
                self.assertIsInstance(exported["records"][0]["type"], str)
                self.assertEqual(original["records"][0], {"title": "Original"})

    def test_search_clears_unconfirmed_selection_but_keeps_confirmed_result(self):
        manager = InteractiveSessionManager(
            adapter=FakeSearchAdapter(
                outcomes=(SearchOutcome(),),
                resource_outcomes={
                    "artist": ResourceSearchOutcome(
                        resource_ids=(1, 2),
                        candidates=(
                            ResourceCandidate(resource_id=1, title="One"),
                            ResourceCandidate(resource_id=2, title="Two"),
                        ),
                    ),
                },
            )
        )
        manager.load_input({"list_name": "Test", "records": [{"title": "X"}]})
        manager.run_validation()
        manager.search_record(0, {"title": "First"}, ["artist"])
        manager.select_candidate(0, "artist", 1)
        manager.search_record(0, {"title": "Second"}, ["artist"])
        self.assertIsNone(manager.get_record_results(0)["selected_candidate"])
        manager.select_candidate(0, "artist", 2)
        manager.confirm_selection(0)
        manager.search_record(0, {"title": "Third"}, ["artist"])
        exported = manager.get_export_input()
        self.assertEqual(exported["records"][0]["title"], "Second")
        self.assertEqual(exported["records"][0]["selected_result"]["id"], 2)

    def test_sorting_is_stable_and_does_not_change_export_order(self):
        manager = InteractiveSessionManager(
            adapter=FakeSearchAdapter(
                outcomes=(
                    SearchOutcome(
                        master_ids=(1,),
                        candidates=(MasterCandidate(1, title="First", artist="A"),),
                    ),
                    SearchOutcome(
                        master_ids=(2,),
                        candidates=(MasterCandidate(2, title="Second", artist="B"),),
                    ),
                    SearchOutcome(
                        master_ids=(3,),
                        candidates=(MasterCandidate(3, title="Third", artist="A"),),
                    ),
                )
            )
        )
        manager.load_input({
            "list_name": "Test",
            "records": [{"title": "1"}, {"title": "2"}, {"title": "3"}],
        })
        manager.run_validation()

        ascending = manager.get_web_state(sort_by="artist", direction="asc")
        descending = manager.get_web_state(sort_by="artist", direction="desc")
        self.assertEqual([row["position"] for row in ascending["iO"]], [1, 3, 2])
        self.assertEqual([row["position"] for row in descending["iO"]], [2, 1, 3])
        exported = manager.get_export_input()
        self.assertEqual(
            [record["title"] for record in exported["records"]],
            ["1", "2", "3"],
        )

    def test_web_metadata_is_not_passed_to_core_search(self):
        class ParameterTrackingAdapter(FakeSearchAdapter):
            def __init__(self):
                super().__init__(outcomes=(SearchOutcome(),))
                self.params_seen = []

            def search(self, params):
                self.params_seen.append(dict(params))
                return super().search(params)

            def search_albums(self, params):
                self.params_seen.append(dict(params))
                return super().search_albums(params)

        adapter = ParameterTrackingAdapter()
        manager = InteractiveSessionManager(adapter=adapter)
        manager.load_input({
            "list_name": "Web export",
            "records": [{
                "title": "Candidate",
                "type": "release",
                "selected_result": {
                    "type": "release",
                    "id": 25,
                    "url": "https://www.discogs.com/release/25",
                },
            }],
        })
        manager.run_validation()
        self.assertNotIn("selected_result", adapter.params_seen[0])

    def test_export_adds_master_id_only_to_ok_records_without_mutating_input(self):
        manager = InteractiveSessionManager(
            adapter=FakeSearchAdapter(
                outcomes=(
                    SearchOutcome(master_ids=(42,)),
                    SearchOutcome(),
                )
            )
        )
        document = {
            "list_name": "Test",
            "records": [{"title": "OK"}, {"title": "Unresolved"}],
        }
        manager.load_input(document)
        manager.run_validation()

        exported = manager.get_export_input()
        if exported is None:
            self.fail("Expected an export after validation")

        self.assertEqual(exported["records"][0]["master_id"], 42)
        self.assertNotIn("master_id", exported["records"][1])
        self.assertEqual(manager.get_current_input(), document)

    def test_export_keeps_original_query_for_unresolved_record(self):
        manager = InteractiveSessionManager(
            adapter=FakeSearchAdapter(outcomes=(SearchOutcome(), SearchOutcome()))
        )
        document = {
            "list_name": "Test",
            "records": [{"title": "Original title"}],
        }
        manager.load_input(document)
        manager.run_validation()
        manager.research_record(0, {"title": "Edited title", "type": ["release"]})

        exported = manager.get_export_input()
        if exported is None:
            self.fail("Expected an export after re-search")

        self.assertEqual(
            exported["records"][0],
            {"title": "Original title"},
        )

    def test_exported_release_result_contains_associated_master_id(self):
        manager = InteractiveSessionManager(
            adapter=FakeSearchAdapter(
                album_outcomes=(
                    AlbumSearchOutcome(
                        release_ids=(23,),
                        candidates=(
                            AlbumCandidate(release_id=23, master_id=7),
                        ),
                    ),
                )
            )
        )
        manager.load_input(
            {
                "list_name": "Test",
                "records": [{"title": "Album", "type": ["release"]}],
            }
        )
        manager.run_validation()

        exported = manager.get_export_input()
        if exported is None:
            self.fail("Expected an export after successful validation")
        self.assertEqual(exported["records"][0]["master_id"], 7)

    def test_get_current_input(self):
        """Get current input state."""
        manager = InteractiveSessionManager()
        document = {
            "list_name": "Test",
            "records": [{"artist": "Test"}]
        }
        manager.load_input(document)
        current = manager.get_current_input()
        self.assertEqual(current, document)

    def test_get_resolved_results(self):
        """Get resolved results from summary."""
        adapter = FakeSearchAdapter(
            outcomes=(
                SearchOutcome(
                    master_ids=(123,),
                    candidates=(
                        MasterCandidate(
                            master_id=123,
                            title="Test Album",
                            artist="Test Artist",
                            year="2000"
                        ),
                    )
                ),
            ),
        )
        manager = InteractiveSessionManager(adapter=adapter)
        document = {
            "list_name": "Test",
            "records": [{"artist": "Test"}]
        }
        manager.load_input(document)
        manager.run_validation()
        
        resolved = manager.get_resolved_results()
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["master_id"], 123)
        self.assertEqual(resolved[0]["title"], "Test Album")

    def test_save_to_file(self):
        """Save current input to file."""
        manager = InteractiveSessionManager()
        document = {
            "list_name": "Test",
            "records": [{"artist": "Test"}]
        }
        manager.load_input(document)
        
        with TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "test.json"
            result = manager.save_to_file(json_path)
            self.assertEqual(result["status"], "ok")
            self.assertTrue(json_path.exists())
            
            saved = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["list_name"], "Test")

    def test_reset_to_original(self):
        """Reset input to original."""
        manager = InteractiveSessionManager()
        document = {
            "list_name": "Test",
            "records": [{"artist": "Original"}]
        }
        manager.load_input(document)
        manager.update_record_params(0, {"artist": "Modified"})
        
        result = manager.reset_to_original()
        self.assertEqual(result["status"], "ok")
        
        current = manager.get_current_input()
        self.assertEqual(current["records"][0]["artist"], "Original")

    def test_multiple_entries_with_mixed_results(self):
        """Handle multiple entries with mixed results."""
        adapter = FakeSearchAdapter(
            outcomes=(
                SearchOutcome(master_ids=(1,)),  # OK
                SearchOutcome(master_ids=()),    # NOT_FOUND
                SearchOutcome(master_ids=(3, 4)),  # MULTIPLE
            ),
        )
        manager = InteractiveSessionManager(adapter=adapter)
        document = {
            "list_name": "Test",
            "records": [
                {"artist": "A"},
                {"artist": "B"},
                {"artist": "C"},
            ]
        }
        manager.load_input(document)
        result = manager.run_validation()
        
        self.assertEqual(result["total"], 3)
        self.assertFalse(result["all_ok"])
        self.assertEqual(result["counts"].get("OK"), 1)
        self.assertEqual(result["counts"].get("NOT_FOUND"), 1)
        self.assertEqual(result["counts"].get("MULTIPLE"), 1)


class FlaskWebAppTests(unittest.TestCase):
    """Test Flask web application."""

    def setUp(self):
        """Set up test client."""
        adapter = FakeSearchAdapter(
            outcomes=(
                SearchOutcome(master_ids=(1,)),
            ),
        )
        self.app = create_app(adapter=adapter)
        self.client = self.app.test_client()

    def test_index_returns_html(self):
        """Index route returns HTML."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'BeatBee', response.data)
        self.assertIn(b'grid-template-columns: repeat(2, minmax(0, 1fr))', response.data)
        self.assertIn(b'class="type-option"', response.data)
        self.assertIn(b'"artist": "NKS", "release_title": "*****", "year": "2006"', response.data)
        self.assertIn(b'"q": "Kov\xc3\xa1cs Kati \xc3\xa9s az Locomotiv GT", "year": "1974"', response.data)
        self.assertIn(b'Manual iO', response.data)
        self.assertNotIn(b'Confirmation source', response.data)

    def test_api_load_accepts_json(self):
        """API load endpoint accepts JSON."""
        document = {
            "list_name": "Test",
            "records": [{"artist": "Test"}]
        }
        response = self.client.post(
            '/api/load',
            json=document,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "ok")

    def test_api_load_rejects_invalid_json(self):
        """API load rejects invalid input."""
        document = {"records": []}  # Missing list_name
        response = self.client.post(
            '/api/load',
            json=document,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "error")

    def test_api_validate_requires_load_first(self):
        """API validate requires loaded session."""
        response = self.client.post('/api/validate')
        self.assertEqual(response.status_code, 400)

    def test_api_validate_returns_summary(self):
        """API validate returns search summary."""
        document = {
            "list_name": "Test",
            "records": [{"artist": "Test"}]
        }
        self.client.post('/api/load', json=document)
        response = self.client.post('/api/validate')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["list_name"], "Test")
        self.assertTrue(data["all_ok"])

    def test_api_reset(self):
        """API reset endpoint."""
        document = {
            "list_name": "Test",
            "records": [{"artist": "Original"}]
        }
        self.client.post('/api/load', json=document)
        response = self.client.post('/api/reset')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "ok")

    def test_api_download_json(self):
        """API download JSON endpoint."""
        document = {
            "list_name": "Test",
            "records": [{"artist": "Test"}]
        }
        self.client.post('/api/load', json=document)
        self.client.post('/api/validate')
        response = self.client.get('/api/download/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'list_name', response.data)
        self.assertIn(b'"master_id": 1', response.data)

    def test_api_download_zip(self):
        """API download ZIP endpoint."""
        document = {
            "list_name": "Test",
            "records": [{"artist": "Test"}]
        }
        self.client.post('/api/load', json=document)
        self.client.post('/api/validate')
        response = self.client.get('/api/download/zip')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'PK', response.data)  # ZIP magic bytes

    def test_api_sessions_are_isolated_between_browser_clients(self):
        second_client = self.app.test_client()
        self.assertEqual(second_client.get('/api/state').status_code, 400)

        self.client.post(
            '/api/load',
            json={"list_name": "First", "records": [{"title": "A"}]},
        )
        self.client.post('/api/validate')
        second_client.post(
            '/api/load',
            json={"list_name": "Second", "records": [{"title": "B"}]},
        )
        second_client.post('/api/validate')

        first_state = self.client.get('/api/state').get_json()
        second_state = second_client.get('/api/state').get_json()
        self.assertEqual(first_state["list_name"], "First")
        self.assertEqual(second_state["list_name"], "Second")

    def test_interactive_search_error_does_not_expose_token(self):
        secret = "private-discogs-token"

        class ErrorAdapter(FakeSearchAdapter):
            def __init__(self):
                super().__init__(outcomes=(SearchOutcome(),))
                self.token = secret

            def search_resource_type(self, params, resource_type):
                raise RuntimeError(f"request failed with {secret}")

        client = create_app(adapter=ErrorAdapter()).test_client()
        client.post(
            '/api/load',
            json={"list_name": "Test", "records": [{"title": "A"}]},
        )
        client.post('/api/validate')
        response = client.post(
            '/api/record/search',
            json={
                "record_index": 0,
                "params": {"title": "A"},
                "search_types": ["artist"],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(secret.encode(), response.data)
        self.assertIn(b"[redacted]", response.data)

    def test_api_state_and_confirmation_routes(self):
        adapter = FakeSearchAdapter(
            outcomes=(SearchOutcome(),),
            resource_outcomes={
                "release": ResourceSearchOutcome(
                    resource_ids=(77,),
                    candidates=(ResourceCandidate(resource_id=77, title="Release"),),
                ),
            },
        )
        client = create_app(adapter=adapter).test_client()
        client.post(
            '/api/load',
            json={"list_name": "Test", "records": [{"title": "A"}]},
        )
        client.post('/api/validate')
        search = client.post(
            '/api/record/search',
            json={
                "record_index": 0,
                "params": {"title": "Changed"},
                "search_types": ["release"],
            },
        )
        self.assertEqual(search.status_code, 200)
        selected = client.post(
            '/api/record/select',
            json={
                "record_index": 0,
                "resource_type": "release",
                "resource_id": 77,
            },
        )
        self.assertEqual(selected.status_code, 200)
        confirmed = client.post(
            '/api/record/confirm',
            json={"record_index": 0},
        )
        self.assertEqual(confirmed.status_code, 200)
        state = client.get('/api/state').get_json()
        self.assertEqual(state["nIO"], [])
        self.assertEqual(state["iO"][0]["resource_type"], "release")
        self.assertEqual(state["core_counts"]["NOT_FOUND"], 1)
        self.assertEqual(state["manual_count"], 1)
        self.assertEqual(state["automatic_count"], 0)
        exported = json.loads(client.get('/api/download/json').data)
        self.assertEqual(exported["records"][0]["type"], "release")


if __name__ == '__main__':
    unittest.main()
