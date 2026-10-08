"""Checks of lottery arithmetic, historical summaries, and causal evaluation."""

from copy import deepcopy
from datetime import date, timedelta
import json
from math import comb
import unittest

from lotto.analysis import analyze, backtest, generate_sets


def history_from_sets(sets):
    start = date(2002, 12, 7)
    return [{"round": index + 1,
             "date": (start + timedelta(days=index * 7)).isoformat(),
             "numbers": numbers,
             "bonus": next(n for n in range(1, 46) if n not in numbers),
             "source": "synthetic test fixture"}
            for index, numbers in enumerate(sets)]


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.history = history_from_sets([
            [1, 2, 3, 23, 24, 45],
            [1, 2, 4, 25, 35, 44],
            [2, 3, 4, 26, 36, 43],
        ])
        self.result = analyze(self.history, window=2)

    def test_counts_and_rates_use_draws_and_keep_bonus_separate(self):
        rows = {row["number"]: row for row in self.result["numbers"]}
        self.assertEqual(len(rows), 45)
        self.assertEqual(sum(row["count"] for row in rows.values()), 18)
        self.assertEqual(sum(row["recent_count"] for row in rows.values()), 12)
        self.assertEqual(sum(row["bonus_count"] for row in rows.values()), 3)
        self.assertEqual(rows[2]["count"], 3)
        self.assertEqual(rows[2]["rate"], 1)
        self.assertEqual(rows[1]["recent_count"], 1)
        self.assertEqual(rows[1]["recent_rate"], 0.5)
        self.assertEqual(rows[1]["last_seen"], 2)
        self.assertEqual(rows[1]["draws_since"], 1)
        self.assertIsNone(rows[42]["last_seen"])
        self.assertEqual(rows[42]["draws_since"], 3)
        self.assertEqual(rows[4]["count"], 2)
        self.assertEqual(rows[4]["bonus_count"], 1)

    def test_pairs_and_triples_cover_whole_sample_space(self):
        for key, size in (("pairs", 2), ("triples", 3)):
            result = self.result[key]
            self.assertEqual(len(result["counts"]), comb(45, size))
            self.assertEqual(sum(row["count"] for row in result["counts"]),
                             3 * comb(6, size))
            self.assertAlmostEqual(result["expected_count"],
                                   3 * comb(6, size) / comb(45, size))
            self.assertEqual(len(result["top"]), 20)
        pairs = {tuple(row["numbers"]): row["count"]
                 for row in self.result["pairs"]["counts"]}
        self.assertEqual(pairs[1, 2], 2)
        self.assertEqual(pairs[42, 45], 0)

    def test_per_draw_features(self):
        first, second, third = self.result["per_draw"]
        self.assertEqual(first["sum"], 98)
        self.assertEqual((first["odd"], first["even"]), (4, 2))
        self.assertEqual((first["low"], first["high"]), (3, 3))
        self.assertEqual(first["consecutive_pairs"], 3)
        self.assertEqual(first["span"], 44)
        self.assertIsNone(first["repeated_from_previous"])
        self.assertEqual(second["repeated_from_previous"], 2)
        self.assertEqual(third["repeated_from_previous"], 2)
        self.assertEqual(first["tens_bins"],
                         {"1-10": 3, "11-20": 0, "21-30": 2, "31-40": 0, "41-45": 1})
        self.assertEqual(self.result["distributions"]["repeated_from_previous"],
                         [{"value": 2, "count": 2, "rate": 1}])
        for name, rows in self.result["distributions"].items():
            expected = 2 if name == "repeated_from_previous" else 3
            self.assertEqual(sum(row["count"] for row in rows), expected)
            self.assertAlmostEqual(sum(row["rate"] for row in rows), 1)

    def test_theoretical_odds(self):
        odds = self.result["odds"]
        self.assertEqual(odds["total_combinations"], 8_145_060)
        self.assertEqual([row["winning_combinations"] for row in odds["prize_tiers"]],
                         [1, 6, 228, 11_115, 182_780])
        self.assertAlmostEqual(sum(row["probability"] for row in odds["match_probabilities"]), 1)
        self.assertAlmostEqual(sum(row["matches"] * row["probability"]
                                   for row in odds["match_probabilities"]), 0.8)
        self.assertAlmostEqual(odds["at_least_3_probability"],
                               sum(row["probability"] for row in odds["match_probabilities"]
                                   if row["matches"] >= 3))

    def test_window_larger_than_history_and_json_compatibility(self):
        result = analyze(self.history, window=100)
        self.assertEqual(result["summary"]["recent_draw_count"], 3)
        for row in result["numbers"]:
            self.assertEqual(row["count"], row["recent_count"])
            self.assertEqual(row["rate"], row["recent_rate"])
        json.dumps(result, allow_nan=False)

    def test_input_not_mutated(self):
        original = deepcopy(self.history)
        analyze(self.history)
        generate_sets(self.history)
        backtest(self.history, window=1)
        self.assertEqual(self.history, original)


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.history = history_from_sets([[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]])

    def test_unique_sorted_sets_and_seed_reproducibility(self):
        for strategy in ("uniform", "hot", "frequent", "balanced"):
            with self.subTest(strategy=strategy):
                sets = generate_sets(self.history, count=30, strategy=strategy, seed=123)
                self.assertEqual(sets, generate_sets(self.history, 30, strategy, 123))
                self.assertEqual(len({tuple(ticket) for ticket in sets}), 30)
                for ticket in sets:
                    self.assertEqual(len(set(ticket)), 6)
                    self.assertEqual(ticket, sorted(ticket))
                    self.assertTrue(all(1 <= number <= 45 for number in ticket))
                    if strategy == "balanced":
                        self.assertEqual(sum(number % 2 for number in ticket), 3)
                        self.assertEqual(sum(number <= 22 for number in ticket), 3)

    def test_different_seed_changes_sample(self):
        self.assertNotEqual(generate_sets(self.history, seed=1),
                            generate_sets(self.history, seed=2))

    def test_invalid_controls(self):
        for bad in (0, -1, 1.5, "5", True, None, 1001):
            with self.subTest(count=bad), self.assertRaises(ValueError):
                generate_sets(self.history, count=bad)
        for bad in (0, -1, 1.5, "50", True, None):
            with self.subTest(window=bad), self.assertRaises(ValueError):
                analyze(self.history, window=bad)
            with self.assertRaises(ValueError):
                backtest(self.history, window=bad)
        with self.assertRaises(ValueError):
            generate_sets(self.history, strategy="prediction")
        with self.assertRaises(ValueError):
            generate_sets(self.history, seed="random")

    def test_invalid_history(self):
        bad_histories = [[], list(reversed(self.history))]
        repeated = deepcopy(self.history)
        repeated[0]["numbers"] = [1, 1, 2, 3, 4, 5]
        bad_histories.append(repeated)
        invalid_bonus = deepcopy(self.history)
        invalid_bonus[0]["bonus"] = 1
        bad_histories.append(invalid_bonus)
        for history in bad_histories:
            with self.subTest(history=history), self.assertRaises(ValueError):
                analyze(history)


