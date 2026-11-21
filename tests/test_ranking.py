import unittest

from beatbee.models import MasterCandidate
from beatbee.ranking import rank_candidates


class RankingTests(unittest.TestCase):
    def test_rank_is_deterministic_across_input_order(self) -> None:
        candidates = (
            MasterCandidate(
                master_id=300,
                title="Omega - 10000 Lépés",
                artist="Omega",
                release_title="10000 Lépés",
                year="1969",
            ),
            MasterCandidate(
                master_id=100,
                title="Omega - Gyöngyhajú Lány",
                artist="Omega",
                release_title="Gyöngyhajú Lány",
                year="1969",
            ),
            MasterCandidate(
                master_id=200,
                title="Omega - 10000 lépés",
                artist="Omega",
                release_title="10000 lépés",
                year="1969",
            ),
        )
        query = {
            "artist": "Omega",
            "release_title": "10000 lépés",
            "year": "1969",
        }

        forward = rank_candidates(candidates, query)
        shuffled = rank_candidates(tuple(reversed(candidates)), query)

        self.assertEqual(forward, shuffled)
        self.assertEqual([candidate.master_id for candidate in forward[:3]], [200, 300, 100])

    def test_missing_candidate_metadata_does_not_infer_a_match(self) -> None:
        candidates = (
            MasterCandidate(master_id=9),
            MasterCandidate(
                master_id=2,
                title="Unknown",
                artist="Other",
                release_title="Album",
            ),
        )
        ranked = rank_candidates(candidates, {"artist": "Omega", "release_title": "Album"})

        self.assertEqual(ranked[0].master_id, 2)


if __name__ == "__main__":
    unittest.main()
