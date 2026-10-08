"""Direct API integration checks; no socket or network service is started."""

import csv
from datetime import timedelta
import io
import json
from pathlib import Path
import tempfile
import unittest

from lotto.analysis import backtest, generate_sets
from lotto.data import FIRST_DRAW_DATE, save_draws
from lotto.server import Application


def fixture():
    sets = [[1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6],
            [7, 8, 9, 10, 11, 12], [7, 8, 9, 10, 11, 12],
            [20, 21, 22, 23, 24, 25], [30, 31, 32, 33, 34, 35]]
    return [{"round": index + 1,
             "date": (FIRST_DRAW_DATE + timedelta(weeks=index)).isoformat(),
             "numbers": numbers, "bonus": 45, "source": "Synthetic API fixture"}
            for index, numbers in enumerate(sets)]


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        directory = Path(self.temporary.name)
        self.draws = fixture()
        self.manifest_path = directory / "sources.json"
        data_path = directory / "draws.json"
        save_draws(self.draws, data_path)
        self.app = Application(data_path, self.manifest_path)
        self.addCleanup(self.app.analysis.cache_clear)
        self.addCleanup(self.app.evaluation.cache_clear)

    def test_draw_and_csv_filters_are_inclusive_and_keep_bonus_separate(self):
        query = {"start": ["2"], "end": ["4"]}
        self.assertEqual(self.app.api("/api/draws", query), self.draws[1:4])
        rows = list(csv.DictReader(io.StringIO(self.app.api("/api/export.csv", query))))
        self.assertEqual([int(row["round"]) for row in rows], [2, 3, 4])
        self.assertTrue(all(int(row["bonus"]) == 45 for row in rows))

    def test_analysis_limits_both_history_and_recent_window(self):
        result = self.app.api("/api/analysis", {"start": ["2"], "end": ["4"], "window": ["1"]})
        self.assertEqual(result["summary"]["draw_count"], 3)
        self.assertEqual(result["summary"]["first_round"], 2)
        self.assertEqual(result["summary"]["last_round"], 4)
        rows = {row["number"]: row for row in result["numbers"]}
        self.assertEqual(rows[1]["count"], 1)
        self.assertEqual(rows[1]["recent_count"], 0)
        self.assertEqual(rows[7]["count"], 2)
        self.assertEqual(rows[7]["recent_count"], 1)
        self.assertEqual(rows[45]["count"], 0)
        self.assertEqual(rows[45]["bonus_count"], 3)
        self.assertNotIn("counts", result["pairs"])
        self.assertNotIn("counts", result["triples"])
        self.assertEqual(len(result["pairs"]["top"]), 20)
        json.dumps(result, allow_nan=False)

    def test_generation_uses_only_selected_history_and_is_reproducible(self):
        query = {"start": ["3"], "end": ["5"], "window": ["1"],
                 "strategy": ["hot"], "count": ["7"], "seed": ["15"]}
        result = self.app.api("/api/generate", query)
        expected = generate_sets(self.draws[2:5], count=7, strategy="hot", seed=15, window=1)
        self.assertEqual(result["sets"], expected)
        self.assertEqual(result["through_round"], 5)
        self.assertEqual(result, self.app.api("/api/generate", query))

    def test_backtest_filter_preserves_earlier_training_and_excludes_future_draws(self):
        query = {"start": ["4"], "end": ["5"], "window": ["2"]}
        result = self.app.api("/api/backtest", query)
        expected = backtest(self.draws[:5], window=2, start_round=4)
        self.assertEqual(result["rounds"], expected["rounds"])
        self.assertEqual(result["draw_count"], 2)
        self.assertEqual(result["start_round"], 4)
        self.assertEqual(result["end_round"], 5)

    def test_invalid_range_controls_and_unknown_route_are_rejected(self):
        bad_queries = [
            {"start": ["0"]}, {"end": ["7"]},
            {"start": ["4"], "end": ["2"]}, {"window": ["0"]},
            {"window": ["1.5"]}, {"start": [""]},
        ]
        for query in bad_queries:
            with self.subTest(query=query), self.assertRaises(ValueError):
                self.app.api("/api/analysis", query)
        for query in ({"count": ["101"]}, {"strategy": ["magic"]}, {"seed": ["-1"]}):
            with self.subTest(query=query), self.assertRaises(ValueError):
                self.app.api("/api/generate", query)
        with self.assertRaises(KeyError):
            self.app.api("/api/not-found", {})

    def test_manifest_is_loaded_from_supplied_path_with_missing_fallback(self):
        missing = self.app.api("/api/sources", {})
        self.assertEqual(missing["sources"], [])
        self.assertIn("missing", missing["coverage_note"].lower())
        manifest = {"sources": [{"name": "Synthetic source", "rounds": [1, 6]}]}
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8-sig")
        self.assertEqual(self.app.api("/api/sources", {}), manifest)


if __name__ == "__main__":
    unittest.main()