class BacktestTests(unittest.TestCase):
    def setUp(self):
        self.history = history_from_sets([
            [1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6],
            [7, 8, 9, 10, 11, 12], [7, 8, 9, 10, 11, 12],
            [7, 8, 9, 10, 11, 12], [20, 21, 22, 23, 24, 25],
        ])

    def test_predicts_before_seeing_current_or_future_draws(self):
        result = backtest(self.history, window=2, seed=45)
        first = result["rounds"][0]
        self.assertEqual(first["round"], 3)
        self.assertEqual(first["predictions"]["hot"], [1, 2, 3, 4, 5, 6])
        self.assertEqual(first["predictions"]["frequent"], [1, 2, 3, 4, 5, 6])
        self.assertEqual(first["matches"]["hot"], 0)
        changed = deepcopy(self.history)
        for draw in changed[2:]:
            draw["numbers"] = [30, 31, 32, 33, 34, 35]
            draw["bonus"] = 36
        changed_result = backtest(changed, window=2, seed=45)
        self.assertEqual(first["predictions"], changed_result["rounds"][0]["predictions"])
        self.assertEqual(backtest(self.history[:4], window=2, seed=45)["rounds"],
                         result["rounds"][:2])

    def test_hot_uses_rolling_window_frequent_uses_all_prior_draws(self):
        rows = backtest(self.history, window=2)["rounds"]
        fifth = rows[2]
        self.assertEqual(fifth["round"], 5)
        self.assertEqual(fifth["predictions"]["hot"], [7, 8, 9, 10, 11, 12])
        self.assertEqual(fifth["predictions"]["frequent"], [1, 2, 3, 4, 5, 6])

    def test_summary_matches_per_round_results(self):
        result = backtest(self.history, window=2)
        self.assertEqual(result["draw_count"], 4)
        self.assertEqual(result["expected_matches"], 0.8)
        for name, summary in result["strategies"].items():
            matches = [row["matches"][name] for row in result["rounds"]]
            self.assertEqual(sum(summary["match_histogram"].values()), 4)
            self.assertEqual(summary["avg_matches"], sum(matches) / 4)
            self.assertEqual(summary["hits_at_least_3"], sum(value >= 3 for value in matches))
        self.assertEqual(result, backtest(self.history, window=2))
        json.dumps(result, allow_nan=False)

    def test_cutoff_does_not_change_predictions_or_uniform_baseline(self):
        all_results = backtest(self.history, window=2, seed=99)
        cut_results = backtest(self.history, window=2, start_round=5, seed=99)
        self.assertEqual(cut_results["rounds"], all_results["rounds"][2:])

    def test_insufficient_history_reports_no_score(self):
        result = backtest(self.history, window=50)
        self.assertEqual(result["draw_count"], 0)
        self.assertEqual(result["rounds"], [])
        self.assertIsNone(result["start_round"])
        self.assertTrue(result["methodology"]["insufficient_history"])
        for summary in result["strategies"].values():
            self.assertIsNone(summary["avg_matches"])
            self.assertIsNone(summary["hit_rate_at_least_3"])


if __name__ == "__main__":
    unittest.main()
