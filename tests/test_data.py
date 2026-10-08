"""Dataset integrity checks using deliberately small, synthetic histories."""

from copy import deepcopy
import csv
from datetime import timedelta
import io
import json
from pathlib import Path
import tempfile
import unittest

from lotto.data import FIRST_DRAW_DATE, draws_csv, load_draws, save_draws, validate_draws


def fixture():
    return [
        {"round": index + 1,
         "date": (FIRST_DRAW_DATE + timedelta(weeks=index)).isoformat(),
         "numbers": list(range(index + 1, index + 7)), "bonus": 45,
         "source": "Synthetic fixture, not an actual result", "verified": False}
        for index in range(4)
    ]


class DataTests(unittest.TestCase):
    def test_normalization_preserves_metadata_and_does_not_change_input(self):
        draws = list(reversed(fixture()))
        draws[0]["numbers"].reverse()
        original = deepcopy(draws)
        normalized = validate_draws(draws, expected_start=1, expected_end=4)
        self.assertEqual(draws, original)
        self.assertEqual([row["round"] for row in normalized], [1, 2, 3, 4])
        self.assertEqual(normalized[-1]["numbers"], [4, 5, 6, 7, 8, 9])
        self.assertFalse(normalized[0]["verified"])
        self.assertEqual(normalized[0]["source"], original[0]["source"])

    def test_rejects_gap_duplicate_and_incomplete_expected_coverage(self):
        draws = fixture()
        invalid = [draws[:1] + draws[2:], draws + [draws[-1]]]
        for rows in invalid:
            with self.subTest(rounds=[row["round"] for row in rows]), self.assertRaises(ValueError):
                validate_draws(rows)
        with self.assertRaises(ValueError):
            validate_draws(draws[1:], expected_start=1)
        with self.assertRaises(ValueError):
            validate_draws(draws, expected_end=5)
        self.assertEqual(len(validate_draws(draws[1:3])), 2)

    def test_rejects_invalid_main_bonus_and_calendar_values(self):
        changes = [
            ("numbers", [1, 1, 2, 3, 4, 5]),
            ("numbers", [1, 2, 3, 4, 5, 46]),
            ("numbers", [True, 2, 3, 4, 5, 6]),
            ("numbers", [1, 2, 3, 4, 5, 6.0]),
            ("numbers", [1, 2, 3, 4, 5]),
            ("bonus", 1), ("bonus", True), ("bonus", 46),
            ("round", 0), ("round", True), ("round", 10 ** 30),
            ("date", "2002-12-08"), ("date", "not a date"),
        ]
        for key, value in changes:
            rows = fixture()
            rows[0][key] = value
            with self.subTest(field=key, value=value), self.assertRaises(ValueError):
                validate_draws(rows)

    def test_invalid_save_preserves_existing_dataset(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "draws.json"
            save_draws(fixture(), path)
            before = path.read_bytes()
            invalid = fixture()
            invalid[-1]["bonus"] = invalid[-1]["numbers"][0]
            with self.assertRaises(ValueError):
                save_draws(invalid, path)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(load_draws(path), fixture())

    def test_loading_accepts_utf8_bom_and_rejects_corrupt_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "draws.json"
            path.write_text(json.dumps(fixture()), encoding="utf-8-sig")
            self.assertEqual(load_draws(path), fixture())
            path.write_text("{invalid", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_draws(path)

    def test_csv_roundtrip_keeps_main_bonus_and_quoted_source_separate(self):
        draws = fixture()
        draws[0]["source"] = 'Synthetic, "quoted" source\nwith a second line'
        rows = list(csv.DictReader(io.StringIO(draws_csv(draws))))
        self.assertEqual(len(rows), len(draws))
        self.assertEqual(rows[0]["source"], draws[0]["source"])
        self.assertEqual([int(rows[0][f"n{index}"]) for index in range(1, 7)],
                         draws[0]["numbers"])
        self.assertEqual(int(rows[0]["bonus"]), 45)


if __name__ == "__main__":
    unittest.main()
